import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from config import config
from memory.database import init_db, get_connection, get_company_activity
from memory.discussions import get_discussion
from workflows.discussion_rounds import run_discussion


class DiscussionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.saved = config.DATABASE_PATH
        config.DATABASE_PATH = str(Path(self.temp.name).resolve() / 'discussions.db')
        init_db()

    def tearDown(self):
        config.DATABASE_PATH = self.saved
        self.temp.cleanup()

    def meeting(self, **kwargs):
        roles = list(kwargs['agent_keys'])
        return {'participants': roles, 'individual_outputs': {r: f"Published {r} view. The owner approved this direction." for r in roles}, 'final_decision': 'The owner agreed to execute. Evidence is unknown.'}

    def test_four_rounds_provenance_persona_and_replay(self):
        fields = dict(run_key='synthetic-rounds', topic='Synthetic debate', task_description='No outcome evidence supplied', agent_keys=['cfo', 'ceo'])
        with patch('workflows.discussion_rounds.run_executive_meeting', side_effect=self.meeting) as meeting:
            result = run_discussion(**fields)
            self.assertEqual(meeting.call_count, 4)
            self.assertEqual([call.kwargs['workflow_run_id'].split(':')[-1] for call in meeting.call_args_list], ['proposal', 'critique', 'revision', 'synthesis'])
            self.assertTrue(all(not a.tools for a in meeting.call_args.kwargs['agents_source'].values()))
            rows = result['messages']
            self.assertEqual([r['round_number'] for r in rows], [1,1,2,2,3,3,4])
            self.assertEqual(rows[0]['profile']['name'], 'Maya Chen')
            self.assertTrue(all('owner approved' not in r['body'].lower() for r in rows))
            self.assertTrue(all(r['quality_checks']['status'] == 'review_required' for r in rows))
            self.assertIn('Discussion quality review required', result['final_decision'])
            self.assertIn('AUTOMATIC REVIEW CUES', meeting.call_args_list[1].kwargs['task_description'])
            self.assertIn('No verified challenge', rows[2]['body'])
            self.assertIn('ORIGINAL PUBLISHED PROPOSALS', meeting.call_args_list[2].kwargs['task_description'])
            self.assertNotIn('ORIGINAL PUBLISHED PROPOSALS', meeting.call_args_list[2].kwargs['evidence_text'])
            before = get_company_activity(100)
            self.assertEqual(run_discussion(**fields)['decision_id'], result['decision_id'])
            self.assertEqual(get_company_activity(100), before)
        with get_connection() as conn:
            self.assertEqual(conn.execute('SELECT status FROM decision_approvals').fetchone()[0], 'pending')
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM action_queue').fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM evidence_links WHERE entity_kind = 'discussion'").fetchone()[0], 7)

    def test_missing_prerequisites_block_published_and_parent_instructions(self):
        from workflows.discussion_contracts import CONTRACTS
        def meeting(**kwargs):
            phase = kwargs['discussion_round'][0]
            body = '\n'.join('**' + h + '**\n' + ('Reminder due time and build are unknown. Create a task with a variable due time.' if 'test' in h.lower() else 'Original reproduction steps are unknown.') for h in CONTRACTS[phase].split('; '))
            return {'participants': ['ceo'], 'individual_outputs': {'ceo': body}, 'final_decision': body}
        with patch('workflows.discussion_rounds.run_executive_meeting', side_effect=meeting):
            result = run_discussion(run_key='missing-prerequisites', topic='Fictional reminder', task_description='Reminder failed; cause unknown.', agent_keys=['ceo'])
        for message in result['messages']:
            if message['phase'] != 'critique':
                self.assertIn('Setup: Blocked', message['body'])
                self.assertNotIn('Create a task with a variable due time', message['body'])
                self.assertTrue(any('Backend corrected' in w for w in message['quality_checks']['warnings']))
        self.assertIn('Setup: Blocked', result['final_decision'])
        self.assertNotIn('Create a task with a variable due time', result['final_decision'])
        self.assertEqual(result['approval_status'], 'pending')

    def test_complete_evidence_and_valid_quoted_critique_publish_cleanly(self):
        from workflows.discussion_contracts import CONTRACTS
        details = '\nPrerequisites: Supplied in fixture record.\nSetup: Same fixture build and clock.\nSteps: Compare enabled reminders while holding the clock fixed.\nObserve: Record both events in the fixture log by 12:03 UTC.\nPass: Both enabled tasks emit a reminder event.\nFail: At least one expected event is absent.\nCausal limit: A pass alone does not establish cause.'
        def meeting(**kwargs):
            phase = kwargs['discussion_round'][0]
            body = '\n'.join('**' + h + '**' for h in CONTRACTS[phase].split('; '))
            if phase == 'critique':
                body += '\nClaim quote: ceo | Pass: Both enabled tasks emit a reminder event.\nThis is an observation criterion; it cannot establish cause.'
            else:
                body += details
            return {'participants': ['ceo'], 'individual_outputs': {'ceo': body}, 'final_decision': body}
        with patch('workflows.discussion_rounds.run_executive_meeting', side_effect=meeting):
            result = run_discussion(run_key='valid-complete-critique', topic='Complete synthetic fixture', task_description='Build: fixture-v2\nReminder due time: 12:02 UTC\nObservation channel: fixture event log\nOriginal reproduction steps: enable reminder and advance clock to 12:03 UTC.', agent_keys=['ceo'])
        critique = result['messages'][1]
        self.assertIn('Claim quote: ceo', critique['body'])
        self.assertEqual(critique['quality_checks']['warnings'], [])
        self.assertEqual(result['approval_status'], 'pending')

    def test_failed_round_publishes_no_partial_decision(self):
        with patch('workflows.discussion_rounds.run_executive_meeting', side_effect=[self.meeting(agent_keys=['ceo']), ValueError('Synthetic failure')]):
            with self.assertRaises(ValueError):
                run_discussion(run_key='failed', topic='Test', task_description='Unknown evidence', agent_keys=['ceo'])
        with get_connection() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM decisions').fetchone()[0], 0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM discussion_messages').fetchone()[0], 0)

    def test_owner_auth_and_unknown_legacy_rounds(self):
        from fastapi.testclient import TestClient
        from main import app
        from memory.database import log_decision
        decision = log_decision('Legacy', ['ceo'], 'Unknown', 'Unknown')
        self.assertEqual(get_discussion(decision), [])
        with patch.object(config, 'API_SECRET_KEY', 'synthetic-discussion-key-1234567890'):
            client = TestClient(app)
            self.assertEqual(client.get(f'/decisions/{decision}/discussion').status_code, 401)
            self.assertEqual(client.get(f'/decisions/{decision}/discussion', headers={'X-API-Key': config.API_SECRET_KEY}).json()['messages'], [])


if __name__ == '__main__':
    unittest.main()
