"""Exercise the approval -> durable execution -> restart boundary on SQLite."""

import os
import tempfile
import unittest
from unittest.mock import patch
from config import config
from memory.database import (
    init_db,
    propose_action,
    transition_action_status,
    get_connection,
    get_action_outcome,
    recover_interrupted_actions,
)
from workflows.action_executor import execute_action
from workflows.step_checkpoints import reconcile_interrupted_steps


class ActionCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.saved = (
            config.DATABASE_PATH,
            config.ACTION_APPROVAL_HMAC_KEY,
            config.SANDBOX_MODE,
        )
        config.DATABASE_PATH = os.path.join(self.temp.name, "actions.db")
        config.ACTION_APPROVAL_HMAC_KEY = "test-only-checkpoint-key"
        config.SANDBOX_MODE = True
        init_db()
        self.action = propose_action("COO", "Test only", "printf hello", "shell")
        transition_action_status(self.action, "approved", ("pending",))

    def tearDown(self):
        config.DATABASE_PATH, config.ACTION_APPROVAL_HMAC_KEY, config.SANDBOX_MODE = (
            self.saved
        )
        self.temp.cleanup()

    def status(self):
        with get_connection() as conn:
            return conn.execute(
                "SELECT status FROM workflow_step_checkpoints"
            ).fetchone()[0]

    def test_dry_run_is_persisted_and_never_dispatched_twice(self):
        with patch("workflows.action_executor.send_notification"):
            self.assertTrue(execute_action(self.action)["success"])
        self.assertEqual(self.status(), "succeeded")
        with patch("workflows.action_executor._execute_claimed_action") as dispatch:
            self.assertFalse(execute_action(self.action)["success"])
            dispatch.assert_not_called()

    def test_crash_after_effect_requires_reconciliation_and_cannot_replay(self):
        with patch(
            "workflows.action_executor._execute_claimed_action",
            side_effect=KeyboardInterrupt,
        ):
            with self.assertRaises(KeyboardInterrupt):
                execute_action(self.action)
        self.assertEqual(self.status(), "running")
        self.assertEqual(reconcile_interrupted_steps(), 1)
        self.assertEqual(recover_interrupted_actions(), 1)
        self.assertEqual(self.status(), "inconclusive")
        self.assertEqual(
            get_action_outcome(self.action)["outcome_status"], "inconclusive"
        )
        with patch("workflows.action_executor._execute_claimed_action") as dispatch:
            self.assertFalse(execute_action(self.action)["success"])
            dispatch.assert_not_called()

    def test_exception_after_dispatch_is_uncertain(self):
        with patch(
            "workflows.action_executor._execute_claimed_action", side_effect=OSError
        ):
            self.assertFalse(execute_action(self.action)["success"])
        self.assertEqual(self.status(), "inconclusive")
        self.assertEqual(
            get_action_outcome(self.action)["outcome_status"], "inconclusive"
        )

    def test_live_handler_failure_does_not_prove_absence_of_effects(self):
        with patch(
            "workflows.action_executor._execute_claimed_action",
            return_value={"success": False, "mode": "live"},
        ):
            self.assertFalse(execute_action(self.action)["success"])
        self.assertEqual(self.status(), "inconclusive")
        self.assertEqual(
            get_action_outcome(self.action)["outcome_status"], "inconclusive"
        )
