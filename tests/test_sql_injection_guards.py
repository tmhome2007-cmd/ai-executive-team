"""Adversarial SQL-identifier/status input tests against real SQLite."""
import os
import tempfile
import unittest
from config import config
from memory.database import (
    init_db, get_company_goals, get_followup_events,
    get_resource_requests, transition_action_status,
)


class SQLInjectionGuardTests(unittest.TestCase):
    def test_malicious_dynamic_status_values_cannot_change_sql(self):
        original = config.DATABASE_PATH
        with tempfile.TemporaryDirectory() as temp:
            try:
                config.DATABASE_PATH = os.path.join(temp, "db.sqlite")
                init_db()
                attack = "active'); DROP TABLE company_goals; --"
                with self.assertRaises(ValueError):
                    get_company_goals(statuses=(attack,))
                with self.assertRaises(ValueError):
                    get_followup_events(statuses=(attack,))
                with self.assertRaises(ValueError):
                    get_resource_requests(statuses=(attack,))
                with self.assertRaises(ValueError):
                    transition_action_status(1, "approved", (attack,))
                # Table remains queryable after all adversarial inputs.
                self.assertEqual(get_company_goals(), [])
            finally:
                config.DATABASE_PATH = original


if __name__ == "__main__":
    unittest.main()
