"""Private stop/continue fencing, cached recovery and metadata privacy."""

import concurrent.futures
import threading
import unittest
from unittest.mock import patch
from tests import test_sprint3_practice_evidence as fixture
from memory.database import get_connection
from memory.business_discovery import get_brief, claim_stage, reconcile_discovery
from memory import run_inspector as inspector
from workflows.business_discovery import run_stage, continue_private_run
from workflows.step_checkpoints import (
    init_step_checkpoints,
    run_json_step,
    reconcile_interrupted_steps,
    claim_step,
)


class InspectorTests(unittest.TestCase):
    setUp = fixture.SprintThreeTests.setUp
    tearDown = fixture.SprintThreeTests.tearDown
    payload = fixture.SprintThreeTests.payload
    brief = fixture.SprintThreeTests.brief
    sample = fixture.SprintThreeTests.sample
    assess = fixture.SprintThreeTests.assess

    def test_live_stop_blocks_old_output_and_continues_once(self):
        b = self.brief()
        entered = threading.Event()
        release = threading.Event()

        def slow(*args, **kwargs):
            entered.set()
            release.wait(10)
            return "Fictional input A is the only supplied fact for this private summary. Missing outcome details remain unknown. No action has been taken; the owner must assess this sample separately."

        with (
            patch("workflows.business_discovery._reason", side_effect=slow),
            concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool,
        ):
            work = pool.submit(run_stage, b["id"], b["version"], "practice")
            try:
                self.assertTrue(entered.wait(10))
                current = inspector.list_runs()["private_runs"][0]
                self.assertEqual(current["phase"], "generating")
                self.assertTrue(current["can_stop"])
                with self.assertRaises(RuntimeError):
                    inspector.stop_run(current["id"], current["control_version"] + 1)
                stopped = inspector.stop_run(current["id"], current["control_version"])
                self.assertTrue(stopped["stop_requested"])
                self.assertFalse(stopped["can_continue"])
                with self.assertRaises(RuntimeError):
                    continue_private_run(
                        current["id"],
                        stopped["control_version"],
                        get_brief(b["id"])["version"],
                    )
            finally:
                release.set()
            with self.assertRaises(RuntimeError):
                work.result(timeout=15)
        b = get_brief(b["id"])
        self.assertEqual(b["state"], "needs_review")
        self.assertEqual(b["attempts"], [])
        stopped = inspector.get_run(current["id"])
        self.assertTrue(stopped["can_continue"])
        with patch(
            "workflows.business_discovery._reason",
            return_value="Fictional input A is the only supplied fact for this private summary. Missing outcome details remain unknown. No action has been taken; the owner must assess this sample separately.",
        ) as reason:
            done = continue_private_run(
                current["id"], stopped["control_version"], b["version"]
            )
            self.assertEqual(done["state"], "sample_ready")
            self.assertEqual(len(done["attempts"]), 1)
            self.assertEqual(reason.call_count, 1)
            with self.assertRaises(RuntimeError):
                continue_private_run(
                    current["id"], stopped["control_version"], b["version"]
                )
            self.assertEqual(reason.call_count, 1)
        self.assertEqual(
            inspector.get_run(current["id"])["continued_by"],
            inspector.list_runs()["private_runs"][0]["id"],
        )

    def test_finished_checkpoint_recovery_reuses_without_inference(self):
        b = self.brief()
        with (
            patch(
                "workflows.business_discovery._reason",
                return_value="Fictional input A is the only supplied fact for this private summary. Missing outcome details remain unknown. No action has been taken; the owner must assess this sample separately.",
            ),
            patch(
                "workflows.business_discovery.finish_stage",
                side_effect=RuntimeError("fixture publication gap"),
            ),
        ):
            with self.assertRaises(RuntimeError):
                run_stage(b["id"], b["version"], "practice")
        row = inspector.list_runs()["private_runs"][0]
        self.assertEqual(row["checkpoint_status"], "succeeded")
        reconcile_discovery()
        reconcile_interrupted_steps()
        inspector.recover_inspector()
        b = get_brief(b["id"])
        row = inspector.get_run(row["id"])
        with patch(
            "workflows.business_discovery._reason",
            side_effect=AssertionError("must not regenerate"),
        ):
            result = continue_private_run(
                row["id"], row["control_version"], b["version"]
            )
        self.assertEqual(len(result["attempts"]), 1)
        self.assertEqual(result["state"], "sample_ready")

    def test_unknown_action_has_no_replay_controls_or_private_payload(self):
        init_step_checkpoints()
        claim_step("secret-run-key", "private-payment-label")
        reconcile_interrupted_steps()
        with get_connection() as conn:
            conn.execute(
                "UPDATE workflow_step_checkpoints SET result_json=?",
                ('{"api_key":"private-sentinel"}',),
            )
            conn.commit()
        data = inspector.list_runs()
        self.assertNotIn("private-sentinel", str(data))
        self.assertNotIn("secret-run-key", str(data))
        self.assertNotIn("private-payment-label", str(data))
        self.assertFalse(data["existing_steps"][0]["can_continue"])
        self.assertIn("Reconcile", data["existing_steps"][0]["pending_input"])

    def test_owner_api_and_stale_controls(self):
        from fastapi.testclient import TestClient
        from config import config
        from main import app

        with patch.object(config, "API_SECRET_KEY", "run-fixture-key"):
            client = TestClient(app)
            self.assertEqual(client.get("/runs").status_code, 401)
            result = client.get("/runs", headers={"X-API-Key": "run-fixture-key"})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.headers["cache-control"], "no-store")
            self.assertEqual(
                client.post(
                    "/runs/1/continue",
                    headers={"X-API-Key": "run-fixture-key"},
                    json={"expected_version": True, "expected_brief_version": 1},
                ).status_code,
                422,
            )

    def test_changed_prompt_never_reuses_saved_output(self):
        b = self.brief()
        b = claim_stage(b["id"], b["version"], "practice")
        ident, run, step = inspector.register_run(
            b["id"], "practice", b["version"], "a" * 64, "b" * 64, "local/model"
        )
        run_json_step(run, step, "a" * 64, lambda: "private sentinel")
        with get_connection() as conn:
            previous = inspector._row(conn, ident)
        with self.assertRaises(RuntimeError):
            inspector.cached_result(previous, "c" * 64, "b" * 64)
        self.assertEqual(
            inspector.cached_result(previous, "a" * 64, "b" * 64), "private sentinel"
        )

    def test_publication_and_completion_are_atomic(self):
        b = self.brief()
        with (
            patch(
                "workflows.business_discovery._reason",
                return_value="Fictional input A is the only supplied fact for this private summary. Missing outcome details remain unknown. No action has been taken; the owner must assess this sample separately.",
            ),
            patch(
                "memory.run_inspector.complete_publication",
                side_effect=RuntimeError("fixture commit failure"),
            ),
        ):
            with self.assertRaises(RuntimeError):
                run_stage(b["id"], b["version"], "practice")
        self.assertEqual(get_brief(b["id"])["attempts"], [])
        self.assertEqual(get_brief(b["id"])["state"], "needs_review")
        row = inspector.list_runs()["private_runs"][0]
        self.assertEqual(row["checkpoint_status"], "succeeded")
        self.assertEqual(row["error_category"], "publication_error")
        with patch(
            "workflows.business_discovery._reason",
            side_effect=AssertionError("no second generation"),
        ):
            result = continue_private_run(
                row["id"], row["control_version"], get_brief(b["id"])["version"]
            )
        self.assertEqual(len(result["attempts"]), 1)
        inspector.recover_inspector()
        self.assertEqual(inspector.list_runs()["private_runs"][0]["phase"], "completed")

    def test_stop_before_repair_prevents_second_model_call(self):
        b = self.brief()
        entered = threading.Event()
        release = threading.Event()

        def invalid(*args, **kwargs):
            entered.set()
            release.wait(10)
            return "Invalid short draft"

        with (
            patch(
                "workflows.business_discovery._reason", side_effect=invalid
            ) as reason,
            concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool,
        ):
            work = pool.submit(run_stage, b["id"], b["version"], "practice")
            try:
                self.assertTrue(entered.wait(10))
                row = inspector.list_runs()["private_runs"][0]
                inspector.stop_run(row["id"], row["control_version"])
            finally:
                release.set()
            with self.assertRaises(RuntimeError):
                work.result(timeout=15)
        self.assertEqual(reason.call_count, 1)
        self.assertEqual(get_brief(b["id"])["attempts"], [])
