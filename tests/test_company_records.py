"""Real SQLite tests for immutable published contributions and activity provenance."""
import tempfile
import unittest
from pathlib import Path
from config import config
from memory.database import (
    init_db, log_decision, get_decision_contributions, get_company_activity,
    transition_decision_approval, claim_decision_for_preparation,
    finish_decision_preparation, get_decision_by_id, get_connection,
)


class CompanyRecordsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.saved = config.DATABASE_PATH
        config.DATABASE_PATH = str(Path(self.temp.name).resolve() / 'records.db')
        init_db()
        self.profiles = {'ceo': {'name': 'Kai Akira', 'role': 'CEO', 'goal': 'Direction', 'backstory': 'Synthetic profile'}}

    def tearDown(self):
        config.DATABASE_PATH = self.saved
        self.temp.cleanup()

    def decision(self, **kwargs):
        return log_decision('Synthetic decision', ['cfo', 'ceo'], 'Synthetic evidence', 'Published final', **kwargs)

    def test_order_profile_snapshot_and_replay(self):
        outputs = {'cfo': 'Published financial review', 'ceo': 'Published direction'}
        ident = self.decision(workflow_key='records-test', individual_outputs=outputs, executive_profiles=self.profiles)
        rows = get_decision_contributions(ident)
        self.assertEqual([r['executive_key'] for r in rows], ['cfo', 'ceo'])
        self.assertEqual(rows[1]['profile']['name'], 'Kai Akira')
        self.assertEqual(self.decision(workflow_key='records-test', individual_outputs=outputs, executive_profiles=self.profiles), ident)
        self.assertEqual(len(get_decision_contributions(ident)), 2)
        with self.assertRaises(ValueError):
            self.decision(workflow_key='records-test', individual_outputs={'ceo': 'Changed text'})
        self.assertEqual(get_decision_contributions(ident), rows)

    def test_secret_and_invalid_role_roll_back_parent(self):
        for outputs in [{'ceo': 'api_key=do-not-store'}, {'unknown': 'Text'}, {'ceo': 'x' * 100001}]:
            with self.assertRaises(ValueError):
                self.decision(individual_outputs=outputs)
        with get_connection() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM decisions').fetchone()[0], 0)

    def test_preparation_is_atomic_and_not_duplicated(self):
        ident = self.decision()
        self.assertTrue(transition_decision_approval(ident, 'approved', ('pending',)))
        self.assertTrue(claim_decision_for_preparation(ident))
        with self.assertRaises(ValueError):
            finish_decision_preparation(ident, True, 'Plan', {'ceo': 'token=do-not-store'})
        self.assertEqual(get_decision_by_id(ident)['preparation_status'], 'in_progress')
        self.assertTrue(finish_decision_preparation(ident, True, 'Plan', {'ceo': 'Published preparation'}, self.profiles))
        self.assertFalse(finish_decision_preparation(ident, True, 'Plan', {'ceo': 'Other'}))
        self.assertEqual(get_decision_contributions(ident)[0]['phase'], 'preparation')

    def test_legacy_empty_pagination_and_provenance(self):
        ident = self.decision()
        self.assertEqual(get_decision_contributions(ident), [])
        self.decision(individual_outputs={'ceo': 'Published contribution'})
        events = get_company_activity(100)
        self.assertEqual(len({e['event_key'] for e in events}), len(events))
        self.assertEqual(get_company_activity(1, 1), events[1:2])
        self.assertTrue(any(e['category'] == 'conversation' and e['decision_id'] for e in events))
        with self.assertRaises(ValueError):
            get_company_activity(101)

    def test_decision_endpoint_persists_published_outputs(self):
        from fastapi.testclient import TestClient
        from unittest.mock import patch
        from main import app
        client = TestClient(app)
        with patch.object(config, 'API_SECRET_KEY', 'synthetic-records-test-key-1234567890'), \
             patch('main.run_executive_meeting', return_value={'final_decision': 'Published final', 'participants': ['ceo'], 'individual_outputs': {'ceo': 'Published executive recommendation'}}), \
             patch('main.send_notification'):
            response = client.post('/decisions/trigger', headers={'X-API-Key': config.API_SECRET_KEY}, json={
                'topic': 'Synthetic meeting', 'task_description': 'Synthetic evidence', 'agent_keys': ['ceo']})
            self.assertEqual(response.status_code, 200, response.text)
            ident = response.json()['database_id']
            row = get_decision_contributions(ident)[0]
            self.assertEqual(row['body'], 'Published executive recommendation')
            self.assertEqual(row['profile']['name'], 'Kai Akira')

    def test_read_api_requires_auth_and_bounds(self):
        from fastapi.testclient import TestClient
        from unittest.mock import patch
        from main import app
        client = TestClient(app)
        ident = self.decision(individual_outputs={'ceo': 'Published'}, executive_profiles=self.profiles)
        with patch.object(config, 'API_SECRET_KEY', 'synthetic-records-test-key-1234567890'):
            for path in [f'/decisions/{ident}/conversations', '/executives/profiles', '/company/activity']:
                self.assertEqual(client.get(path).status_code, 401)
                response = client.get(path, headers={'X-API-Key': config.API_SECRET_KEY})
                self.assertEqual(response.status_code, 200)
            self.assertEqual(client.get('/company/activity?limit=101', headers={'X-API-Key': config.API_SECRET_KEY}).status_code, 422)
            self.assertEqual(client.get('/decisions/999999/conversations', headers={'X-API-Key': config.API_SECRET_KEY}).status_code, 404)


if __name__ == '__main__':
    unittest.main()
