"""Retained transitions, transaction boundaries, migration gaps and cursor stability."""
import concurrent.futures
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from config import config
from memory.activity import activity_origin
from memory.database import init_db, get_connection, log_decision, transition_decision_approval, get_company_activity, finish_decision_preparation, claim_decision_for_preparation
from memory.agile import create_board, create_task, update_task


class ActivityLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.saved = config.DATABASE_PATH
        config.DATABASE_PATH = str(Path(self.temp.name).resolve() / 'activity.db')
        init_db()

    def tearDown(self):
        config.DATABASE_PATH = self.saved
        self.temp.cleanup()

    def decision(self, **kwargs):
        return log_decision('Synthetic direction', ['ceo'], 'Synthetic input', 'Synthetic output', **kwargs)

    def test_retains_transitions_and_retries_and_rollback(self):
        ident = self.decision(workflow_key='ledger-retry')
        count = len(get_company_activity(100))
        self.assertEqual(self.decision(workflow_key='ledger-retry'), ident)
        self.assertEqual(len(get_company_activity(100)), count)
        with activity_origin('owner', 'http:POST /decisions/review'):
            self.assertTrue(transition_decision_approval(ident, 'approved', ('pending',)))
            self.assertFalse(transition_decision_approval(ident, 'approved', ('pending',)))
        self.assertTrue(claim_decision_for_preparation(ident))
        before = get_company_activity(100)
        with self.assertRaises(ValueError):
            finish_decision_preparation(ident, True, 'Plan', {'ceo': 'token=synthetic-secret'})
        self.assertEqual(get_company_activity(100), before)
        self.assertTrue(finish_decision_preparation(ident, True, 'Plan'))
        states = [r for r in reversed(get_company_activity(100)) if r['entity_table'] == 'decision_approvals']
        self.assertEqual([r['new_state']['preparation_status'] for r in states], ['not_started', 'not_started', 'in_progress', 'completed'])
        approval = states[1]
        self.assertEqual(approval['previous_state']['status'], 'pending')
        self.assertEqual(approval['new_state']['status'], 'approved')
        self.assertEqual(approval['actor'], 'owner')
        self.assertEqual(approval['source'], 'http:POST /decisions/review')
        self.assertEqual(states[-1]['actor'], 'system')

    def test_append_only_noop_and_no_free_text_copy(self):
        ident = self.decision()
        before = get_company_activity(100)
        with get_connection() as conn:
            conn.execute('UPDATE decision_approvals SET status = status WHERE decision_id = ?', (ident,))
            conn.commit()
            for statement in ['UPDATE activity_events SET actor = ?', 'DELETE FROM activity_events WHERE actor = ?']:
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(statement, ('system',))
            contents = ' '.join(str(tuple(r)) for r in conn.execute('SELECT * FROM activity_events'))
            self.assertNotIn('Synthetic input', contents)
            self.assertNotIn('Synthetic output', contents)
        self.assertEqual(get_company_activity(100), before)

    def test_legacy_migration_is_atomic_and_idempotent(self):
        self.decision()
        with get_connection() as conn:
            names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'trigger' AND name LIKE 'activity_%'")]
            for name in names:
                conn.execute(f'DROP TRIGGER "{name}"')
            conn.execute('DROP TABLE activity_events')
            conn.execute('DROP TABLE activity_migrations')
            conn.commit()
        init_db()
        rows = get_company_activity(100)
        self.assertTrue(rows)
        self.assertTrue(all(r['legacy_snapshot'] and r['previous_state'] is None for r in rows))
        self.assertTrue(all('earlier transitions unknown' in r['detail'] for r in rows))
        init_db()
        self.assertEqual(get_company_activity(100), rows)
        self.decision()
        self.assertFalse(get_company_activity(1)[0]['legacy_snapshot'])

    def test_concurrent_claim_only_one_event_and_cursor_stable(self):
        ident = self.decision()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: transition_decision_approval(ident, 'approved', ('pending',)), range(2)))
        self.assertEqual(sum(results), 1)
        updates = [r for r in get_company_activity(100) if r['operation'] == 'update']
        self.assertEqual(len(updates), 1)
        first = get_company_activity(2)
        expected = [r for r in get_company_activity(100) if r['id'] < first[-1]['id']]
        self.decision()
        self.assertEqual(get_company_activity(100, before_id=first[-1]['id']), expected)

    def test_company_board_visibility_and_authenticated_actor(self):
        from main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        development = create_board('Development', 'development')
        create_task(development, title='Development implementation')
        self.assertEqual(get_company_activity(100), [])
        company = create_board('Company', 'company')
        with patch.object(config, 'API_SECRET_KEY', 'synthetic-ledger-owner-key-1234567890'):
            payload = {'title': 'Observe', 'acceptance_criteria': 'Record evidence'}
            self.assertEqual(client.post(f'/boards/{company}/tasks', json=payload).status_code, 401)
            headers = {'X-API-Key': config.API_SECRET_KEY}
            task = client.post(f'/boards/{company}/tasks', headers=headers, json=payload).json()
            response = client.patch(f"/tasks/{task['id']}", headers=headers, json={'expected_version': 1, 'status': 'ready'})
            self.assertEqual(response.status_code, 200)
            items = client.get('/company/activity?limit=1', headers=headers).json()
            self.assertEqual(items['items'][0]['actor'], 'owner')
            self.assertEqual(items['items'][0]['new_state']['status'], 'ready')
            self.assertTrue(items['next_before_id'])
            self.assertEqual(client.get('/company/activity?before_id=0', headers=headers).status_code, 422)
            self.assertEqual(client.get('/company/activity').status_code, 401)


if __name__ == '__main__':
    unittest.main()
