"""Transfer inference cannot silently resume, retune or discard failed samples."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import sprint7_transfer_experiment as runner


class TransferExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Path(self.temp.name).resolve()
        self.model = {"configuration": {"tag": "local", "resolved_tag": "local"}}

    def frozen_run(self):
        directory = self.store / ("run-" + "a" * 32)
        runner.private_save(
            directory,
            "freeze.json",
            {
                "source_hashes": {"asset": "unchanged"},
                "options": dict(runner.delivery.OPTIONS),
                "models": {"baseline": self.model, "candidate": self.model},
                "cases": {
                    name: {
                        "input": {
                            "request": "Review privately",
                            "lead_status": "unknown",
                            "tool_status": "unknown",
                            "owner_minutes": 60,
                        },
                        "intake": {"brief": "Private review"},
                    }
                    for name in ("transfer-01", "transfer-02")
                },
            },
        )
        return directory

    def test_development_gate_and_reserved_hashes_block_before_model_lookup(self):
        reserved, development = self.store / "reserved", self.store / "development"
        development.mkdir()
        assessment = development / "semantic-assessment.json"
        assessment.write_text(json.dumps({"development_gate_passed": False}))
        with patch.object(runner, "identity") as identity:
            with self.assertRaisesRegex(ValueError, "development gate"):
                runner.freeze(reserved, development)
            identity.assert_not_called()
            assessment.write_text(json.dumps({"development_gate_passed": True}))
            source_hashes = runner.hashes()
            source_hashes["workflows/plan_delivery.py"] = "old passed code"
            (development / "freeze.json").write_text(
                json.dumps({"source_hashes": source_hashes})
            )
            (development / "summary.json").write_text(
                json.dumps(
                    {
                        "completed": 9,
                        "validated": 9,
                        "identity_unchanged": True,
                        "source_unchanged": True,
                    }
                )
            )
            with self.assertRaisesRegex(ValueError, "Current-code"):
                runner.freeze(reserved, development)
            identity.assert_not_called()
            (development / "freeze.json").write_text(
                json.dumps({"source_hashes": runner.hashes()})
            )
            reserved.mkdir()
            (reserved / "cases.json").write_text("{}")
            (reserved / "protocol.json").write_text("{}")
            (reserved / "manifest.json").write_text(
                json.dumps({"cases_sha256": "changed", "protocol_sha256": "changed"})
            )
            with self.assertRaisesRegex(ValueError, "drift"):
                runner.freeze(reserved, development)
            identity.assert_not_called()

    def test_source_drift_and_duplicate_start_never_request_inference(self):
        directory = self.frozen_run()
        with (
            patch.object(runner, "STORE", self.store),
            patch.object(runner, "hashes", return_value={"asset": "changed"}),
            patch.object(runner, "identity", return_value=self.model),
            patch.object(runner, "local_request") as request,
        ):
            with self.assertRaisesRegex(ValueError, "drift"):
                runner.run(directory)
            request.assert_not_called()
            self.assertFalse((directory / "started.json").exists())
        runner.private_save(directory, "started.json", {"prior_attempt": True})
        with (
            patch.object(runner, "STORE", self.store),
            patch.object(runner, "hashes", return_value={"asset": "unchanged"}),
            patch.object(runner, "identity", return_value=self.model),
            patch.object(runner, "local_request") as request,
        ):
            with self.assertRaises(FileExistsError):
                runner.run(directory)
            request.assert_not_called()

    def test_all_twelve_failures_retained_once_without_repair(self):
        directory = self.frozen_run()
        with (
            patch.object(runner, "STORE", self.store),
            patch.object(runner, "hashes", return_value={"asset": "unchanged"}),
            patch.object(runner, "identity", return_value=self.model),
            patch.object(runner.delivery, "evidence_sources", return_value={}),
            patch.object(runner.delivery, "preparation_payload", return_value={}),
            patch.object(
                runner.delivery, "validate_preparation", side_effect=ValueError
            ),
            patch.object(
                runner, "local_request", return_value={"done": True, "response": "bad"}
            ) as request,
        ):
            runner.run(directory)
        self.assertEqual(request.call_count, 12)
        summary = json.loads((directory / "summary.json").read_text())
        self.assertEqual(len(summary["samples"]), 12)
        self.assertTrue(summary["source_and_models_unchanged"])
        self.assertFalse(any(item["validated"] for item in summary["samples"]))
        for path in directory.glob("transfer-*.json"):
            slot = json.loads(path.read_text())
            self.assertEqual(slot["raw_stages"][0]["raw"], "bad")
            self.assertEqual(slot["error_type"], "ValueError")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
