"""Combined permission changes, concurrent claims and private recovery guidance."""

import concurrent.futures
import threading
import unittest
from unittest.mock import patch
from tests import test_sprint4_integration as fixtures

from memory.database import get_connection
from memory.business_discovery import get_brief
from memory.executive_skills import bind_skill, decide_skill
from memory.workflow_templates import list_templates, review_template
from memory.run_inspector import get_run, claim_continuation
from workflows.business_discovery import run_stage


class RecoveryTests(unittest.TestCase):
    setUp = fixtures.SprintFourIntegrationTests.setUp
    tearDown = fixtures.SprintFourIntegrationTests.tearDown
    payload = fixtures.SprintFourIntegrationTests.payload
    brief = fixtures.SprintFourIntegrationTests.brief
    sample = fixtures.SprintFourIntegrationTests.sample
    assess = fixtures.SprintFourIntegrationTests.assess
    accepted_examples = fixtures.SprintFourIntegrationTests.accepted_examples
    propose = fixtures.SprintFourIntegrationTests.propose
    interrupted = fixtures.SprintFourIntegrationTests.interrupted

    def bound(self):
        skill = self.propose()
        decide_skill(skill["id"], 1, "accepted", "Synthetic reviewed examples")
        template = list_templates()[0]
        review_template(template["id"], 1, "reviewed", "Synthetic private gates")
        brief = self.brief(facts="Independent fictional recovery example")
        with get_connection() as conn:
            bind_skill(conn.cursor(), brief["id"], skill["id"])
            conn.execute(
                "INSERT INTO business_workflow_bindings VALUES(?,?,?)",
                (brief["id"], template["id"], "2026-10-11"),
            )
            conn.commit()
        return brief, skill, template

    def change(self, kind, skill, template):
        if kind == "revoked":
            decide_skill(skill["id"], 2, "revoked", "PRIVATE-SENTINEL")
        elif kind == "withdrawn":
            review_template(template["id"], 2, "withdrawn", "PRIVATE-SENTINEL")
        else:
            self.assess(self.examples[0], [False, True], correction=True)

    def test_permission_changes_block_stale_claim_and_preserve_history(self):
        for kind in ("revoked", "withdrawn", "corrected"):
            with self.subTest(kind=kind):
                # Separate databases avoid sharing fixture review versions.
                if kind != "revoked":
                    self.tearDown()
                    self.setUp()
                brief, skill, template = self.bound()
                run = self.interrupted(brief)
                history = get_brief(self.examples[0]["id"])["attempts"]
                version = get_brief(brief["id"])["version"]
                self.assertTrue(run["can_continue"])
                self.change(kind, skill, template)
                changed = get_run(run["id"])
                self.assertFalse(changed["can_continue"])
                self.assertIn(kind, changed["recovery_code"])
                self.assertIn("new", changed["recovery_action"])
                self.assertNotIn("PRIVATE-SENTINEL", str(changed))
                with self.assertRaises(RuntimeError):
                    claim_continuation(run["id"], run["control_version"], version)
                self.assertEqual(get_brief(brief["id"])["version"], version)
                self.assertEqual(get_brief(brief["id"])["attempts"], [])
                after = get_brief(self.examples[0]["id"])["attempts"]
                self.assertEqual(after[0]["sample"], history[0]["sample"])
                self.assertEqual(
                    after[0]["reviews"][: len(history[0]["reviews"])],
                    history[0]["reviews"],
                )

    def test_permission_changes_during_generation_fence_publication(self):
        for kind in ("revoked", "withdrawn", "corrected"):
            with self.subTest(kind=kind):
                if kind != "revoked":
                    self.tearDown()
                    self.setUp()
                brief, skill, template = self.bound()
                entered, release = threading.Event(), threading.Event()

                def reason(*args, **kwargs):
                    entered.set()
                    release.wait(10)
                    return "Fictional input A is the only supplied fact for this private summary. Missing outcome details remain unknown. No action has been taken; the owner must assess this sample separately."

                with (
                    patch("workflows.business_discovery._reason", side_effect=reason),
                    concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool,
                ):
                    worker = pool.submit(
                        run_stage, brief["id"], brief["version"], "practice"
                    )
                    try:
                        self.assertTrue(entered.wait(10))
                        self.change(kind, skill, template)
                    finally:
                        release.set()
                    with self.assertRaises((ValueError, RuntimeError)):
                        worker.result(timeout=15)
                self.assertEqual(get_brief(brief["id"])["attempts"], [])

    def test_concurrent_continuation_claim_has_one_winner(self):
        brief = self.brief()
        run = self.interrupted(brief)
        version = get_brief(brief["id"])["version"]
        barrier = threading.Barrier(2)

        def claim():
            barrier.wait(timeout=10)
            try:
                claim_continuation(run["id"], run["control_version"], version)
                return True
            except RuntimeError:
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: claim(), range(2)))
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(get_brief(brief["id"])["version"], version + 1)
        self.assertEqual(get_brief(brief["id"])["attempts"], [])
        self.assertFalse(get_run(run["id"])["can_continue"])

    def test_unexpected_binding_error_is_sanitized(self):
        run = self.interrupted(self.brief())
        with patch(
            "memory.practice_quality.assert_specification",
            side_effect=ValueError("PRIVATE-SENTINEL"),
        ):
            result = get_run(run["id"])
        self.assertFalse(result["can_continue"])
        self.assertNotIn("PRIVATE-SENTINEL", str(result))
        self.assertEqual(result["recovery_code"], "exercise_changed")

    def test_run_headers_cover_success_and_stale_error_responses(self):
        from fastapi.testclient import TestClient
        from config import config
        from main import app

        run = self.interrupted(self.brief())
        with patch.object(config, "API_SECRET_KEY", "synthetic-be38-key"):
            client = TestClient(app)
            headers = {"X-API-Key": "synthetic-be38-key"}
            responses = [
                client.get("/runs"),
                client.get("/runs", headers=headers),
                client.get("/runs/999999", headers=headers),
                client.post(
                    f"/runs/{run['id']}/continue",
                    headers=headers,
                    json={"expected_version": True, "expected_brief_version": 1},
                ),
                client.post(
                    f"/runs/{run['id']}/continue",
                    headers=headers,
                    json={
                        "expected_version": run["control_version"] + 1,
                        "expected_brief_version": get_brief(run["brief_id"])["version"],
                    },
                ),
            ]
            self.assertEqual(
                [r.status_code for r in responses], [401, 200, 404, 422, 409]
            )
            for response in responses:
                self.assertEqual(response.headers.get("cache-control"), "no-store")
                self.assertEqual(
                    response.headers.get("x-content-type-options"), "nosniff"
                )
