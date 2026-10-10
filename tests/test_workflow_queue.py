"""Workflow review gates and source retries on disposable SQLite."""

import copy
import sqlite3
from unittest.mock import patch
from tests import test_sprint3_practice_evidence as fixtures
from memory.database import get_connection
from memory.workflow_templates import (
    PRESET,
    validate_steps,
    list_templates,
    review_template,
    create_template,
)
from memory.research_queue import (
    propose_source,
    get_proposal,
    claim_read,
    finish_read,
    recover_queue,
    public_url,
)
from memory.business_discovery import create_brief, claim_stage, finish_stage, get_brief
from memory.evidence import get_source
from workflows.research_queue import read_proposal


class WorkflowQueueTests(fixtures.unittest.TestCase):
    setUp = fixtures.SprintThreeTests.setUp
    tearDown = fixtures.SprintThreeTests.tearDown

    def accepted(self):
        t = list_templates()[0]
        return review_template(
            t["id"], t["review_version"], "reviewed", "Reviewed fixed gates"
        )

    def payload(self, url=None):
        if url is None:
            return fixtures.SprintThreeTests.payload(self)
        return dict(
            title="Fictional fetched document",
            reference=url,
            summary="Synthetic document for retry testing; no buyer demand established.",
            observed_at=fixtures.NOW(),
            source_kind="external_reference",
        )

    def test_graph_rejects_cycles_missing_inputs_and_execution(self):
        self.assertEqual(len(validate_steps(copy.deepcopy(PRESET))), 5)
        variants = []
        for key, value in [
            ("depends_on", ["review_sample"]),
            ("capability", "shell"),
            ("gate", "automatic"),
            ("code", "print(1)"),
        ]:
            steps = copy.deepcopy(PRESET)
            steps[0][key] = value
            variants.append(steps)
        steps = copy.deepcopy(PRESET)
        steps[1]["depends_on"] = []
        variants.append(steps)
        steps = copy.deepcopy(PRESET)
        steps[1]["depends_on"] = ["missing"]
        variants.append(steps)
        steps = copy.deepcopy(PRESET)
        steps[1]["id"] = steps[0]["id"]
        variants.append(steps)
        for steps in variants:
            with self.subTest(steps=steps), self.assertRaises(ValueError):
                validate_steps(steps)

    def test_unreviewed_binding_rolls_back_and_provenance_is_immutable(self):
        t = list_templates()[0]
        with self.assertRaises(ValueError):
            create_brief("Test", "Private only", self.ids, workflow_template_id=t["id"])
        with get_connection() as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM business_discovery").fetchone()[0], 0
            )
        t = self.accepted()
        b = create_brief("Test", "Private only", self.ids, workflow_template_id=t["id"])
        self.assertEqual(b["workflow_template"]["digest"], t["digest"])
        for table in [
            "workflow_template_versions",
            "workflow_template_reviews",
            "business_workflow_bindings",
        ]:
            with get_connection() as conn, self.assertRaises(sqlite3.IntegrityError):
                conn.execute(f"DELETE FROM {table}")

    def test_withdrawal_blocks_claim_and_publication_without_rewriting_records(self):
        t = self.accepted()
        b = create_brief("Test", "Private only", self.ids, workflow_template_id=t["id"])
        b = claim_stage(b["id"], b["version"], "research")
        review_template(
            t["id"], t["review_version"], "withdrawn", "Retire this version"
        )
        with self.assertRaises(ValueError):
            finish_stage(b["id"], "research", "Unverified report", b["version"])
        b = finish_stage(b["id"], "research", None, b["version"])
        with self.assertRaises(ValueError):
            claim_stage(b["id"], b["version"], "research")
        self.assertFalse(get_brief(b["id"])["workflow_template"]["usable"])
        with self.assertRaises(RuntimeError):
            review_template(
                t["id"], t["review_version"] + 1, "reviewed", "Cannot reactivate"
            )
        fresh = create_template(t["template_key"], t["name"], copy.deepcopy(PRESET))
        self.assertEqual(fresh["version"], 2)
        self.assertFalse(fresh["usable"])

    def test_queue_is_not_evidence_and_read_is_unverified_idempotent(self):
        q = propose_source(
            "https://docs.python.org/3/", "Investigate a buyer hypothesis", "buyer"
        )
        self.assertFalse(q["counts_as_evidence"])
        with get_connection() as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM evidence_sources").fetchone()[0], 3
            )
        with patch(
            "workflows.research_queue.fetch_public_source",
            return_value=self.payload(q["url"]),
        ) as fetch:
            q = read_proposal(q["id"], q["version"])
            again = read_proposal(q["id"], 1)
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(q["source_id"], again["source_id"])
        source = get_source(q["source_id"])
        self.assertEqual(source["verification"], "unverified")
        with get_connection() as conn:
            self.assertIsNone(
                conn.execute(
                    "SELECT * FROM business_source_annotations WHERE source_id=?",
                    (q["source_id"],),
                ).fetchone()
            )
        self.assertEqual(propose_source(q["url"], "Same URL")["id"], q["id"])
        fresh = propose_source(q["url"], "Fresh capture", new_snapshot=True)
        self.assertNotEqual(fresh["id"], q["id"])
        self.assertIsNone(fresh["source_id"])

    def test_failed_read_and_recovery_do_not_create_evidence(self):
        q = propose_source("https://docs.python.org/3/", "Read document")
        with patch(
            "workflows.research_queue.fetch_public_source",
            side_effect=ValueError("Read failed"),
        ):
            with self.assertRaises(ValueError):
                read_proposal(q["id"], q["version"])
        q = get_proposal(q["id"])
        self.assertEqual(q["state"], "failed")
        self.assertIsNone(q["source_id"])
        q = claim_read(q["id"], q["version"])
        recover_queue()
        q = get_proposal(q["id"])
        self.assertEqual(q["state"], "needs_review")
        with patch(
            "workflows.research_queue.fetch_public_source",
            return_value=self.payload(q["url"]),
        ) as fetch:
            q = read_proposal(q["id"], q["version"])
            self.assertEqual(fetch.call_count, 1)
        self.assertEqual(q["state"], "fetched")

    def test_publication_gap_reuses_checkpoint_without_duplicate_fetch(self):
        q = propose_source("https://docs.python.org/3/", "Retry document")
        original = finish_read

        def fail_publication(ident, version, payload=None):
            if payload is not None:
                raise RuntimeError("Synthetic publication gap")
            return original(ident, version)

        with patch(
            "workflows.research_queue.fetch_public_source",
            return_value=self.payload(q["url"]),
        ) as fetch:
            with patch(
                "workflows.research_queue.finish_read", side_effect=fail_publication
            ):
                with self.assertRaises(RuntimeError):
                    read_proposal(q["id"], q["version"])
            q = get_proposal(q["id"])
            q = read_proposal(q["id"], q["version"])
            self.assertEqual(fetch.call_count, 1)
        self.assertEqual(q["state"], "fetched")
        with get_connection() as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM evidence_sources").fetchone()[0], 4
            )

    def test_registration_and_link_are_atomic(self):
        q = propose_source("https://docs.python.org/3/", "Atomic link")
        q = claim_read(q["id"], q["version"])
        with get_connection() as conn:
            conn.execute(
                "CREATE TRIGGER synthetic_failure BEFORE UPDATE ON research_source_queue WHEN NEW.state='fetched' BEGIN SELECT RAISE(ABORT,'synthetic failure'); END"
            )
            conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            finish_read(q["id"], q["version"], self.payload(q["url"]))
        with get_connection() as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM evidence_sources").fetchone()[0], 3
            )
        self.assertIsNone(get_proposal(q["id"])["source_id"])

    def test_url_guards(self):
        for url in [
            "http://127.0.0.1/",
            "http://10.0.0.1/",
            "https://example.org/page",
            "https://docs.python.org/?key=abc",
            "https://user:pass@docs.python.org/",
            "https://docs.python.org:9000/",
            "file:///tmp/test",
            "https://app.local/",
        ]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                public_url(url)

    def test_owner_api_auth_and_strict_controls(self):
        from fastapi.testclient import TestClient
        from main import app
        from config import config

        with patch.object(config, "API_SECRET_KEY", "synthetic-workflow-test-key"):
            client = TestClient(app)
            self.assertEqual(client.get("/workflow-templates").status_code, 401)
            headers = {"X-API-Key": "synthetic-workflow-test-key"}
            response = client.get("/workflow-templates", headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertIn("no-store", response.headers["cache-control"])
            t = response.json()[0]
            self.assertEqual(
                client.post(
                    f"/workflow-templates/{t['id']}/review",
                    headers=headers,
                    json={
                        "expected_version": True,
                        "state": "reviewed",
                        "note": "Test",
                    },
                ).status_code,
                422,
            )
            self.assertEqual(
                client.post(
                    "/research-queue",
                    headers=headers,
                    json={
                        "url": "https://docs.python.org/3/",
                        "purpose": "Test",
                        "execute": True,
                    },
                ).status_code,
                422,
            )

    def test_retry_keeps_frozen_practice_approval(self):
        t = self.accepted()

        def bound(*args, **kwargs):
            return create_brief(*args, **kwargs, workflow_template_id=t["id"])

        with patch.object(fixtures, "create_brief", side_effect=bound):
            b = fixtures.SprintThreeTests.brief(self)
        from workflows.business_discovery import run_stage, continue_private_run
        from memory.run_inspector import list_runs, get_run

        before = b["practice_specification"]
        with patch(
            "workflows.business_discovery._reason",
            side_effect=RuntimeError("Synthetic generation failure"),
        ):
            with self.assertRaises(RuntimeError):
                run_stage(b["id"], b["version"], "practice")
        b = get_brief(b["id"])
        r = list_runs()["private_runs"][0]
        text = "Fictional input A is the only supplied fact for this private summary. Missing outcome details remain unknown. No action has been taken; the owner must assess this sample separately."
        with patch("workflows.business_discovery._reason", return_value=text):
            b = continue_private_run(r["id"], r["control_version"], b["version"])
        self.assertEqual(b["practice_specification"], before)
        self.assertEqual(len(b["attempts"]), 1)
        self.assertEqual(
            get_run(r["id"])["continued_by"], list_runs()["private_runs"][0]["id"]
        )

    def test_concurrent_reads_have_one_owner(self):
        import concurrent.futures
        import threading

        q = propose_source("https://docs.python.org/3/", "Concurrent test")
        entered, release = threading.Event(), threading.Event()

        def fetch(url):
            entered.set()
            if not release.wait(10):
                raise AssertionError("Test release timed out")
            return self.payload(url)

        with (
            patch(
                "workflows.research_queue.fetch_public_source", side_effect=fetch
            ) as reader,
            concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool,
        ):
            worker = pool.submit(read_proposal, q["id"], q["version"])
            try:
                self.assertTrue(entered.wait(10))
                with self.assertRaises(RuntimeError):
                    read_proposal(q["id"], q["version"])
            finally:
                release.set()
            self.assertEqual(worker.result(timeout=10)["state"], "fetched")
            self.assertEqual(reader.call_count, 1)
