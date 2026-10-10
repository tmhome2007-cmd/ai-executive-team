"""Regression checks for evidence."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from config import config
from memory.database import init_db, log_decision, get_connection, get_company_activity
from memory.evidence import (
    create_source,
    review_source,
    add_evidence_link,
    entity_evidence,
)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.saved = config.DATABASE_PATH
        config.DATABASE_PATH = str(Path(self.temp.name).resolve() / "evidence.db")
        init_db()
        self.fields = dict(
            source_key="synthetic-source",
            title="Synthetic counter",
            reference="https://example.test/counter",
            summary="Synthetic counter = 4",
            observed_at="2020-01-01T00:00:00Z",
            expires_at="2020-01-02T00:00:00Z",
        )

    def tearDown(self):
        config.DATABASE_PATH = self.saved
        self.temp.cleanup()

    def test_provenance_freshness_conflicts_and_retry(self):
        source = create_source(**self.fields)
        self.assertEqual(source["freshness"], "stale")
        self.assertEqual(source["verification"], "unverified")
        events = get_company_activity(100)
        self.assertEqual(create_source(**self.fields)["id"], source["id"])
        self.assertEqual(get_company_activity(100), events)
        with self.assertRaises(RuntimeError):
            create_source(**{**self.fields, "summary": "Different fact"})
        decision = log_decision("Test", ["ceo"], "No external evidence", "Unknown")
        add_evidence_link(
            source_id=source["id"],
            entity_kind="decision",
            entity_id=decision,
            relation="contradicts",
            claim="Four checks passed",
        )
        evidence = entity_evidence("decision", decision)
        self.assertTrue(evidence["conflicting"])
        review_source(source["id"], 1, "owner_confirmed")
        with self.assertRaises(RuntimeError):
            review_source(source["id"], 1, "disputed")
        with get_connection() as conn:
            self.assertEqual(
                conn.execute("SELECT status FROM decision_approvals").fetchone()[0],
                "pending",
            )

    def test_missing_legacy_and_invalid_source_fail_closed(self):
        decision = log_decision("Test", ["ceo"], "Context", "Unknown")
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO decisions(timestamp,topic,agents_involved,task_description,decision_outcome,sandbox_mode) VALUES ('2020','Legacy','ceo','Unknown','Unknown',1)"
            )
            ident = conn.execute("SELECT MAX(id) FROM decisions").fetchone()[0]
            conn.commit()
        self.assertTrue(entity_evidence("decision", ident)["missing"])
        for change in [
            dict(reference="https://user:password@example.test/x"),
            dict(summary="api_key=do-not-store"),
            dict(observed_at="2999-01-01T00:00:00Z"),
            dict(reference="https://example.test/x?credential=private"),
        ]:
            with self.assertRaises(ValueError):
                create_source(**{**self.fields, **change})
        with self.assertRaises(LookupError):
            add_evidence_link(
                source_id=99999, entity_kind="decision", entity_id=decision
            )

    def test_owner_api_validation_and_registry_does_not_fetch(self):
        from fastapi.testclient import TestClient
        from main import app

        with (
            patch.object(config, "API_SECRET_KEY", "synthetic-evidence-key-1234567890"),
            patch(
                "requests.get",
                side_effect=AssertionError("Registry must not fetch URLs"),
            ),
        ):
            client = TestClient(app)
            self.assertEqual(
                client.post("/evidence", json=self.fields).status_code, 401
            )
            headers = {"X-API-Key": config.API_SECRET_KEY}
            self.assertEqual(
                client.post("/evidence", headers=headers, json=self.fields).status_code,
                200,
            )
            self.assertEqual(
                client.get("/evidence?limit=101", headers=headers).status_code, 422
            )
            self.assertEqual(
                client.get("/evidence-for/decision/99999", headers=headers).status_code,
                404,
            )


if __name__ == "__main__":
    unittest.main()
