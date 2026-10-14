"""Atomic generation claims, uncertain delivery closure and saved-history recovery."""

from concurrent.futures import ThreadPoolExecutor
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from config import config
from memory.database import get_connection, get_decision_by_id, init_db, log_decision
from memory import decision_requests as requests


class DecisionRequestTests(unittest.TestCase):
    def test_source_review_changed_during_generation_prevents_saved_decision(self):
        from fastapi.testclient import TestClient
        from memory.evidence import create_source, review_source
        import main

        source = create_source(
            source_key="fictional-race",
            title="Fictional context",
            reference="Owner supplied test record",
            summary="The supplied ledger records 12 forms.",
            observed_at="2026-01-01T00:00:00Z",
        )

        def generate(**kwargs):
            review_source(source["id"], source["version"], "disputed")
            return {
                "final_decision": "Private pending proposal.",
                "participants": ["ceo"],
                "individual_outputs": {},
            }

        key = "synthetic-request-key-12345678901234567890"
        with (
            patch.object(config, "API_SECRET_KEY", key),
            patch(
                "workflows.structured_decision.run_structured_decision",
                side_effect=generate,
            ),
            patch.object(main, "send_notification"),
        ):
            client = TestClient(main.app)
            response = client.post(
                "/decisions/trigger",
                headers={"X-API-Key": key},
                json={
                    "workflow_run_id": "decision:source-race",
                    "topic": "Fictional context race",
                    "task_description": "Review the supplied ledger",
                    "source_ids": [source["id"]],
                    "output_mode": "structured",
                    "agent_keys": ["ceo"],
                },
            )
            self.assertEqual(response.status_code, 409, response.text)
            self.assertEqual(
                requests.inspect("decision:source-race")["status"], "failed"
            )
            with get_connection() as conn:
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 0
                )

    def test_source_expiring_without_version_change_prevents_publication(self):
        import datetime
        from memory.evidence import (
            create_source,
            source_context_snapshot,
            SourceContextChanged,
        )

        source = create_source(
            source_key="fictional-expiry",
            title="Fictional expiring context",
            reference="Owner supplied test record",
            summary="The supplied ledger records 12 forms.",
            observed_at="2026-01-01T00:00:00Z",
            expires_at="2026-01-02T00:00:00Z",
        )
        actual_datetime = datetime.datetime
        moment = [actual_datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)]

        class Clock(actual_datetime):
            @classmethod
            def now(cls, tz=None):
                return moment[0]

        with patch("memory.evidence.datetime.datetime", Clock):
            text, snapshot = source_context_snapshot([source["id"]])
            self.assertIn("current", text)
            moment[0] = actual_datetime(2026, 1, 3, tzinfo=datetime.timezone.utc)
            with self.assertRaises(SourceContextChanged):
                log_decision(
                    "Fictional expiry",
                    ["ceo"],
                    "Read the ledger",
                    "Private proposal",
                    source_ids=[source["id"]],
                    expected_source_snapshot=snapshot,
                )
        with get_connection() as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 0
            )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        )
        self.addCleanup(self.tmp.cleanup)
        self.database = patch.object(
            config, "DATABASE_PATH", str(Path(self.tmp.name) / "company.db")
        )
        self.database.start()
        self.addCleanup(self.database.stop)
        init_db()

    def test_atomic_claim_one_winner_and_changed_input_conflict(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            claims = list(
                pool.map(lambda _: requests.claim("decision:same", "a" * 64), range(12))
            )
        self.assertEqual(sum(owned for owned, _ in claims), 1)
        self.assertTrue(all(state["status"] == "generating" for _, state in claims))
        with self.assertRaises(requests.RequestConflict):
            requests.claim("decision:same", "b" * 64)
        with self.assertRaises(requests.RequestConflict):
            requests.close("decision:same")

    def test_closure_blocks_a_late_delivery_and_never_reopens_identity(self):
        self.assertIsNone(requests.inspect("decision:late"))
        self.assertEqual(requests.close("decision:late")["status"], "closed")
        owned, state = requests.claim("decision:late", "a" * 64)
        self.assertFalse(owned)
        self.assertEqual(state["status"], "closed")
        owned, state = requests.claim("decision:late", "b" * 64)
        self.assertFalse(owned)
        with get_connection() as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 0
            )

    def test_restart_recovers_saved_result_and_interrupts_only_unsaved_work(self):
        from workflows.instance_lock import database_instance_lock

        requests.claim("decision:saved", "a" * 64)
        decision = log_decision(
            "Fictional request",
            ["ceo"],
            "Private test input",
            "Pending owner review.",
            workflow_key="decision:saved",
        )
        requests.claim("decision:interrupted", "b" * 64)
        with database_instance_lock(config.DATABASE_PATH):
            self.assertEqual(requests.recover_interrupted_requests(), 1)
        self.assertEqual(requests.inspect("decision:saved")["decision_id"], decision)
        self.assertEqual(
            requests.inspect("decision:interrupted")["status"], "interrupted"
        )
        self.assertFalse(requests.claim("decision:interrupted", "b" * 64)[0])
        self.assertEqual(get_decision_by_id(decision)["approval_status"], "pending")
        requests.finish("decision:saved", decision_id=decision)
        with self.assertRaises(ValueError):
            requests.finish("decision:saved", decision_id=decision + 1)

    def test_authenticated_concurrent_repeat_does_not_generate_twice(self):
        from fastapi.testclient import TestClient
        import main

        key = "synthetic-request-key-12345678901234567890"
        started, release = threading.Event(), threading.Event()

        def generate(**kwargs):
            started.set()
            if not release.wait(10):
                raise RuntimeError("Test release missing")
            return {
                "final_decision": "Private proposal, pending owner review.",
                "participants": ["ceo"],
                "individual_outputs": {},
            }

        body = {
            "workflow_run_id": "decision:concurrent",
            "topic": "Fictional private request",
            "task_description": "Private supplied test record",
            "output_mode": "structured",
            "agent_keys": ["ceo"],
        }
        with (
            patch.object(config, "API_SECRET_KEY", key),
            patch(
                "workflows.structured_decision.run_structured_decision",
                side_effect=generate,
            ) as model,
            patch.object(main, "send_notification"),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            client = TestClient(main.app)
            self.assertEqual(
                client.get("/decisions/requests/decision:concurrent").status_code, 401
            )
            headers = {"X-API-Key": key}
            first = pool.submit(
                client.post, "/decisions/trigger", json=body, headers=headers
            )
            try:
                self.assertTrue(started.wait(10))
                repeat = client.post("/decisions/trigger", json=body, headers=headers)
                self.assertEqual(repeat.status_code, 202, repeat.text)
                self.assertEqual(repeat.json()["status"], "generating")
                state = client.get(
                    "/decisions/requests/decision:concurrent", headers=headers
                )
                self.assertIn("no-store", state.headers["cache-control"])
                self.assertEqual(state.json()["status"], "generating")
                self.assertEqual(
                    client.post(
                        "/decisions/requests/decision:concurrent/close", headers=headers
                    ).status_code,
                    409,
                )
                changed = client.post(
                    "/decisions/trigger",
                    json={**body, "topic": "Different inputs"},
                    headers=headers,
                )
                self.assertEqual(changed.status_code, 409)
            finally:
                release.set()
            response = first.result(timeout=10)
            self.assertEqual(response.status_code, 200, response.text)
            repeated = client.post("/decisions/trigger", json=body, headers=headers)
            self.assertEqual(repeated.status_code, 200)
            self.assertEqual(
                repeated.json()["database_id"], response.json()["database_id"]
            )
            self.assertEqual(model.call_count, 1)
            self.assertEqual(
                get_decision_by_id(response.json()["database_id"])["approval_status"],
                "pending",
            )

    def test_failed_and_closed_api_requests_do_not_automatically_retry(self):
        from fastapi.testclient import TestClient
        import main

        key = "synthetic-request-key-12345678901234567890"
        body = {
            "workflow_run_id": "decision:failed",
            "topic": "Fictional failure",
            "task_description": "Private supplied test record",
            "output_mode": "structured",
            "agent_keys": ["ceo"],
        }
        with (
            patch.object(config, "API_SECRET_KEY", key),
            patch(
                "workflows.structured_decision.run_structured_decision",
                side_effect=RuntimeError("SECRET_MODEL_DETAIL"),
            ) as model,
            patch.object(main, "send_notification"),
        ):
            client = TestClient(main.app)
            headers = {"X-API-Key": key}
            response = client.post("/decisions/trigger", json=body, headers=headers)
            self.assertEqual(response.status_code, 502)
            self.assertNotIn("SECRET_MODEL_DETAIL", response.text)
            repeated = client.post("/decisions/trigger", json=body, headers=headers)
            self.assertEqual(repeated.json()["status"], "failed")
            self.assertEqual(model.call_count, 1)
            close = client.post(
                "/decisions/requests/decision:late/close", headers=headers
            )
            self.assertEqual(close.status_code, 200)
            late = client.post(
                "/decisions/trigger",
                json={**body, "workflow_run_id": "decision:late"},
                headers=headers,
            )
            self.assertEqual(late.json()["status"], "closed")
            self.assertEqual(model.call_count, 1)
            with get_connection() as conn:
                row = dict(
                    conn.execute(
                        "SELECT * FROM decision_generation_requests WHERE request_id='decision:failed'"
                    ).fetchone()
                )
                self.assertNotIn("Private supplied test record", str(row))
                self.assertNotIn("SECRET_MODEL_DETAIL", str(row))
