"""Exercise real SQLite contention at the owner-approval execution gate."""
import concurrent.futures
import os
import tempfile
import unittest
from config import config
from memory.database import (
    init_db, propose_action, transition_action_status,
    claim_action_for_execution, get_action_by_id,
)


class AtomicActionClaimTests(unittest.TestCase):
    def test_two_workers_cannot_claim_same_approved_action(self):
        previous = config.DATABASE_PATH
        previous_key = config.ACTION_APPROVAL_HMAC_KEY
        with tempfile.TemporaryDirectory() as temp:
            try:
                config.DATABASE_PATH = os.path.join(temp, "claims.db")
                config.ACTION_APPROVAL_HMAC_KEY = "ci-concurrency-test-only-key-not-production"
                init_db()
                action_id = propose_action("COO", "Concurrency test", "printf hello", "shell")
                self.assertTrue(transition_action_status(action_id, "approved", ("pending",)))
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    futures = [executor.submit(claim_action_for_execution, action_id) for _ in range(2)]
                    results = [future.result(timeout=15) for future in futures]
                self.assertEqual(results.count(True), 1)
                self.assertEqual(results.count(False), 1)
                self.assertEqual(get_action_by_id(action_id)["status"], "executing")
            finally:
                config.DATABASE_PATH = previous
                config.ACTION_APPROVAL_HMAC_KEY = previous_key


if __name__ == "__main__":
    unittest.main()
