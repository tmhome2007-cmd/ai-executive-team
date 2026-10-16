"""Freeze integrity and assessment-input isolation, without model calls."""

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.evaluation_protocol import ROOT, model_input, validate


class EvaluationProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "protocol"
        shutil.copytree(ROOT / "docs/evaluation/sprint6", self.directory)

    def rewrite(self, name, value):
        path = self.directory / name
        path.write_text(json.dumps(value))
        manifest_path = self.directory / "freeze.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))

    def test_frozen_inputs_validate_without_generation(self):
        result = validate(self.directory)
        self.assertEqual(len(result["splits"]["held_out"]), 8)
        self.assertEqual(result["scheduled_samples_per_variant_per_split"], 24)
        self.assertFalse(result["generation_performed"])

    def test_changed_case_prompt_rubric_or_checker_is_rejected(self):
        for name in (
            "development-cases.json",
            "held-out-cases.json",
            "baseline-prompt.txt",
            "rubric.json",
            "legacy-output-quality-v2.txt",
        ):
            with self.subTest(name=name):
                path = self.directory / name
                original = path.read_bytes()
                path.write_bytes(original + b"\n")
                with self.assertRaisesRegex(ValueError, "changed"):
                    validate(self.directory)
                path.write_bytes(original)

    def test_overlap_rejected_even_when_asset_hash_is_updated(self):
        cases = json.loads((self.directory / "held-out-cases.json").read_text())
        cases[0]["id"] = "dev-01"
        self.rewrite("held-out-cases.json", cases)
        with self.assertRaisesRegex(ValueError, "overlap"):
            validate(self.directory)

    def test_missing_evidence_and_duplicate_ids_rejected(self):
        path = self.directory / "development-cases.json"
        original = json.loads(path.read_text())
        cases = json.loads(json.dumps(original))
        cases[0]["evidence_contract"]["unknowns"] = []
        self.rewrite(path.name, cases)
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            validate(self.directory)
        cases = json.loads(json.dumps(original))
        cases[1]["id"] = cases[0]["id"]
        self.rewrite(path.name, cases)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate(self.directory)

    def test_manifest_cannot_read_arbitrary_paths_or_symlinks(self):
        path = self.directory / "freeze.json"
        original = json.loads(path.read_text())
        changed = json.loads(json.dumps(original))
        changed["files"]["../../private-input.json"] = "0" * 64
        path.write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, "Unexpected"):
            validate(self.directory)
        path.write_text(json.dumps(original))
        prompt = self.directory / "baseline-prompt.txt"
        other = self.directory / "other.txt"
        other.write_bytes(prompt.read_bytes())
        prompt.unlink()
        prompt.symlink_to(other)
        with self.assertRaisesRegex(ValueError, "Invalid"):
            validate(self.directory)

    def test_expected_answers_do_not_leak_into_model_input(self):
        case = json.loads((self.directory / "held-out-cases.json").read_text())[0]
        case["evidence_contract"]["must_not_claim"].append("SECRET_RUBRIC_MARKER")
        raw = model_input(case)
        self.assertNotIn("SECRET_RUBRIC_MARKER", raw)
        self.assertNotIn("evidence_contract", json.loads(raw))
        self.assertEqual(json.loads(raw)["sources"], case["sources"])


if __name__ == "__main__":
    unittest.main()
