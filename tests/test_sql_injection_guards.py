"""Adversarial SQL-identifier/status input tests against real SQLite."""
import json
import os
import tempfile
import unittest
from config import config
from memory.database import (
    init_db, get_company_goals, get_followup_events,
    import_history_from_jsonl, _sync_record_signature, create_company_goal,
    update_company_goal, get_company_goal,
    get_resource_requests, transition_action_status,
)


class SQLInjectionGuardTests(unittest.TestCase):
    def test_signed_import_cannot_inject_table_or_column_identifiers(self):
        saved = config.DATABASE_PATH, config.SYNC_HMAC_KEY
        with tempfile.TemporaryDirectory() as temp:
            try:
                config.DATABASE_PATH = os.path.join(temp, "imports.db")
                config.SYNC_HMAC_KEY = "test-only-signed-import-key"
                init_db()
                row = {"_table": "company_goals", "sync_uuid": "test-uuid",
                       "created_at": "2026-10-08", "updated_at": "2026-10-08",
                       "title": "Test", "description": "Test", "success_criteria": "Test",
                       "priority": "low", "status": "active"}
                bad_table = dict(row, _table="company_goals; DROP TABLE action_queue; --")
                bad_column = dict(row)
                bad_column["title); DROP TABLE action_queue; --"] = "attack"
                path = os.path.join(temp, "import.jsonl")
                with open(path, "w") as stream:
                    for attack in (bad_table, bad_column):
                        attack["_signature"] = _sync_record_signature(attack)
                        stream.write(json.dumps(attack) + "\n")
                result = import_history_from_jsonl(path)
                self.assertEqual(result["skipped_existing"], 2)
                self.assertEqual(get_company_goals(), [])
                # Values in dynamic UPDATE queries remain bound parameters.
                goal_id = create_company_goal("Test", "Test", "Test")
                literal = "x'); DROP TABLE company_goals; --"
                update_company_goal(goal_id, title=literal)
                self.assertEqual(get_company_goal(goal_id)["title"], literal)
            finally:
                config.DATABASE_PATH, config.SYNC_HMAC_KEY = saved

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
