"""Transactional checkpoint and no-replay behavior using real SQLite."""

import concurrent.futures
import os
import tempfile
import unittest
from config import config
from workflows.step_checkpoints import (
    init_step_checkpoints,
    claim_step,
    finish_step,
    reconcile_interrupted_steps,
)


class DurableStepCheckpointTests(unittest.TestCase):
    def test_concurrent_claim_and_crash_reconciliation_never_replays(self):
        previous = config.DATABASE_PATH
        with tempfile.TemporaryDirectory() as temp:
            try:
                config.DATABASE_PATH = os.path.join(temp, "checkpoint.db")
                init_step_checkpoints()
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                    futures = [
                        pool.submit(claim_step, "run-A", "payment-1") for _ in range(2)
                    ]
                    results = [f.result(timeout=15) for f in futures]
                self.assertEqual(sorted(results), [False, True])
                self.assertEqual(reconcile_interrupted_steps(), 1)
                self.assertFalse(claim_step("run-A", "payment-1"))
                self.assertFalse(finish_step("run-A", "payment-1", "succeeded"))
                self.assertTrue(claim_step("run-A", "analysis-2"))
                self.assertTrue(finish_step("run-A", "analysis-2", "succeeded"))
                self.assertFalse(claim_step("run-A", "analysis-2"))
                self.assertEqual(reconcile_interrupted_steps(), 0)
                # Distinct workflow executions do not collide.
                self.assertTrue(claim_step("run-B", "payment-1"))
            finally:
                config.DATABASE_PATH = previous


if __name__ == "__main__":
    unittest.main()
