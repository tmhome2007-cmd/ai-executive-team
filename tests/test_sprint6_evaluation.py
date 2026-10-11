"""Evaluation errors, partial slots and contamination are not hidden."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import sprint6_evaluation as evaluation


class Sprint6EvaluationTests(unittest.TestCase):
    def test_interruption_retains_manifest_and_blocks_fresh_held_out_claim(self):
        with tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        ) as tmp:
            root = Path(tmp)
            candidate = root / "candidate.json"
            candidate.write_text("{}")
            snapshot = {
                "identity": {"digest": "synthetic"},
                "protocol_hash": "synthetic",
                "persona": "canonical",
            }
            with (
                patch.object(evaluation, "ROOT", root),
                patch.object(evaluation, "STORE", root / "results"),
                patch.object(evaluation, "validate_candidate", return_value=snapshot),
                patch.object(
                    evaluation, "local_request", side_effect=KeyboardInterrupt
                ),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    evaluation.run(candidate, "held_out")
                manifest = next((root / "results").glob("held_out-*/manifest.json"))
                self.assertEqual(len(json.loads(manifest.read_text())["slots"]), 48)
                self.assertTrue(
                    all(
                        slot["status"] == "incomplete"
                        for slot in json.loads(manifest.read_text())["slots"]
                    )
                )
                with self.assertRaisesRegex(ValueError, "already accessed"):
                    evaluation.run(candidate, "held_out")

    def test_baseline_contract_rejects_extra_fields_and_empty_lists(self):
        good = {
            "findings": ["Supplied observation."],
            "unknowns": ["Cause unknown."],
            "next_action": "Review privately.",
        }
        evaluation.baseline_valid(json.dumps(good))
        for change in ({"extra": "unexpected"}, {"findings": []}, {"next_action": 123}):
            with self.assertRaises(ValueError):
                evaluation.baseline_valid(json.dumps({**good, **change}))

    def test_canonical_persona_can_be_read_without_running_agents(self):
        self.assertIn("Kai Akira", evaluation.persona())

    def test_generated_decision_retention_preserves_provenance_and_other_files(self):
        import os
        from config import config
        from memory.artifact_retention import prune_structured_decisions

        with (
            tempfile.TemporaryDirectory(
                dir=Path(tempfile.gettempdir()).resolve()
            ) as tmp,
            patch.object(config, "WORKSPACE_ROOT", tmp),
        ):
            run = (
                Path(tmp) / "structured-decisions/12345678-1234-1234-1234-123456789abc"
            )
            run.mkdir(parents=True, mode=0o700)
            for name in (
                "input.json",
                "ceo-1.json",
                "brief.json",
                "provenance.json",
                "owner-file.txt",
            ):
                path = run / name
                path.write_text("synthetic")
                os.utime(path, (10, 10))
            self.assertEqual(prune_structured_decisions(20), 3)
            self.assertTrue((run / "provenance.json").exists())
            self.assertTrue((run / "owner-file.txt").exists())
