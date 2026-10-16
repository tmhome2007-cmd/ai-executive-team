"""Structured publication, failed sample retention and attributed dissent boundaries."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from workflows import structured_decision as sd


def sample(recommendation="Review the supplied ledger privately.", objections=None):
    """Synthetic role proposal with a real quote from the test source."""
    return dict(
        facts=[dict(source_id="owner-task", quote="The ledger records 12 forms.")],
        unknowns=["Distinct participants are unknown."],
        assumptions=[],
        recommendation=recommendation,
        objections=objections or [],
        success="One discrepancy is documented for owner review.",
        stop="Stop if the original ledger is unavailable.",
        pivotal_fact="Whether the entries represent distinct participants.",
        next_owner_decision="Choose whether to inspect the ledger privately.",
        effort_minutes=20,
    )


class StructuredDecisionTests(unittest.TestCase):
    sources = {
        "owner-task": "The ledger records 12 forms. Participant count is unknown."
    }

    def test_wording_matches_ignore_punctuation_without_inventing_agreement(self):
        ceo = sd.validate_contribution(json.dumps(sample()), self.sources)
        cfo = sd.validate_contribution(
            json.dumps(sample("  REVIEW the supplied   ledger privately  ")),
            self.sources,
        )
        brief = sd.render_brief({"cfo": cfo, "ceo": ceo})
        self.assertIn("Matching proposals: CFO, CEO.", brief)
        self.assertIn("no implied vote", brief)
        self.assertIn("CFO: no objection recorded; agreement is not inferred.", brief)
        different = sd.validate_contribution(
            json.dumps(sample("Do not review the supplied ledger privately.")),
            self.sources,
        )
        self.assertIn(
            "Matching proposals: CEO.",
            sd.render_brief({"cfo": different, "ceo": ceo}),
        )

    def test_rejects_bad_schema_reference_quote_and_consent(self):
        for change in (
            dict(extra="invented"),
            dict(effort_minutes="20"),
            dict(effort_minutes=61),
            dict(recommendation="Owner approved execution."),
            dict(facts=[dict(source_id="fake", quote="The ledger records 12 forms.")]),
            dict(
                facts=[
                    dict(source_id="owner-task", quote="There were 12 participants.")
                ]
            ),
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                sd.validate_contribution(
                    json.dumps({**sample(), **change}), self.sources
                )

    def test_valid_quotes_do_not_assert_consent_from_evidence(self):
        obj = sd.validate_contribution(json.dumps(sample()), self.sources)
        self.assertEqual(obj.effort_minutes, 20)

    def test_blank_fields_and_non_text_provider_response_fail_closed(self):
        with self.assertRaises(ValueError):
            sd.validate_contribution(
                json.dumps({**sample(), "success": "   "}), self.sources
            )
        with tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        ) as tmp:
            transport = unittest.mock.Mock(
                return_value={"done": True, "response": {"invalid": "shape"}}
            )
            with self.assertRaisesRegex(ValueError, "No decision published"):
                sd.generate_contribution(
                    {"prompt": "original"},
                    self.sources,
                    tmp,
                    "ceo",
                    "http://localhost",
                    transport,
                )

    def test_failed_samples_retained_and_no_legacy_fallback(self):
        with tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        ) as tmp:
            transport = unittest.mock.Mock(
                return_value={"done": True, "response": "not json"}
            )
            with self.assertRaisesRegex(ValueError, "No decision published"):
                sd.generate_contribution(
                    {"prompt": "original"},
                    self.sources,
                    tmp,
                    "cfo",
                    "http://localhost",
                    transport,
                )
            self.assertEqual(transport.call_count, 2)
            self.assertEqual(len(list(Path(tmp).glob("cfo-[12].json"))), 2)
            self.assertEqual((Path(tmp) / "cfo-1.json").stat().st_mode & 0o777, 0o600)

    def test_repair_preserves_failed_attempt_and_marks_valid_sample(self):
        with tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        ) as tmp:
            transport = unittest.mock.Mock(
                side_effect=[
                    {"done": True, "response": "{}"},
                    {"done": True, "response": json.dumps(sample())},
                ]
            )
            sd.generate_contribution(
                {"prompt": "original"},
                self.sources,
                tmp,
                "cfo",
                "http://localhost",
                transport,
            )
            self.assertFalse(
                json.loads((Path(tmp) / "cfo-1.json").read_text())["valid"]
            )
            self.assertTrue(json.loads((Path(tmp) / "cfo-2.json").read_text())["valid"])

    def test_provider_error_is_sanitized_and_fail_closed(self):
        with tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        ) as tmp:
            transport = unittest.mock.Mock(side_effect=RuntimeError("SECRET_TOKEN"))
            with self.assertRaises(ValueError) as error:
                sd.generate_contribution(
                    {"prompt": "original"},
                    self.sources,
                    tmp,
                    "cfo",
                    "http://localhost",
                    transport,
                )
            self.assertNotIn("SECRET_TOKEN", str(error.exception))
            self.assertNotIn("SECRET_TOKEN", (Path(tmp) / "cfo-1.json").read_text())

    def test_disagreement_and_unanimous_proposals_keep_actual_attribution(self):
        cfo = sd.Contribution(
            **sample(objections=["Time available may not cover a complete review."])
        )
        ceo = sd.Contribution(
            **sample("Privately compare one entry before expanding review.")
        )
        brief = sd.render_brief({"cfo": cfo, "ceo": ceo})
        self.assertIn("CFO objection: Time available", brief)
        self.assertIn("Matching proposals: CEO.", brief)
        unanimous = sd.render_brief({"cfo": ceo, "ceo": ceo})
        self.assertIn("Matching proposals: CFO, CEO.", unanimous)
        self.assertNotIn("objection:", unanimous)
        self.assertIn("Pending owner review", unanimous)

    def test_workflow_identity_change_cannot_publish_or_propose_actions(self):
        identity = {
            "digest": "a" * 64,
            "configuration": {"resolved_tag": "local:latest"},
        }
        agents = {"ceo": SimpleNamespace(backstory="Canonical CEO personality")}
        with (
            tempfile.TemporaryDirectory(
                dir=Path(tempfile.gettempdir()).resolve()
            ) as tmp,
            patch("config.config.WORKSPACE_ROOT", str(Path(tmp).resolve())),
            patch.object(
                sd,
                "resolve_model",
                side_effect=[identity, {**identity, "digest": "b" * 64}],
            ),
            patch.object(
                sd, "generate_contribution", return_value=sd.Contribution(**sample())
            ),
        ):
            with self.assertRaisesRegex(ValueError, "identity changed"):
                sd.run_structured_decision(
                    "The ledger records 12 forms.",
                    ["ceo"],
                    agents,
                    "local",
                    "http://localhost",
                )
            self.assertFalse(list(Path(tmp).rglob("brief.json")))

    def test_workflow_keeps_canonical_profiles_and_ceo_last(self):
        identity = {
            "digest": "a" * 64,
            "configuration": {"resolved_tag": "local:latest"},
        }
        agents = {
            role: SimpleNamespace(backstory=role + " canonical personality")
            for role in ("ceo", "cfo")
        }
        with (
            tempfile.TemporaryDirectory(
                dir=Path(tempfile.gettempdir()).resolve()
            ) as tmp,
            patch("config.config.WORKSPACE_ROOT", str(Path(tmp).resolve())),
            patch.object(sd, "resolve_model", return_value=identity),
            patch.object(
                sd,
                "local_request",
                return_value={"done": True, "response": json.dumps(sample())},
            ) as request,
        ):
            result = sd.run_structured_decision(
                "The ledger records 12 forms.",
                ["ceo", "cfo"],
                agents,
                "local",
                "http://localhost",
            )
            self.assertEqual(result["participants"], ["cfo", "ceo"])
            self.assertEqual(result["proposed_action_ids"], [])
            self.assertIn(
                "cfo canonical personality", request.call_args_list[0].args[2]["prompt"]
            )
            self.assertIsInstance(request.call_args_list[0].args[2]["format"], dict)


class StructuredDecisionApiTests(unittest.TestCase):
    def test_existing_authenticated_path_persists_readable_brief_and_contributions(
        self,
    ):
        from fastapi.testclient import TestClient
        from config import config
        from memory.database import init_db, get_decision_by_id, get_connection
        import main

        key = "sprint6-structured-synthetic-key"
        with (
            tempfile.TemporaryDirectory(
                dir=Path(tempfile.gettempdir()).resolve()
            ) as tmp,
            patch.object(config, "DATABASE_PATH", str(Path(tmp) / "test.db")),
            patch.object(config, "API_SECRET_KEY", key),
            patch("workflows.structured_decision.run_structured_decision") as run,
            patch.object(main, "send_notification"),
        ):
            init_db()
            result = {
                "final_decision": "Findings\nPrivate proposal.\nPending owner review.",
                "participants": ["cfo", "ceo"],
                "individual_outputs": {
                    "cfo": json.dumps(sample()),
                    "ceo": json.dumps(sample()),
                },
                "quality_warnings": {"structured_schema": sd.SCHEMA_VERSION},
            }
            run.return_value = result
            client = TestClient(main.app)
            data = {
                "topic": "Synthetic private decision",
                "task_description": "The ledger records 12 forms.",
                "output_mode": "structured",
                "agent_keys": ["cfo", "ceo"],
            }
            self.assertEqual(
                client.post("/decisions/trigger", json=data).status_code, 401
            )
            response = client.post(
                "/decisions/trigger", json=data, headers={"X-API-Key": key}
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn("no-store", response.headers["cache-control"])
            record = get_decision_by_id(response.json()["database_id"])
            self.assertEqual(record["decision_outcome"], result["final_decision"])
            self.assertEqual(record["approval_status"], "pending")
            with get_connection() as conn:
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM decision_contributions"
                    ).fetchone()[0],
                    2,
                )
            run.side_effect = RuntimeError("SECRET_MODEL_ERROR")
            response = client.post(
                "/decisions/trigger", json=data, headers={"X-API-Key": key}
            )
            self.assertEqual(response.status_code, 502)
            self.assertNotIn("SECRET_MODEL_ERROR", response.text)
            self.assertIn("no-store", response.headers["cache-control"])
            with get_connection() as conn:
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 1
                )
