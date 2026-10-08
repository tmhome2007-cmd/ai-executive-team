"""Real SQLite checks for task integrity and separate planning/execution authority."""
import tempfile
import unittest
from pathlib import Path
from config import config
from memory.database import init_db, get_connection, log_decision, create_company_goal, propose_action, action_provenance_scope, get_decision_by_id, transition_decision_approval, claim_decision_for_preparation
from memory.agile import create_board, list_tasks, create_task, update_task, create_roadmap_board


class AgileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.saved = config.DATABASE_PATH
        config.DATABASE_PATH = str(Path(self.temp.name).resolve() / 'agile.db')
        init_db()
        self.board = create_board('Synthetic company work', 'company')

    def tearDown(self):
        config.DATABASE_PATH = self.saved
        self.temp.cleanup()

    def test_stale_editor_and_completion_requirements(self):
        task = create_task(self.board, title='Synthetic observation')
        with self.assertRaises(ValueError):
            update_task(task['id'], 1, status='ready')
        task = update_task(task['id'], 1, status='ready', acceptance_criteria='Record the observed outcome')
        with self.assertRaises(RuntimeError):
            update_task(task['id'], 1, title='Stale overwrite')
        with self.assertRaises(ValueError):
            update_task(task['id'], 2, status='done')
        with self.assertRaises(ValueError):
            update_task(task['id'], 2, status='blocked')
        task = update_task(task['id'], 2, status='done', completion_note='Synthetic observation verified')
        self.assertEqual(task['version'], 3)
        self.assertEqual(task['status'], 'done')

    def test_links_and_status_never_execute(self):
        goal = create_company_goal('Test goal', 'Synthetic mission', 'Synthetic criteria', status='active')
        decision = log_decision('Synthetic direction', ['ceo'], 'Synthetic data', 'Direction', goal_id=goal)
        transition_decision_approval(decision, 'approved', ('pending',))
        claim_decision_for_preparation(decision)
        with action_provenance_scope(decision, get_decision_by_id(decision)['sync_uuid']):
            action = propose_action('CTO', 'Synthetic action', 'printf synthetic')
        task = create_task(self.board, title='Review proposed action', acceptance_criteria='Owner review', goal_id=goal, decision_id=decision, action_id=action, assignee='cto')
        update_task(task['id'], 1, status='done', completion_note='Review completed')
        with get_connection() as conn:
            self.assertEqual(conn.execute('SELECT status FROM action_queue WHERE id = ?', (action,)).fetchone()[0], 'pending')
        other = log_decision('Other direction', ['ceo'], 'Other synthetic data', 'Other direction')
        with self.assertRaises(ValueError):
            create_task(self.board, title='Mismatched lineage', decision_id=other, action_id=action)
        development = create_board('Development', 'development')
        with self.assertRaises(ValueError):
            create_task(development, title='Wrong scope', decision_id=decision)
        with self.assertRaises(ValueError):
            create_task(self.board, title='Missing link', action_id=999999)

    def test_seed_is_idempotent_and_secrets_rejected(self):
        first = create_roadmap_board()
        self.assertEqual(create_roadmap_board()['id'], first['id'])
        tasks = list_tasks(first['id'])
        self.assertEqual(len(tasks), 14)
        self.assertEqual(len({t['title'] for t in tasks}), 14)
        with self.assertRaises(ValueError):
            create_task(self.board, title='Credential', description='api_key=do-not-store')
        self.assertEqual(list_tasks(self.board), [])

    def test_authenticated_api_and_stale_conflict(self):
        from fastapi.testclient import TestClient
        from unittest.mock import patch
        from main import app
        client = TestClient(app)
        with patch.object(config, 'API_SECRET_KEY', 'synthetic-agile-test-key-1234567890'):
            headers = {'X-API-Key': config.API_SECRET_KEY}
            self.assertEqual(client.post('/boards/roadmap').status_code, 401)
            self.assertEqual(client.post('/boards/roadmap', headers=headers).status_code, 200)
            response = client.post(f'/boards/{self.board}/tasks', headers=headers, json={'title': 'Test API task'})
            self.assertEqual(response.status_code, 200)
            task = response.json()
            self.assertEqual(client.patch(f"/tasks/{task['id']}", headers=headers, json={'expected_version': 1, 'title': 'Changed'}).status_code, 200)
            self.assertEqual(client.patch(f"/tasks/{task['id']}", headers=headers, json={'expected_version': 1, 'title': 'Stale'}).status_code, 409)
            self.assertEqual(client.get(f'/boards/{self.board}/tasks?limit=101', headers=headers).status_code, 422)


if __name__ == '__main__':
    unittest.main()
