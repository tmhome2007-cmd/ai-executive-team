"""Delivery experiment cannot silently retry or use drifted assets."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import sprint7_delivery_experiment as experiment


class DeliveryExperimentTests(unittest.TestCase):
    def test_drift_rejects_before_inference(self):
        with tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        ) as tmp:
            root = Path(tmp)
            directory = root / "run-test"
            directory.mkdir()
            (directory / "freeze.json").write_text(
                json.dumps({"source_hashes": {}, "model": {}})
            )
            with (
                patch.object(experiment, "STORE", root),
                patch.object(experiment, "local_request") as transport,
            ):
                with self.assertRaisesRegex(ValueError, "source or model"):
                    experiment.run(directory)
                transport.assert_not_called()
            self.assertFalse((directory / "started.json").exists())

    def test_started_run_rejects_duplicate_without_generation(self):
        with tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        ) as tmp:
            root = Path(tmp)
            directory = root / "run-test"
            directory.mkdir()
            (directory / "freeze.json").write_text(
                json.dumps({"source_hashes": experiment.hashes(), "model": {}})
            )
            (directory / "started.json").write_text("{}")
            with (
                patch.object(experiment, "STORE", root),
                patch.object(experiment, "identity", return_value={}),
                patch.object(experiment, "local_request") as transport,
            ):
                with self.assertRaises(FileExistsError):
                    experiment.run(directory)
                transport.assert_not_called()

    def test_explicit_model_change_is_frozen_without_changing_cases(self):
        with tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        ) as tmp:
            root = Path(tmp)
            prior = root / "prior"
            prior.mkdir()
            old = {
                "model": {"digest": "a" * 64, "configuration": {"tag": "llama3.1"}},
                "options": {"seed": 47},
                "persona": "Metadata persona",
                "cases": {"example": {"input": {"tool_status": "unknown"}}},
                "rubric": {"required": "usefulness"},
            }
            (prior / "freeze.json").write_text(json.dumps(old))
            selected = {"digest": "b" * 64, "configuration": {"tag": "llama3"}}
            with (
                patch.object(experiment, "STORE", root),
                patch.object(experiment, "identity", return_value=selected) as lookup,
            ):
                result = experiment.freeze(prior, "llama3")
                lookup.assert_called_once_with("llama3")
            frozen = json.loads((result / "freeze.json").read_text())
            self.assertEqual(frozen["cases"], old["cases"])
            self.assertEqual(frozen["options"], old["options"])
            self.assertEqual(frozen["model"], selected)
            self.assertEqual(frozen["baseline_model"], old["model"])
            self.assertEqual(frozen["comparison_kind"], "different-installed-model")
            self.assertEqual(frozen["repairs"], 0)
            self.assertFalse((result / "started.json").exists())

    def test_unavailable_selected_model_cannot_fallback_or_start(self):
        with tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        ) as tmp:
            root = Path(tmp)
            prior = root / "prior"
            prior.mkdir()
            (prior / "freeze.json").write_text(
                json.dumps({"model": {"configuration": {"tag": "llama3.1"}}})
            )
            with (
                patch.object(experiment, "STORE", root),
                patch.object(
                    experiment,
                    "identity",
                    side_effect=RuntimeError("Installed model unavailable"),
                ),
                patch.object(experiment, "local_request") as transport,
            ):
                with self.assertRaises(RuntimeError):
                    experiment.freeze(prior, "llama3")
                transport.assert_not_called()
            self.assertEqual(list(root.glob("run-*")), [])
