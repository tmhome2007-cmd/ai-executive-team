"""Private Sprint 7 bytes expire; durable metadata and unrelated files survive."""

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from config import config
from memory.artifact_retention import prune_evaluation_samples


class Sprint7RetentionTests(unittest.TestCase):
    def test_expired_inputs_samples_and_assessments_leave_only_hash_receipts(self):
        with (
            tempfile.TemporaryDirectory(
                dir=Path(tempfile.gettempdir()).resolve()
            ) as tmp,
            patch.object(config, "WORKSPACE_ROOT", str(Path(tmp) / "workspace")),
        ):
            root = Path(tmp) / "audit-results"
            for label in ("schema", "intake", "delivery", "reasoning", "transfer"):
                run = root / ("sprint7-" + label) / ("run-" + "a" * 32)
                run.mkdir(parents=True, mode=0o700)
                for name in (
                    "freeze.json",
                    "cases.json",
                    "A_as_tested-1.json",
                    "B_replied-2-candidate.json",
                    "semantic-assessment.json",
                    "backend-tests.log",
                    "summary.json",
                    "protocol.json",
                    "owner-file.txt",
                ):
                    path = run / name
                    path.write_text(
                        json.dumps({"status": "error", "private": "PRIVATE CONTENT"})
                    )
                    os.utime(path, (10, 10))
                fresh = run / "C_silent-3.json"
                fresh.write_text("{}")
            self.assertEqual(prune_evaluation_samples(20), 30)
            self.assertEqual(prune_evaluation_samples(20), 0)
            for label in ("schema", "intake", "delivery", "reasoning", "transfer"):
                run = root / ("sprint7-" + label) / ("run-" + "a" * 32)
                self.assertFalse((run / "freeze.json").exists())
                receipt = json.loads(
                    (run / "A_as_tested-1.json.provenance.json").read_text()
                )
                self.assertEqual(receipt["status"], "error")
                self.assertNotIn("PRIVATE CONTENT", json.dumps(receipt))
                self.assertTrue(receipt["bytes_expired"])
                for name in (
                    "summary.json",
                    "protocol.json",
                    "owner-file.txt",
                    "C_silent-3.json",
                ):
                    self.assertTrue((run / name).exists())

    def test_links_unknown_directories_and_foreign_receipts_are_not_followed(self):
        with (
            tempfile.TemporaryDirectory(
                dir=Path(tempfile.gettempdir()).resolve()
            ) as tmp,
            patch.object(config, "WORKSPACE_ROOT", str(Path(tmp) / "workspace")),
        ):
            root = Path(tmp)
            container = root / "audit-results/sprint7-reasoning"
            container.mkdir(parents=True)
            outside = root / "owner"
            outside.mkdir()
            private = outside / "A_as_tested-1.json"
            private.write_text("owner data")
            os.utime(private, (10, 10))
            (container / ("run-" + "a" * 32)).symlink_to(
                outside, target_is_directory=True
            )
            run = container / ("run-" + "b" * 32)
            run.mkdir(mode=0o700)
            (run / "B_replied-1.json").symlink_to(private)
            path = run / "freeze.json"
            path.write_text("private input")
            os.utime(path, (10, 10))
            (run / "freeze.json.provenance.json").write_text("different receipt")
            unknown = container / "owner-not-a-run"
            unknown.mkdir()
            (unknown / "freeze.json").write_text("owner input")
            os.utime(unknown / "freeze.json", (10, 10))
            self.assertEqual(prune_evaluation_samples(20), 0)
            self.assertEqual(private.read_text(), "owner data")
            self.assertTrue(path.exists())
            self.assertTrue((unknown / "freeze.json").exists())
