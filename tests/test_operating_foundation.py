"""Operating sprint tests use disposable databases and never real actions."""
import datetime
import json
import sqlite3
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import test_experiments as experiments_tests
from test_experiments import now
from memory.database import (get_connection, add_treasury_entry, propose_action,
    approve_action_with_treasury, claim_action_for_execution, get_action_by_id,
    create_executive_memory, get_executive_memories)
from memory.operating_policies import save_policy, get_policy
from memory.memory_reconciliation import reconcile_memory, expire_memories, curated_memories
from memory.evidence import create_source, review_source
from memory.observation_jobs import schedule_observation, claim_job, get_job, recover_observations, run_observation_jobs, review_job
from memory.agent_runtime import record_state, recover_agent_runtime
from memory.agent_activity_stream import executive_states, stream_page


class OperatingFoundationTests(unittest.TestCase):
    setUp = experiments_tests.ExperimentTests.setUp
    tearDown = experiments_tests.ExperimentTests.tearDown
    experiment = experiments_tests.ExperimentTests.experiment
    terminal = experiments_tests.ExperimentTests.terminal

    def policy(self, **changes):
        return save_policy(expected_version=get_policy()['version'], currency='EUR', note='Synthetic owner limit', **changes)

    def source(self, key='synthetic-current', summary='Recorded test evidence', **changes):
        return create_source(source_key=key, title='Synthetic evidence', reference='Owner test record', summary=summary, observed_at=now(), **changes)

    def test_limits_rollback_and_policy_change_invalidates_approval(self):
        add_treasury_entry('funding',20,'EUR')
        self.policy(max_action_cost=4)
        with self.assertRaises(ValueError): approve_action_with_treasury(self.action)
        self.assertEqual(get_action_by_id(self.action)['status'],'pending')
        self.policy(max_action_cost=5)
        approve_action_with_treasury(self.action)
        self.policy(max_action_cost=5)
        with self.assertRaises(ValueError): claim_action_for_execution(self.action)
        self.assertEqual(get_action_by_id(self.action)['status'],'pending')
        with get_connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM treasury_reservations WHERE status='active'").fetchone()[0],0)
            with self.assertRaises(sqlite3.IntegrityError): conn.execute('DELETE FROM operating_policies')

    def test_concurrent_daily_cap_and_unknown_cost_are_atomic(self):
        add_treasury_entry('funding',20,'EUR'); self.policy(max_daily_cost=5, require_known_cost=True)
        other=propose_action('CTO','Synthetic second','printf synthetic',expected_cost_amount=5,currency='EUR')
        barrier=threading.Barrier(2)
        def approve(ident):
            barrier.wait()
            try: approve_action_with_treasury(ident); return True
            except ValueError: return False
        with ThreadPoolExecutor(2) as executor: self.assertEqual(sum(executor.map(approve,[self.action,other])),1)
        unknown=propose_action('CTO','Unknown cost','printf synthetic')
        with self.assertRaises(ValueError): approve_action_with_treasury(unknown)

    def test_prohibited_types_stale_version_and_malformed_inputs(self):
        self.policy(prohibited_types=['shell']); add_treasury_entry('funding',20,'EUR')
        with self.assertRaises(ValueError): approve_action_with_treasury(self.action)
        with self.assertRaises(RuntimeError): save_policy(expected_version=1,currency='EUR',note='Stale synthetic')
        for invalid in [[{}],['shell','shell']]:
            with self.assertRaises(ValueError): self.policy(prohibited_types=invalid)
        with self.assertRaises(ValueError): self.policy(max_action_cost=float('nan'))

    def test_memory_correction_preserves_original_and_rejects_reactivation(self):
        ident,_=create_executive_memory(executive_key='ceo',memory_kind='general_lesson',lesson='Original synthetic lesson',fingerprint='synthetic-memory')
        source=self.source()
        result=reconcile_memory(ident,expected_version=1,operation='correct',source_ids=[source['id']],note='Owner correction',lesson='Corrected source-backed lesson')
        active=get_executive_memories('ceo')
        self.assertEqual([r['id'] for r in active],[result['replacement_id']])
        with self.assertRaises(RuntimeError): reconcile_memory(ident,expected_version=2,operation='annotate',source_ids=[source['id']],note='Cannot restore')
        with get_connection() as conn:
            self.assertEqual(conn.execute('SELECT lesson FROM executive_memories WHERE id=?',(ident,)).fetchone()[0],'Original synthetic lesson')
            for statement in ['DELETE FROM memory_revisions','UPDATE executive_memories SET lesson=\'changed\' WHERE id=?']:
                with self.assertRaises(sqlite3.IntegrityError): conn.execute(statement,(ident,) if '?' in statement else ())
        again,created=create_executive_memory(executive_key='ceo',memory_kind='general_lesson',lesson='Automatic overwrite',fingerprint='synthetic-memory')
        self.assertEqual(again,ident); self.assertFalse(created)

    def test_memory_conflicts_expiry_and_disputed_sources_withheld(self):
        source=self.source()
        for idx in range(2):
            ident,_=create_executive_memory(executive_key='ceo',memory_kind='general_lesson',lesson=f'Synthetic claim {idx}',fingerprint=f'memory-{idx}')
            reconcile_memory(ident,expected_version=1,operation='annotate',source_ids=[source['id']],note='Source attached',claim_key='same-claim')
        self.assertEqual(get_executive_memories('ceo'),[])
        self.assertTrue(all(m['conflict_review_required'] for m in curated_memories()))
        ident,_=create_executive_memory(executive_key='cto',memory_kind='general_lesson',lesson='Expired record',fingerprint='expired')
        reconcile_memory(ident,expected_version=1,operation='annotate',source_ids=[source['id']],note='Expire old lesson',expires_at='2020-01-01T00:00:00Z')
        self.assertEqual(expire_memories(),1); self.assertEqual(expire_memories(),0)
        self.assertEqual(get_executive_memories('cto'),[])
        review_source(source['id'],1,'disputed')
        with self.assertRaises(RuntimeError): reconcile_memory(ident,expected_version=2,operation='correct',source_ids=[source['id']],note='Invalid correction',lesson='Invalid')

    def job(self, value=25, **changes):
        experiment=self.experiment(); self.terminal()
        measured=now()
        source=self.source(summary=json.dumps(dict(experiment_id=experiment['id'],metric_name='requests',observed_at=measured,value=value)))
        review_source(source['id'],1,'owner_confirmed')
        return schedule_observation(job_key='synthetic-job',experiment_id=experiment['id'],collector='owner_source',source_id=source['id'],due_at='2020-01-01T00:00:00Z',**changes)

    def test_collectors_record_once_and_preserve_unknown(self):
        job=self.job(value=None)
        self.assertEqual(run_observation_jobs(),[job['id']]); self.assertEqual(run_observation_jobs(),[])
        result=get_job(job['id']); self.assertEqual(result['status'],'completed')
        with get_connection() as conn:
            observation=conn.execute('SELECT value FROM experiment_observations').fetchone()
            self.assertIsNone(observation[0])
        with self.assertRaises(RuntimeError): review_job(job['id'],result['version'],'retry')

    def test_claim_recovery_and_invalid_measurement_do_not_replay_tools(self):
        job=self.job(value='invented')
        barrier=threading.Barrier(2)
        def claim(_): barrier.wait(); return claim_job()
        with ThreadPoolExecutor(2) as executor: claims=list(executor.map(claim,[1,2]))
        self.assertEqual(sum(r is not None for r in claims),1)
        recover_observations(); self.assertEqual(get_job(job['id'])['status'],'retry')
        with patch('workflows.action_control.execute_action_control',side_effect=AssertionError('Source collector must not execute actions')):
            run_observation_jobs()
        self.assertEqual(get_job(job['id'])['status'],'needs_review')
        with get_connection() as conn: self.assertEqual(conn.execute('SELECT COUNT(*) FROM experiment_observations').fetchone()[0],0)

    def test_future_jobs_not_claimed_and_unsafe_collectors_rejected(self):
        experiment=self.experiment()
        source=self.source()
        job=schedule_observation(job_key='future-job',experiment_id=experiment['id'],collector='owner_source',source_id=source['id'],due_at='2999-01-01T00:00:00Z')
        self.assertIsNone(claim_job())
        review_job(job['id'],1,'retry'); self.assertIsNone(claim_job())
        with self.assertRaises(ValueError): schedule_observation(job_key='unsafe',experiment_id=experiment['id'],collector='approved_file_read',collection_action_id=self.action,due_at=now())

    def test_observed_runtime_stream_metadata_reset_and_recovery(self):
        self.assertTrue(all(state=='unknown' for state in executive_states().values()))
        record_state('test-run','task','ceo','running'); self.assertEqual(executive_states()['ceo'],'running')
        record_state('test-run','task','ceo','idle'); self.assertEqual(executive_states()['ceo'],'idle')
        events=stream_page()['items']; runtime=[r for r in events if r['category']=='executive']
        self.assertEqual([r['new_state']['state'] for r in runtime],['running','idle'])
        self.assertNotIn('test-run',json.dumps(events)); self.assertNotIn('prompt',json.dumps(events))
        self.assertTrue(stream_page(999999)['reset_required'])
        self.assertEqual(stream_page(events[-1]['id'])['items'],[])
        record_state('test-run','task2','ceo','running'); recover_agent_runtime(); self.assertEqual(executive_states()['ceo'],'unknown')

    def test_real_approved_read_collector_and_changed_binding(self):
        from config import config
        from pathlib import Path
        from workflows.step_checkpoints import init_step_checkpoints
        experiment=self.experiment(); self.terminal(); init_step_checkpoints()
        workspace=Path(self.temp.name)/'workspace'; workspace.mkdir()
        payload=dict(experiment_id=experiment['id'],metric_name='requests',observed_at=now(),value=25)
        (workspace/'measurement.json').write_text(json.dumps(payload))
        with patch.object(config,'WORKSPACE_ROOT',str(workspace)), patch.object(config,'SANDBOX_MODE',False), patch('workflows.action_executor.send_notification'):
            read=propose_action('CTO','Collect synthetic measurement',json.dumps(dict(operation='read',file_path='measurement.json')),action_type='file_operation',expected_cost_amount=0,currency='EUR')
            job=schedule_observation(job_key='real-read',experiment_id=experiment['id'],collector='approved_file_read',collection_action_id=read,due_at='2020-01-01T00:00:00Z')
            approve_action_with_treasury(read)
            self.assertEqual(run_observation_jobs(),[job['id']])
            self.assertEqual(get_job(job['id'])['status'],'completed')
            self.assertEqual(get_action_by_id(read)['status'],'executed')
            self.assertEqual(run_observation_jobs(),[])
            next_job=schedule_observation(job_key='changed-read',experiment_id=experiment['id'],collector='approved_file_read',collection_action_id=read,due_at='2020-01-01T00:00:00Z')
            with get_connection() as conn:
                conn.execute("UPDATE action_queue SET action_detail=? WHERE id=?",(json.dumps(dict(operation='read',file_path='other.json')),read)); conn.commit()
            run_observation_jobs(); self.assertEqual(get_job(next_job['id'])['status'],'needs_review')
            with get_connection() as conn:
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM experiment_observations').fetchone()[0],1)
                with self.assertRaises(sqlite3.IntegrityError): conn.execute("UPDATE observation_jobs SET collector='owner_source'")

    def test_bounded_transient_retry_and_tool_crash_require_review(self):
        job=self.job()
        with patch('memory.observation_jobs.collect_job',side_effect=sqlite3.OperationalError('Synthetic transient failure')):
            run_observation_jobs()
        result=get_job(job['id']); self.assertEqual(result['status'],'retry'); self.assertEqual(result['attempts'],1)
        self.assertIsNone(claim_job())
        with get_connection() as conn:
            conn.execute("UPDATE observation_jobs SET status='running',attempts=3");conn.commit()
        recover_observations(); self.assertEqual(get_job(job['id'])['status'],'needs_review')
        # A tool job interrupted after claim must never enter automatic retry.
        read=propose_action('CTO','Synthetic read',json.dumps(dict(operation='read',file_path='measurement.json')),action_type='file_operation')
        tool=schedule_observation(job_key='tool-crash',experiment_id=job['experiment_id'],collector='approved_file_read',collection_action_id=read,due_at='2020-01-01T00:00:00Z')
        claimed=claim_job(); self.assertEqual(claimed['id'],tool['id']); recover_observations()
        self.assertEqual(get_job(tool['id'])['status'],'needs_review')
        with self.assertRaises(ValueError): review_job(tool['id'],get_job(tool['id'])['version'],'retry')

    def test_sse_resume_releases_connection_and_rejects_excess_clients(self):
        import asyncio
        import foundation_api
        from fastapi import HTTPException
        async def exercise():
            response=await foundation_api.stream_activity(0)
            iterator=response.body_iterator
            item=await anext(iterator)
            self.assertIn('data:',item)
            await iterator.aclose()
            self.assertEqual(foundation_api._active_streams,0)
            with patch.object(foundation_api,'_active_streams',16):
                with self.assertRaises(HTTPException) as error: await foundation_api.stream_activity(0)
                self.assertEqual(error.exception.status_code,429)
        asyncio.run(exercise())

    def test_owner_api_auth_validation_and_version_conflicts(self):
        from fastapi.testclient import TestClient
        from main import app
        from config import config
        client=TestClient(app); headers={'X-API-Key':config.API_SECRET_KEY}
        for path in ['/operating-policy','/memory-review','/observation-jobs','/activity-stream/page']:
            self.assertEqual(client.get(path).status_code,401)
        response=client.put('/operating-policy',headers=headers,json={'expected_version':1,'currency':'EUR','note':'Owner test policy','max_action_cost':0})
        self.assertEqual(response.status_code,200)
        self.assertEqual(client.put('/operating-policy',headers=headers,json={'expected_version':1,'currency':'EUR','note':'Stale'}).status_code,409)
        self.assertEqual(client.get('/activity-stream/page?limit=101',headers=headers).status_code,422)
        self.assertEqual(client.post('/observation-jobs',headers=headers,json={'job_key':'unsafe','experiment_id':1,'collector':'arbitrary_shell','due_at':now()}).status_code,422)
