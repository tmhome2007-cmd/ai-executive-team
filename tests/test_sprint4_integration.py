"""Combined Sprint 4 privacy and recovery checks using disposable company data."""

import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from config import config
from tests import test_executive_skills as fixtures
from memory.database import get_connection
from memory.business_discovery import get_brief
from memory.executive_skills import decide_skill, bind_skill
from memory.workflow_templates import list_templates, review_template
from memory.run_inspector import list_runs, claim_continuation
from workflows.business_discovery import run_stage
from memory.practice_artifacts import export_sample, download_artifact


class SprintFourIntegrationTests(unittest.TestCase):
    setUp = fixtures.ExecutiveSkillsTests.setUp
    tearDown = fixtures.ExecutiveSkillsTests.tearDown
    payload = fixtures.ExecutiveSkillsTests.payload
    brief = fixtures.ExecutiveSkillsTests.brief
    sample = fixtures.ExecutiveSkillsTests.sample
    assess = fixtures.ExecutiveSkillsTests.assess
    accepted_examples = fixtures.ExecutiveSkillsTests.accepted_examples
    propose = fixtures.ExecutiveSkillsTests.propose

    def test_private_headers_cover_success_auth_lookup_and_validation_errors(self):
        from main import app

        with patch.object(config, "API_SECRET_KEY", "sprint4-synthetic-key"):
            client = TestClient(app)
            headers = {"X-API-Key": "sprint4-synthetic-key"}
            responses = [
                client.get("/runs"),
                client.get("/skills", headers=headers),
                client.get("/skills/99999", headers=headers),
                client.post(
                    "/practice-artifacts",
                    headers=headers,
                    json={"sample_id": True, "kind": "txt"},
                ),
                client.post(
                    "/research-queue",
                    headers=headers,
                    json={
                        "url": "http://127.0.0.1/private",
                        "purpose": "Synthetic denied source",
                    },
                ),
            ]
            self.assertEqual(
                [r.status_code for r in responses], [401, 200, 404, 422, 400]
            )
            for response in responses:
                self.assertEqual(response.headers.get("cache-control"), "no-store")
                self.assertEqual(
                    response.headers.get("x-content-type-options"), "nosniff"
                )

    def test_authentication_precedes_all_sprint4_mutations(self):
        from main import app
        import main

        endpoints = [
            ("POST", "/skills"),
            ("POST", "/skills/draft"),
            ("POST", "/skills/1/decision"),
            ("POST", "/practice-artifacts"),
            ("POST", "/runs/1/stop"),
            ("POST", "/runs/1/continue"),
            ("POST", "/workflow-templates"),
            ("POST", "/workflow-templates/1/review"),
            ("POST", "/research-queue"),
            ("POST", "/research-queue/1/read"),
            ("GET", "/company/knowledge"),
            ("GET", "/practice-artifacts/1/download"),
        ]
        with (
            patch.object(config, "API_SECRET_KEY", "sprint4-synthetic-key"),
            patch.dict(main._failed_auth_attempts, {}, clear=True),
        ):
            client = TestClient(app)
            for method, path in endpoints:
                with self.subTest(path=path):
                    main._failed_auth_attempts.clear()
                    result = client.request(
                        method, path, json={} if method == "POST" else None
                    )
                    self.assertEqual(result.status_code, 401)
            with get_connection() as conn:
                for table in (
                    "executive_skill_versions",
                    "practice_artifacts",
                    "workflow_run_inspection",
                    "research_source_queue",
                ):
                    self.assertEqual(
                        conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0
                    )

    def interrupted(self, brief):
        with (
            patch(
                "workflows.business_discovery._reason",
                return_value="Fictional input A is the only supplied fact for this private summary. Missing outcome details remain unknown. No action has been taken; the owner must assess this sample separately.",
            ),
            patch(
                "workflows.business_discovery.finish_stage",
                side_effect=RuntimeError("Synthetic publication interruption"),
            ),
        ):
            with self.assertRaises(RuntimeError):
                run_stage(brief["id"], brief["version"], "practice")
        from memory.business_discovery import reconcile_discovery
        from memory.run_inspector import recover_inspector

        reconcile_discovery()
        recover_inspector()
        return list_runs()["private_runs"][0]

    def test_revoked_skill_blocks_recovery_and_preserves_existing_export(self):
        config.DATABASE_PATH = str(Path(config.DATABASE_PATH).resolve())
        skill = self.propose()
        decide_skill(skill["id"], 1, "accepted", "Reviewed synthetic examples")
        sample_id = self.examples[0]["attempts"][-1]["id"]
        artifact = export_sample(sample_id, "txt")
        before = download_artifact(artifact["id"])[0]
        third = self.brief(
            facts="Different fictional third example; missing outcomes unknown."
        )
        with get_connection() as conn:
            bind_skill(conn.cursor(), third["id"], skill["id"])
            conn.commit()
        run = self.interrupted(third)
        self.assertTrue(run["can_continue"])
        decide_skill(skill["id"], 2, "revoked", "Retired during recovery")
        run = list_runs()["private_runs"][0]
        self.assertFalse(run["can_continue"])
        self.assertIn("revoked", run["pending_input"])
        with self.assertRaises(RuntimeError):
            claim_continuation(
                run["id"], run["control_version"], get_brief(third["id"])["version"]
            )
        self.assertEqual(download_artifact(artifact["id"])[0], before)
        self.assertEqual(get_brief(third["id"])["attempts"], [])

    def test_withdrawn_template_hides_continuation_and_rejects_claim(self):
        template = list_templates()[0]
        review_template(template["id"], 1, "reviewed", "Reviewed fixed private gates")
        brief = self.brief()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO business_workflow_bindings VALUES(?,?,?)",
                (brief["id"], template["id"], "2026-10-10"),
            )
            conn.commit()
        run = self.interrupted(brief)
        self.assertTrue(run["can_continue"])
        review_template(template["id"], 2, "withdrawn", "Retired template")
        run = list_runs()["private_runs"][0]
        self.assertFalse(run["can_continue"])
        self.assertIn("withdrawn", run["pending_input"])
        with self.assertRaises(RuntimeError):
            claim_continuation(
                run["id"], run["control_version"], get_brief(brief["id"])["version"]
            )
