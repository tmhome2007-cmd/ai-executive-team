"""Disposable owner-controlled discovery; no inference/network or real execution."""
import datetime
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from config import config
from memory.database import init_db, get_connection
from memory.evidence import create_source, review_source
from memory.business_discovery import create_brief, get_brief, select_practice, claim_stage, finish_stage, review_practice, reconcile_discovery
from workflows.business_discovery import run_stage, read_public_source


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = patch.object(config, 'DATABASE_PATH', str(Path(self.temp.name) / 'test.db'))
        self.database.start()
        init_db()
        self.ids = [create_source(source_key=f'synthetic-{i}', title='Synthetic research', reference=f'synthetic record {i}',
            summary='Synthetic platform constraint; customer demand unknown.', observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())['id'] for i in range(3)]
        self.brief = create_brief('Synthetic research', 'Agents do the work. Zero spending.', self.ids)

    def tearDown(self):
        self.database.stop()
        self.temp.cleanup()

    def generate(self):
        with patch('workflows.business_discovery._reason', return_value='Findings: platform constraints only. Unknowns: demand unknown. Recommended next step: private sample.') as reason:
            result = run_stage(self.brief['id'], 1, 'research')
            self.assertEqual(reason.call_count, 1)
            with self.assertRaises(RuntimeError):
                run_stage(self.brief['id'], 1, 'research')
            self.assertEqual(reason.call_count, 1)
        return result

    def plan(self):
        brief = self.generate()
        return select_practice(brief['id'], brief['version'], 'Documentation', 'Draft a synthetic guide', ['Names two prerequisites', 'Labels missing facts'],
            (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).isoformat())

    def test_full_loop_never_approves_actions_or_credits_money(self):
        brief = self.plan()
        with patch('workflows.business_discovery._reason', return_value='Synthetic practice sample; unknown evidence remains unknown.'):
            brief = run_stage(brief['id'], brief['version'], 'practice')
        brief = review_practice(brief['id'], brief['version'], [True, False], 'Checked sample: prerequisite omitted.', datetime.datetime.now(datetime.timezone.utc).isoformat())
        self.assertEqual(brief['review']['assessment'], 'practice_failed')
        self.assertEqual(brief['budget_amount'], 0)
        self.assertEqual(brief['risk_limit'], 0)
        with get_connection() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM action_queue').fetchone()[0], 0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM treasury_entries').fetchone()[0], 0)
        with self.assertRaises(RuntimeError):
            review_practice(brief['id'], brief['version'], [True, True], 'Replacement assessment', datetime.datetime.now(datetime.timezone.utc).isoformat())

    def test_state_and_source_gates(self):
        with self.assertRaises(RuntimeError):
            select_practice(self.brief['id'], 1, 'X', 'Y', ['A', 'B'], '2030-01-01T00:00:00Z')
        review_source(self.ids[0], 1, 'disputed')
        with patch('workflows.business_discovery._reason') as reason:
            with self.assertRaises(ValueError):
                run_stage(self.brief['id'], 1, 'research')
            reason.assert_not_called()
        self.assertEqual(get_brief(self.brief['id'])['state'], 'draft')
        with self.assertRaises(ValueError):
            create_brief('X', 'Y', self.ids[:2])
        with self.assertRaises(ValueError):
            create_brief('X', 'Y', [True, 2, 3])

    def test_crash_and_failure_do_not_replay(self):
        claim_stage(self.brief['id'], 1, 'research')
        reconcile_discovery()
        with patch('workflows.business_discovery._reason') as reason:
            with self.assertRaises(RuntimeError):
                run_stage(self.brief['id'], get_brief(self.brief['id'])['version'], 'research')
            reason.assert_not_called()
        self.assertEqual(get_brief(self.brief['id'])['state'], 'needs_review')

    def test_review_requires_real_boolean_checks(self):
        brief = self.plan()
        with patch('workflows.business_discovery._reason', return_value='Synthetic sample'):
            brief = run_stage(brief['id'], brief['version'], 'practice')
        with self.assertRaises(ValueError):
            review_practice(brief['id'], brief['version'], [1, 1], 'Test evidence', datetime.datetime.now(datetime.timezone.utc).isoformat())
        with self.assertRaises(ValueError):
            review_practice(brief['id'], brief['version'], [True], 'Test evidence', datetime.datetime.now(datetime.timezone.utc).isoformat())
        with self.assertRaises(RuntimeError):
            review_practice(brief['id'], 1, [True, True], 'Test evidence', datetime.datetime.now(datetime.timezone.utc).isoformat())

    def test_source_read_blocks_sensitive_urls_and_failed_reads(self):
        with patch('tools.research_tool.PageReaderTool._run', return_value='Error: blocked') as reader:
            for url in ['https://user:pass@example.org', 'https://example.org?q=private', 'file:///tmp/data']:
                with self.assertRaises(ValueError):
                    read_public_source(url)
            reader.assert_not_called()
            with self.assertRaises(ValueError):
                read_public_source('https://example.org')
        with patch('tools.research_tool.PageReaderTool._run', return_value='Synthetic public page contents.'):
            source = read_public_source('https://example.org')
            self.assertEqual(source['verification'], 'unverified')

    def test_remote_reasoning_is_rejected_and_failure_retained(self):
        from types import SimpleNamespace
        from workflows.business_discovery import _reason
        remote = SimpleNamespace(llm=SimpleNamespace(base_url='https://provider.example', model='ollama/test'))
        with patch.dict('agents.executive_agents.EXECUTIVE_AGENTS_NO_TOOLS', {'cso': remote}):
            with self.assertRaisesRegex(ValueError, 'local Ollama'):
                _reason('Synthetic prompt')
        with patch('workflows.business_discovery._reason', side_effect=ValueError('Synthetic failure')):
            with self.assertRaises(ValueError):
                run_stage(self.brief['id'], 1, 'research')
        self.assertEqual(get_brief(self.brief['id'])['state'], 'needs_review')

    def test_normalized_ollama_provider_and_preflight(self):
        from types import SimpleNamespace
        from workflows.business_discovery import _local_agent
        local = SimpleNamespace(llm=SimpleNamespace(provider='ollama', model='llama3.1', base_url='http://localhost:11434'))
        with patch.dict('agents.executive_agents.EXECUTIVE_AGENTS_NO_TOOLS', {'cso': local}):
            self.assertIs(_local_agent(), local)
        remote_provider = SimpleNamespace(llm=SimpleNamespace(provider='openai', model='ollama/test', base_url='http://localhost:11434'))
        with patch.dict('agents.executive_agents.EXECUTIVE_AGENTS_NO_TOOLS', {'cso': remote_provider}), patch('workflows.business_discovery._reason') as reason:
            with self.assertRaises(ValueError):
                run_stage(self.brief['id'], 1, 'research')
            reason.assert_not_called()
        self.assertEqual(get_brief(self.brief['id'])['state'], 'draft')
        self.assertEqual(get_brief(self.brief['id'])['version'], 1)

    def test_api_forbids_budget_and_launch_fields(self):
        from foundation_api import BusinessBriefRequest, BusinessReview
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            BusinessBriefRequest(title='Synthetic', constraints='Synthetic', source_ids=self.ids, budget_amount=5)
        with self.assertRaises(ValidationError):
            BusinessReview(expected_version=1, results=['true', True], evidence='Synthetic', observed_at='2026-01-01T00:00:00Z')
