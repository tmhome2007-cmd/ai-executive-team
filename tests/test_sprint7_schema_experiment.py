"""Ensure comparison runs cannot hide retries, drift or changed contact variants."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import sprint7_schema_experiment as experiment


class SchemaExperimentTests(unittest.TestCase):
    def test_contact_variants_replace_clarification_and_keep_constraints(self):
        with tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        ) as tmp:
            root = Path(tmp)
            source = root / "input.json"
            question = "FACTS\nExample.\nCLARIFICATION\nIdentity unknown.\nCONSTRAINTS\nZero spend."
            source.write_text(json.dumps({"question": question}))
            with (
                patch.object(experiment, "STORE", root),
                patch.object(experiment, "identity", return_value={"digest": "a" * 64}),
                patch.object(
                    experiment, "persona", return_value="Canonical test persona"
                ),
            ):
                directory = experiment.freeze(source)
            frozen = json.loads((directory / "freeze.json").read_text())
            cases = frozen["cases"]
            self.assertEqual(cases["A_as_tested"], question)
            self.assertIn("different people", cases["B_replied"])
            self.assertIn("same person", cases["C_silent"])
            for key in ("B_replied", "C_silent"):
                self.assertNotIn("Identity unknown.", cases[key])
                self.assertTrue(cases[key].endswith("CONSTRAINTS\nZero spend."))
            self.assertEqual(frozen["repairs"], 0)
            self.assertEqual((directory / "freeze.json").stat().st_mode & 0o777, 0o600)

    def test_source_drift_rejects_before_inference(self):
        with tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        ) as tmp:
            root = Path(tmp)
            run = root / "run-test"
            run.mkdir()
            (run / "freeze.json").write_text(
                json.dumps({"source_hashes": {}, "model": {}})
            )
            with (
                patch.object(experiment, "STORE", root),
                patch.object(experiment, "local_request") as transport,
            ):
                with self.assertRaisesRegex(ValueError, "source or model"):
                    experiment.run(run)
                transport.assert_not_called()
            self.assertFalse((run / "started.json").exists())

    def test_started_run_cannot_be_repeated_as_fresh(self):
        with tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        ) as tmp:
            root = Path(tmp)
            run = root / "run-test"
            run.mkdir()
            (run / "freeze.json").write_text(
                json.dumps({"source_hashes": experiment.hashes(), "model": {}})
            )
            (run / "started.json").write_text("{}")
            with (
                patch.object(experiment, "STORE", root),
                patch.object(experiment, "identity", return_value={}),
                patch.object(experiment, "local_request") as transport,
            ):
                with self.assertRaises(FileExistsError):
                    experiment.run(run)
                transport.assert_not_called()
