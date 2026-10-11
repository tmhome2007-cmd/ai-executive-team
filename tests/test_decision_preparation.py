"""Real SQLite/API characterization of decision preparation without live agents."""

import concurrent.futures
import json
import tempfile
import threading
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from config import config
from main import app, _failed_auth_attempts
from memory.database import (
    action_provenance_scope,
    claim_action_for_execution,
    create_company_goal,
    get_action_by_id,
    get_connection,
    get_decision_by_id,
    get_resource_request_by_id,
    init_db,
    log_decision,
    propose_action,
    transition_decision_approval,
    transition_company_goal_status,
)


class DecisionPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.stack = ExitStack()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.stack.close)
        self.key = "synthetic-preparation-key-1234567890"
        for name, value in {
            "DATABASE_PATH": str(Path(self.temp.name) / "preparation.db"),
            "API_SECRET_KEY": self.key,
            "ACTION_APPROVAL_HMAC_KEY": "synthetic-action-signing-key",
            "SANDBOX_MODE": True,
        }.items():
            self.stack.enter_context(patch.object(config, name, value))
        self.stack.enter_context(patch.dict(_failed_auth_attempts, {}, clear=True))
        self.notify = self.stack.enter_context(patch("main.send_notification"))
        self.meeting = self.stack.enter_context(patch("main.run_executive_meeting"))
        # No lifespan: scheduler, Telegram listener and startup jobs are not started.
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        init_db()
        self.result = {
            "final_decision": "Draft prepared. Owner must review each proposal separately.",
            "participants": ["COO"],
            "individual_outputs": {},
        }
        self.meeting.return_value = self.result

    def decision(self, *, approved=True, **kwargs):
        ident = log_decision(
            "Fictional preparation",
            ["coo"],
            "Only https://example.com/supplied is supplied evidence.",
            "Prepare a private draft, without execution authority.",
            **kwargs,
        )
        if approved:
            self.assertTrue(
                transition_decision_approval(ident, "approved", ("pending",))
            )
        return ident

    def prepare(self, ident, *, authenticated=True):
        response = self.client.post(
            f"/decisions/{ident}/prepare",
            json={"agent_keys": ["coo"]},
            headers={"X-API-Key": self.key} if authenticated else {},
        )
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        return response

    def test_unauthenticated_and_pending_requests_never_start_generation(self):
        ident = self.decision(approved=False)
        self.assertEqual(self.prepare(ident, authenticated=False).status_code, 401)
        self.assertEqual(self.prepare(ident).status_code, 409)
        self.meeting.assert_not_called()
        self.assertEqual(get_decision_by_id(ident)["preparation_status"], "not_started")

    def test_inactive_goal_blocks_claim(self):
        goal = create_company_goal(
            "Fictional goal", "Private draft", "Reviewed draft", status="active"
        )
        ident = self.decision(goal_id=goal)
        transition_company_goal_status(goal, "paused")
        self.assertEqual(self.prepare(ident).status_code, 409)
        self.meeting.assert_not_called()
        self.assertEqual(get_decision_by_id(ident)["preparation_status"], "not_started")

    def test_success_preserves_trusted_context_and_separate_action_approval(self):
        ident = self.decision()
        decision = get_decision_by_id(ident)

        def generate(**kwargs):
            provenance = kwargs["provenance_context"]
            self.assertEqual(
                provenance["allowed_browser_urls"], ["https://example.com/supplied"]
            )
            self.assertEqual(kwargs["evidence_text"], decision["task_description"])
            with action_provenance_scope(ident, decision["sync_uuid"], "preparation"):
                action = propose_action("COO", "Fictional proposal", "printf draft")
            return {**self.result, "proposed_action_ids": [action]}

        self.meeting.side_effect = generate
        self.assertEqual(self.prepare(ident).status_code, 200)
        with get_connection() as conn:
            action_id = conn.execute("SELECT id FROM action_queue").fetchone()[0]
        action = get_action_by_id(action_id)
        self.assertEqual(action["status"], "pending")
        self.assertEqual(action["source_decision_sync_uuid"], decision["sync_uuid"])
        self.assertFalse(claim_action_for_execution(action_id))
        self.assertEqual(get_decision_by_id(ident)["preparation_status"], "completed")
        self.assertEqual(self.prepare(ident).status_code, 409)
        self.assertFalse(transition_decision_approval(ident, "rejected", ("approved",)))
        self.assertEqual(self.meeting.call_count, 1)

    def test_missing_and_orphaned_proposals_fail_provenance_verification(self):
        orphan = propose_action("COO", "Unlinked proposal", "printf draft")
        for action in [orphan, 999999]:
            with self.subTest(action=action):
                ident = self.decision()
                self.meeting.return_value = {
                    **self.result,
                    "proposed_action_ids": [action],
                }
                self.assertEqual(self.prepare(ident).status_code, 502)
                self.assertEqual(
                    get_decision_by_id(ident)["preparation_status"], "failed"
                )
        self.assertEqual(get_action_by_id(orphan)["status"], "pending")
        self.notify.assert_not_called()

    def test_printed_executable_action_is_never_materialized(self):
        ident = self.decision()
        self.meeting.return_value = {
            **self.result,
            "final_decision": json.dumps(
                {
                    "name": "propose_action",
                    "parameters": {"action_detail": "printf draft"},
                }
            ),
        }
        self.assertEqual(self.prepare(ident).status_code, 502)
        self.assertEqual(self.meeting.call_count, 1)
        with get_connection() as conn:
            self.assertEqual(
                conn.execute("SELECT count(*) FROM action_queue").fetchone()[0], 0
            )

    def test_resource_compatibility_fallback_remains_pending_and_has_provenance(self):
        ident = self.decision()
        self.meeting.return_value = {
            **self.result,
            "final_decision": json.dumps(
                {
                    "name": "propose_resource_request",
                    "parameters": {
                        "resource_type": "data",
                        "resource_name": "Approved product facts",
                        "reason": "Required to draft the owner brief",
                    },
                }
            ),
        }
        self.assertEqual(self.prepare(ident).status_code, 200)
        self.assertEqual(self.meeting.call_count, 2)
        with get_connection() as conn:
            request_id = conn.execute("SELECT id FROM resource_requests").fetchone()[0]
        resource = get_resource_request_by_id(request_id)
        self.assertEqual(resource["status"], "pending")
        self.assertEqual(resource["source_decision_id"], ident)
        self.assertEqual(resource["source_phase"], "preparation")

    def test_concurrent_requests_have_one_generator_and_one_conflict(self):
        ident = self.decision()
        entered, release = threading.Event(), threading.Event()

        def generate(**kwargs):
            entered.set()
            if not release.wait(10):
                raise TimeoutError("Synthetic barrier timed out")
            return self.result

        self.meeting.side_effect = generate
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            first = executor.submit(self.prepare, ident)
            try:
                self.assertTrue(entered.wait(10))
                self.assertEqual(self.prepare(ident).status_code, 409)
                self.assertFalse(
                    transition_decision_approval(ident, "rejected", ("approved",))
                )
            finally:
                release.set()
            self.assertEqual(first.result(timeout=10).status_code, 200)
        self.assertEqual(self.meeting.call_count, 1)

    def test_provider_errors_are_private_and_failed_preparation_is_retryable(self):
        ident = self.decision()
        for error, status in [(RuntimeError, 502), (ValueError, 400)]:
            with self.subTest(error=error):
                self.meeting.side_effect = error("PRIVATE-PROVIDER-PAYLOAD-SENTINEL")
                with self.assertLogs("main", level="WARNING") as captured:
                    response = self.prepare(ident)
                self.assertNotIn(
                    "PRIVATE-PROVIDER-PAYLOAD-SENTINEL", str(captured.output)
                )
                self.assertIn(error.__name__, str(captured.output))
                self.assertEqual(response.status_code, status)
                self.assertNotIn("PRIVATE-PROVIDER-PAYLOAD-SENTINEL", response.text)
                self.assertEqual(
                    get_decision_by_id(ident)["preparation_status"], "failed"
                )
        self.meeting.side_effect = None
        self.assertEqual(self.prepare(ident).status_code, 200)

    def test_notification_failure_does_not_leak_or_reverse_completed_preparation(self):
        ident = self.decision()
        self.notify.side_effect = RuntimeError("PRIVATE-NOTIFICATION-PAYLOAD-SENTINEL")
        with self.assertLogs("main", level="WARNING") as captured:
            response = self.prepare(ident)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("PRIVATE-NOTIFICATION-PAYLOAD-SENTINEL", str(captured.output))
        self.assertIn("preparation_notification_failed", str(captured.output))
        self.assertEqual(get_decision_by_id(ident)["preparation_status"], "completed")
