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
