"""Deterministic identity checks; all daemon responses and inference are synthetic."""

import json
import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from workflows.local_model_identity import resolve_model
from tests import test_sprint4_integration as fixtures
from memory.run_inspector import get_run, list_runs, init_inspector
from memory.business_discovery import get_brief
from memory.database import get_connection
from workflows.business_discovery import run_stage, continue_private_run


class ResolutionTests(unittest.TestCase):
    def llm(self, **values):
        return SimpleNamespace(
            **dict(
                dict(
                    provider="ollama",
                    model="llama3.1",
                    base_url="http://127.0.0.1:11434",
                    temperature=0.0,
                    timeout=None,
                    max_tokens=None,
                ),
                **values,
            )
        )

    def resolve(self, models, llm=None, mode=False):
        response = Mock()
        response.read.return_value = json.dumps({"models": models}).encode()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener = Mock()
        opener.open.return_value = response
        with patch("workflows.local_model_identity.build_opener", return_value=opener):
            result = resolve_model(llm or self.llm(), mode)
        opener.open.assert_called_once_with(
            "http://127.0.0.1:11434/api/tags", timeout=5
        )
        return result

    def test_exact_digest_and_effective_settings_without_secrets(self):
        llm = self.llm()
        llm.api_key = "PRIVATE-SENTINEL"
        result = self.resolve(
            [{"name": "llama3.1:latest", "digest": "sha256:" + "a" * 64}],
            llm,
            "revision",
        )
        self.assertEqual(result["digest"], "a" * 64)
        self.assertEqual(result["configuration"]["max_tokens"], 2000)
        self.assertEqual(result["configuration"]["timeout"], 120)
        self.assertNotIn("PRIVATE-SENTINEL", str(result))

    def test_crewai_v1_endpoint_uses_native_metadata_route(self):
        identity = self.resolve(
            [{"name": "llama3.1:latest", "digest": "a" * 64}],
            self.llm(base_url="http://127.0.0.1:11434/v1"),
        )
        self.assertEqual(
            identity["configuration"]["endpoint"], "http://127.0.0.1:11434/v1"
        )

    def test_missing_invalid_or_ambiguous_digest_blocks(self):
        for models in (
            [],
            [{"name": "llama3.1:latest", "digest": "unknown"}],
            [{"name": "llama3.1:latest", "digest": "a" * 64}] * 2,
        ):
            with (
                self.subTest(models=models),
                self.assertRaisesRegex(RuntimeError, "identity unavailable"),
            ):
                self.resolve(models)

    def test_nonlocal_or_secret_endpoint_never_contacts_network(self):
        for base in (
            "https://example.com",
            "http://127.0.0.1:11434?key=PRIVATE-SENTINEL",
            "http://user:pass@localhost:11434",
            "http://localhost:11434/proxy",
        ):
            with (
                patch("workflows.local_model_identity.build_opener") as opener,
                self.assertRaises(RuntimeError),
            ):
                resolve_model(self.llm(base_url=base))
            opener.assert_not_called()

    def test_unavailable_daemon_sanitizes_error(self):
        with patch(
            "workflows.local_model_identity.build_opener",
            side_effect=OSError("PRIVATE-SENTINEL"),
        ):
            with self.assertRaisesRegex(RuntimeError, "identity unavailable") as result:
                resolve_model(self.llm())
        self.assertNotIn("PRIVATE-SENTINEL", str(result.exception))

    def test_legacy_migration_never_backfills_digest(self):
        conn = sqlite3.connect(":memory:")
        try:
            # Build the historical schema by removing only the new nullable columns.
            init_inspector(conn.cursor())
            conn.execute("ALTER TABLE workflow_run_inspection DROP COLUMN model_digest")
            conn.execute(
                "ALTER TABLE workflow_run_inspection DROP COLUMN model_config_json"
            )
            conn.execute(
                "INSERT INTO workflow_run_inspection(run_id,step_id,brief_id,stage,claimed_version,prompt_digest,prompt_version,model_version,created_at,updated_at) VALUES('old','old',1,'practice',1,'prompt','version','tag','now','now')"
            )
            init_inspector(conn.cursor())
            init_inspector(conn.cursor())
            self.assertEqual(
                conn.execute(
                    "SELECT model_digest,model_config_json FROM workflow_run_inspection"
                ).fetchone(),
                (None, None),
            )
        finally:
            conn.close()


class PrivateIdentityTests(unittest.TestCase):
    setUp = fixtures.SprintFourIntegrationTests.setUp
    tearDown = fixtures.SprintFourIntegrationTests.tearDown
    payload = fixtures.SprintFourIntegrationTests.payload
    brief = fixtures.SprintFourIntegrationTests.brief
    interrupted = fixtures.SprintFourIntegrationTests.interrupted

    def test_changed_digest_or_configuration_rejects_continuation_without_claim(self):
        for change in ("digest", "configuration", "tag"):
            brief = self.brief()
            run = self.interrupted(brief)
            version = get_brief(brief["id"])["version"]
            identity = (
                dict(digest="b" * 64, configuration=run["model_configuration"])
                if change == "digest"
                else dict(
                    digest=run["model_digest"], configuration={"temperature": 1.0}
                )
            )
            if change == "tag":
                identity = dict(
                    digest=run["model_digest"],
                    configuration={**run["model_configuration"], "tag": "replacement"},
                )
            with (
                patch(
                    "workflows.local_model_identity.resolve_model",
                    return_value=identity,
                ),
                patch("workflows.business_discovery._reason") as reason,
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "identity or configuration changed"
                ):
                    continue_private_run(run["id"], run["control_version"], version)
                reason.assert_not_called()
            self.assertEqual(get_brief(brief["id"])["version"], version)
            self.assertEqual(get_run(run["id"])["continued_by"], None)
            self.assertEqual(get_brief(brief["id"])["attempts"], [])

    def test_unavailable_model_leaves_new_brief_unclaimed(self):
        brief = self.brief()
        with (
            patch(
                "workflows.local_model_identity.resolve_model",
                side_effect=RuntimeError("Local model identity unavailable"),
            ),
            patch("workflows.business_discovery._reason") as reason,
        ):
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                run_stage(brief["id"], brief["version"], "practice")
            reason.assert_not_called()
        self.assertEqual(get_brief(brief["id"])["version"], brief["version"])
        self.assertEqual(list_runs()["private_runs"], [])

    def test_legacy_unknown_is_visible_and_blocks_cached_reuse(self):
        brief = self.brief()
        run = self.interrupted(brief)
        with get_connection() as conn:
            conn.execute(
                "UPDATE workflow_run_inspection SET model_digest=NULL,model_config_json=NULL WHERE id=?",
                (run["id"],),
            )
            conn.commit()
        unknown = get_run(run["id"])
        self.assertIsNone(unknown["model_digest"])
        self.assertFalse(unknown["can_continue"])
        self.assertEqual(unknown["recovery_code"], "model_identity_unknown")
        from memory.run_inspector import cached_result, _row

        with get_connection() as conn:
            legacy = _row(conn, run["id"])
        with self.assertRaisesRegex(RuntimeError, "identity is unknown"):
            cached_result(legacy, legacy["prompt_digest"], legacy["prompt_version"])

        with patch("workflows.business_discovery._reason") as reason:
            with self.assertRaisesRegex(RuntimeError, "identity is unknown"):
                continue_private_run(
                    run["id"], run["control_version"], get_brief(brief["id"])["version"]
                )
            reason.assert_not_called()

    def test_retag_during_inference_blocks_publication(self):
        brief = self.brief()
        identities = [
            dict(digest="a" * 64, configuration={}),
            dict(digest="a" * 64, configuration={}),
            dict(digest="b" * 64, configuration={}),
        ]
        text = "Fictional input A is the only supplied fact for this private summary. Missing outcome details remain unknown. No action has been taken; the owner must assess this sample separately."
        with (
            patch(
                "workflows.local_model_identity.resolve_model", side_effect=identities
            ),
            patch("workflows.business_discovery._reason", return_value=text),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "identity or configuration changed"
            ):
                run_stage(brief["id"], brief["version"], "practice")
        self.assertEqual(get_brief(brief["id"])["attempts"], [])
        self.assertEqual(list_runs()["private_runs"][0]["model_digest"], "a" * 64)

    def test_unavailable_model_blocks_continuation_without_claim(self):
        brief = self.brief()
        run = self.interrupted(brief)
        version = get_brief(brief["id"])["version"]
        with (
            patch(
                "workflows.local_model_identity.resolve_model",
                side_effect=RuntimeError("Local model identity unavailable"),
            ),
            patch("workflows.business_discovery._reason") as reason,
        ):
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                continue_private_run(run["id"], run["control_version"], version)
            reason.assert_not_called()
        self.assertEqual(get_brief(brief["id"])["version"], version)
        self.assertIsNone(get_run(run["id"])["continued_by"])
