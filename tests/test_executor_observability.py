"""Safe failure events and durable uncertainty under notification/persistence faults."""

from contextlib import ExitStack
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from config import config
from memory.database import (
    init_db,
    propose_action,
    transition_action_status,
    get_action_by_id,
    get_action_outcome,
    recover_interrupted_actions,
)
from workflows.action_executor import execute_action
from workflows.step_checkpoints import finish_step, reconcile_interrupted_steps


class ExecutorObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.stack = ExitStack()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.stack.close)
        for name, value in {
            "DATABASE_PATH": str(Path(self.temp.name) / "events.db"),
            "ACTION_APPROVAL_HMAC_KEY": "synthetic-observability-signing-key",
            "WORKSPACE_ROOT": self.temp.name,
            "SANDBOX_MODE": True,
            "ALLOW_UNSAFE_RAW_SHELL": False,
        }.items():
            self.stack.enter_context(patch.object(config, name, value))
        self.stack.enter_context(patch("workflows.action_executor.send_notification"))
        init_db()
        self.action = propose_action(
            "COO", "Fictional failure exercise", "printf draft"
        )
        transition_action_status(self.action, "approved", ("pending",))
        self.sentinel = "PRIVATE-TOKEN-PROMPT-URL-SENTINEL"

    def safe_event(self, captured, expected):
        self.assertIn(expected, str(captured.output))
        self.assertIn(f"action_id={self.action}", str(captured.output))
        self.assertNotIn(self.sentinel, str(captured.output))

    def assert_no_replay(self):
        with patch("workflows.action_executor._execute_claimed_action") as dispatch:
            self.assertFalse(execute_action(self.action)["success"])
        dispatch.assert_not_called()

    def test_dry_run_notification_error_is_safe_and_does_not_reverse_success(self):
        output = io.StringIO()
        with (
            patch(
                "workflows.action_executor.send_notification",
                side_effect=RuntimeError(self.sentinel),
            ),
            redirect_stdout(output),
            self.assertLogs("workflows.action_executor", level="WARNING") as captured,
        ):
            result = execute_action(self.action)
        self.assertTrue(result["success"])
        self.assertNotIn(self.sentinel, output.getvalue() + str(result))
        self.safe_event(captured, "shell_dry_run_notification_failed")
        self.assert_no_replay()

    def test_block_notification_failure_is_observable_without_enabling_shell(self):
        config.SANDBOX_MODE = False
        with (
            patch(
                "workflows.action_executor.send_notification",
                side_effect=OSError(self.sentinel),
            ),
            patch("workflows.container_executor.run_in_container") as worker,
            self.assertLogs("workflows.action_executor", level="WARNING") as captured,
        ):
            result = execute_action(self.action)
        self.assertTrue(result["blocked"])
        worker.assert_not_called()
        self.safe_event(captured, "shell_block_notification_failed")
        self.assert_no_replay()

    def test_checkpoint_failure_logs_before_persisting_uncertainty_without_dispatch(
        self,
    ):
        with (
            patch(
                "workflows.step_checkpoints.claim_step",
                side_effect=OSError(self.sentinel),
            ),
            patch("workflows.action_executor._execute_claimed_action") as dispatch,
            self.assertLogs("workflows.action_executor", level="WARNING") as captured,
        ):
            result = execute_action(self.action)
        dispatch.assert_not_called()
        self.assertFalse(result["success"])
        self.assertEqual(
            get_action_outcome(self.action)["outcome_status"], "inconclusive"
        )
        self.safe_event(captured, "execution_checkpoint_unavailable")
        self.assert_no_replay()

    def test_effect_exception_is_logged_without_claiming_absence_of_effects(self):
        with (
            patch(
                "workflows.action_executor._execute_claimed_action",
                side_effect=OSError(self.sentinel),
            ),
            self.assertLogs("workflows.action_executor", level="WARNING") as captured,
        ):
            result = execute_action(self.action)
        self.assertFalse(result["success"])
        self.assertEqual(
            get_action_outcome(self.action)["outcome_status"], "inconclusive"
        )
        self.safe_event(captured, "execution_result_unconfirmed")
        self.assertNotIn(self.sentinel, str(result))
        self.assert_no_replay()

    def test_result_persistence_failure_records_uncertainty_and_never_replays(self):
        calls = 0

        def persist(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError(self.sentinel)
            return finish_step(*args, **kwargs)

        with (
            patch(
                "workflows.action_executor._execute_claimed_action",
                return_value={"success": True, "mode": "live"},
            ) as dispatch,
            patch("workflows.step_checkpoints.finish_step", side_effect=persist),
            self.assertLogs("workflows.action_executor", level="WARNING") as captured,
        ):
            result = execute_action(self.action)
        self.assertEqual(dispatch.call_count, 1)
        self.assertFalse(result["success"])
        self.assertEqual(
            get_action_outcome(self.action)["outcome_status"], "inconclusive"
        )
        self.safe_event(captured, "execution_result_unconfirmed")
        self.assert_no_replay()

    def test_persistent_storage_failure_reraises_and_remains_restart_reconcilable(self):
        with (
            patch(
                "workflows.action_executor._execute_claimed_action",
                return_value={"success": True, "mode": "live"},
            ) as dispatch,
            patch(
                "workflows.step_checkpoints.finish_step",
                side_effect=OSError(self.sentinel),
            ),
            self.assertLogs("workflows.action_executor", level="WARNING") as captured,
        ):
            with self.assertRaises(OSError):
                execute_action(self.action)
        self.assertEqual(dispatch.call_count, 1)
        self.safe_event(captured, "execution_result_unconfirmed")
        self.assertEqual(get_action_by_id(self.action)["status"], "executing")
        self.assert_no_replay()
        self.assertEqual(reconcile_interrupted_steps(), 1)
        self.assertEqual(recover_interrupted_actions(), 1)
        self.assertEqual(
            get_action_outcome(self.action)["outcome_status"], "inconclusive"
        )
        self.assert_no_replay()

    def test_file_and_browser_notification_failures_remain_safe_dry_runs(self):
        examples = [
            (
                "file_operation",
                {
                    "operation": "write",
                    "file_path": "draft.txt",
                    "content": "fictional",
                },
                "file_dry_run_notification_failed",
            ),
            (
                "browser_action",
                {"url": "https://example.com/fictional"},
                "browser_dry_run_notification_failed",
            ),
        ]
        for action_type, detail, event in examples:
            with self.subTest(action_type=action_type):
                self.action = propose_action(
                    "CTO", "Fictional dry-run proposal", json.dumps(detail), action_type
                )
                transition_action_status(self.action, "approved", ("pending",))
                with (
                    patch(
                        "workflows.action_executor.check_url_safety", return_value=None
                    ),
                    patch(
                        "workflows.action_executor.send_notification",
                        side_effect=RuntimeError(self.sentinel),
                    ),
                    self.assertLogs(
                        "workflows.action_executor", level="WARNING"
                    ) as captured,
                ):
                    result = execute_action(self.action)
                self.assertTrue(result["success"])
                self.assertEqual(result["mode"], "dry_run")
                self.safe_event(captured, event)
                self.assertFalse((Path(self.temp.name) / "draft.txt").exists())
                self.assert_no_replay()
