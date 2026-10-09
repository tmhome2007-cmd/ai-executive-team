"""Synthetic provider probes and real SQLite approval/claim scope gates."""
import datetime
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from config import config
from memory.database import init_db, get_connection, propose_resource_request, transition_resource_request_status, propose_action, approve_action_with_treasury, claim_action_for_execution, get_action_by_id, log_decision, get_decision_by_id, action_provenance_scope
from memory.capabilities import provide_capability, list_capabilities, revoke_capability, bind_capabilities
from workflows.capability_inventory import verify_capability


class CapabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.saved = config.DATABASE_PATH
        self.saved_key = config.API_SECRET_KEY
        config.API_SECRET_KEY = 'synthetic-capability-test-key-1234567890'
        config.DATABASE_PATH = str(Path(self.temp.name).resolve() / 'scope.db')
        init_db()
        self.environment = patch.dict(os.environ, {'GITHUB_TOKEN': 'synthetic-provider-token-only'})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        config.DATABASE_PATH = self.saved
        config.API_SECRET_KEY = self.saved_key
        self.temp.cleanup()

    def grant(self, **fields):
        resource = propose_resource_request('CTO', 'access', 'Synthetic repo', 'Synthetic test only')
        transition_resource_request_status(resource, 'approved', ('pending',))
        return provide_capability(**{**dict(resource_request_id=resource, provider='github', scopes=['repo.read'], roles=['cto'], target='test-owner/test-repo', secret_ref='GITHUB_TOKEN'), **fields})

    def healthy(self, ident, permissions=None):
        response = Mock(status_code=200)
        response.json.return_value = {'permissions': permissions or {'pull': True, 'push': True}}
        with patch('workflows.capability_inventory.requests.get', return_value=response) as request:
            result = verify_capability(ident)
            self.assertEqual(request.call_args.kwargs['allow_redirects'], False)
            self.assertEqual(request.call_args.kwargs['timeout'], 5)
            self.assertEqual(request.call_args.args[0], 'https://api.github.com/repos/test-owner/test-repo')
            return result

    def action(self, grant, role='CTO', **fields):
        ident = propose_action(role, 'Synthetic gated file', json.dumps({'operation': 'write', 'file_path': 'scope.txt', 'content': 'Synthetic'}), 'file_operation', **fields)
        bind_capabilities(ident, [{'grant_id': grant['id'], 'scope': grant['scopes'][0]}])
        return ident

    def test_provided_is_not_verified_or_authority_and_unscoped_backwards_compatibility(self):
        grant = self.grant()
        action = self.action(grant)
        with self.assertRaises(ValueError):
            approve_action_with_treasury(action)
        self.assertEqual(get_action_by_id(action)['status'], 'pending')
        healthy = self.healthy(grant['id'])
        self.assertEqual(healthy['status'], 'verified')
        self.assertNotIn('credential_fingerprint', healthy)
        self.assertNotIn(os.environ['GITHUB_TOKEN'], json.dumps(list_capabilities()))
        approve_action_with_treasury(action)
        self.assertTrue(claim_action_for_execution(action))
        old = propose_action('CTO', 'Existing safe action', 'printf synthetic')
        approve_action_with_treasury(old)
        self.assertTrue(claim_action_for_execution(old))

    def test_revocation_token_rotation_and_refresh_bind_exact_owner_approval(self):
        grant = self.grant()
        healthy = self.healthy(grant['id'])
        action = self.action(grant)
        approve_action_with_treasury(action)
        self.assertEqual(self.healthy(grant['id'])['version'], healthy['version'])
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'synthetic-rotated-token'}):
            with self.assertRaises(ValueError):
                claim_action_for_execution(action)
            self.healthy(grant['id'])
            with self.assertRaisesRegex(ValueError, 'integrity'):
                claim_action_for_execution(action)
            self.assertEqual(get_action_by_id(action)['status'], 'pending')
            approve_action_with_treasury(action)
            current = list_capabilities()[0]
            revoke_capability(grant['id'], current['version'])
            with self.assertRaises(ValueError):
                claim_action_for_execution(action)
            with self.assertRaises(ValueError):
                verify_capability(grant['id'])
        with get_connection() as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute('DELETE FROM action_capability_requirements WHERE action_id = ?', (action,))

    def test_provider_decline_race_stale_and_wrong_role(self):
        grant = self.grant(scopes=['repo.write'])
        declined = self.healthy(grant['id'], {'pull': True, 'push': False})
        self.assertEqual(declined['status'], 'provided')
        action = self.action(grant)
        with self.assertRaises(ValueError):
            approve_action_with_treasury(action)
        self.healthy(grant['id'])
        wrong = self.action(grant, 'COO')
        with self.assertRaises(ValueError):
            approve_action_with_treasury(wrong)
        with get_connection() as conn:
            conn.execute('UPDATE capability_inventory SET verified_until = ? WHERE id = ?', ((datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)).isoformat(), grant['id']))
            conn.commit()
        with self.assertRaises(ValueError):
            approve_action_with_treasury(action)
        def rotate(*args, **kwargs):
            os.environ['GITHUB_TOKEN'] = 'synthetic-race-token'
            return Mock(status_code=200, json=lambda: {'permissions': {'pull': True, 'push': True}})
        with patch('workflows.capability_inventory.requests.get', side_effect=rotate):
            self.assertEqual(verify_capability(grant['id'])['status'], 'provided')

    def test_browser_exact_host_read_scope_and_manual_unverified(self):
        grant = self.grant(provider='browser', scopes=['page.read'], roles=['coo'], target='example.com', secret_ref=None)
        with patch.object(config, 'ALLOWED_BROWSER_DOMAINS', 'example.com'), patch('playwright.sync_api.sync_playwright'):
            self.assertEqual(verify_capability(grant['id'])['status'], 'verified')
            def browser(url, click=None):
                action = propose_action('COO', 'Synthetic browser', json.dumps({'url': url, 'click_selector': click}), 'browser_action')
                bind_capabilities(action, [{'grant_id': grant['id'], 'scope': 'page.read'}])
                return action
            with self.assertRaises(ValueError):
                approve_action_with_treasury(browser('https://other.example/'))
            with self.assertRaises(ValueError):
                approve_action_with_treasury(browser('https://example.com/', '#submit'))
            action = browser('https://example.com/')
            approve_action_with_treasury(action)
        with patch.object(config, 'ALLOWED_BROWSER_DOMAINS', ''):
            with self.assertRaises(ValueError):
                claim_action_for_execution(action)
        manual = self.grant(provider='manual', scopes=['data.read'], target='Owner-provided dataset', secret_ref=None)
        self.assertEqual(verify_capability(manual['id'])['status'], 'provided')

    def test_lineage_scope_is_required_without_explicit_binding_and_revocation_race(self):
        decision = log_decision('Synthetic browser access', ['coo'], 'Synthetic context', 'Pending')
        with action_provenance_scope(decision, get_decision_by_id(decision)['sync_uuid']):
            grant = self.grant(provider='browser', scopes=['page.read'], roles=['coo'], target='example.com', secret_ref=None)
            action = propose_action('COO', 'Synthetic scoped browser', json.dumps({'url': 'https://example.com/', 'click_selector': '#submit'}), 'browser_action')
        with patch.object(config, 'ALLOWED_BROWSER_DOMAINS', 'example.com'), patch('playwright.sync_api.sync_playwright'):
            verify_capability(grant['id'])
            with self.assertRaisesRegex(ValueError, 'scope'):
                approve_action_with_treasury(action)
        github = self.grant()
        def revoke_during_probe(*args, **kwargs):
            revoke_capability(github['id'], github['version'])
            return Mock(status_code=200, json=lambda: {'permissions': {'pull': True, 'push': True}})
        with patch('workflows.capability_inventory.requests.get', side_effect=revoke_during_probe):
            with self.assertRaises(RuntimeError):
                verify_capability(github['id'])
        self.assertEqual(list_capabilities()[0]['status'], 'revoked')

    def test_api_owner_auth_bounds_and_scope_not_secret_values(self):
        from fastapi.testclient import TestClient
        import main
        client = TestClient(main.app)
        grant = self.grant()
        headers = {'X-API-Key': config.API_SECRET_KEY}
        self.assertEqual(client.get('/capabilities').status_code, 401)
        self.assertEqual(client.get('/capabilities?limit=101', headers=headers).status_code, 422)
        self.assertNotIn(os.environ['GITHUB_TOKEN'], client.get('/capabilities', headers=headers).text)
        action = self.action(grant)
        response = client.post(f'/actions/{action}/capabilities', headers=headers, json={'requirements': [{'grant_id': grant['id'], 'scope': 'repo.read'}]})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('credential_fingerprint', response.text)
        with self.assertRaises(ValueError):
            self.grant(target='test-owner/..')
        with self.assertRaises(ValueError):
            self.grant(secret_ref='ACTUAL_TOKEN_VALUE')


if __name__ == '__main__':
    unittest.main()
