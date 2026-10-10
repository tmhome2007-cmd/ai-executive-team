"""Regression coverage for benchmark comparability, failures and private snapshots."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workflows.quality_benchmark import (
    assess,
    comparable,
    local_request,
    checker_identity,
)


class QualityBenchmarkTests(unittest.TestCase):
    def test_coverage_and_unknowns_are_separate(self):
        fixture = {
            "facts": "Interface unknown.",
            "required": ["create"],
            "unknown": "interface",
        }
        good = json.dumps(
            {
                "findings": ["Can create a task"],
                "unknowns": ["interface unknown"],
                "next_action": "Review privately",
            }
        )
        self.assertEqual(assess(good, fixture), [])
        self.assertTrue(assess(good.replace("create", "edit"), fixture))
        self.assertTrue(assess(good.replace("interface unknown", "no gaps"), fixture))
        self.assertTrue(assess("```json\n" + good + "\n```", fixture))
        self.assertTrue(
            assess(good.replace("Review privately", "Owner approved"), fixture)
        )

    def test_local_boundary_rejects_remote_and_credentials(self):
        for url in (
            "https://127.0.0.1:11434",
            "http://example.org",
            "http://127.0.0.1.evil.test",
            "http://user:pass@localhost",
            "http://localhost/path",
            "http://localhost?token=secret",
        ):
            with self.assertRaises(ValueError):
                local_request(url, "/api/tags")

    def test_changed_rubric_cannot_be_compared(self):
        run = {
            "dataset_hash": "a",
            "checker_hash": "b",
            "rubric_version": "v1",
            "summary": {"passed": 0, "denominator": 30},
            "prompt_hash": "p",
            "model": {"name": "m", "digest": "d"},
            "options": {},
        }
        self.assertFalse(comparable(run, run)["model_changed"])
        for key in ("dataset_hash", "checker_hash", "rubric_version"):
            with self.assertRaises(ValueError):
                comparable(run, dict(run, **{key: "changed"}))

    def test_runner_counts_transport_failures_and_saves_private_progress(self):
        spec = importlib.util.spec_from_file_location(
            "benchmark_script",
            Path(__file__).resolve().parents[1] / "scripts/quality_benchmark.py",
        )
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        from types import SimpleNamespace

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "docs/planning").mkdir(parents=True)
            fixtures = [
                {
                    "id": str(i),
                    "facts": "No evidence",
                    "required": [],
                    "unknown": "cause",
                }
                for i in range(10)
            ]
            (root / "docs/planning/quality-fixtures-v1.json").write_text(
                json.dumps(fixtures)
            )
            (root / "workflows").mkdir()
            (root / "workflows/output_quality.py").write_text("checker fixture")

            def respond(base, endpoint, payload=None):
                if endpoint == "/api/tags":
                    return {
                        "models": [{"name": "synthetic:latest", "digest": "synthetic"}]
                    }
                raise OSError("must not appear in reports: private credentials")

            with (
                patch.object(runner, "ROOT", root),
                patch.object(runner, "local_request", respond),
            ):
                self.assertEqual(
                    runner.run(
                        SimpleNamespace(
                            model="synthetic",
                            base_url="http://localhost",
                            prompt_version=None,
                        )
                    ),
                    1,
                )
            report = next((root / "quality-results").glob("*/report.json"))
            body = report.read_text()
            self.assertNotIn("private credentials", body)
            self.assertEqual(
                json.loads(body)["summary"],
                {
                    "passed": 0,
                    "failed": 0,
                    "errors": 30,
                    "incomplete": 0,
                    "denominator": 30,
                },
            )
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                runner.save(report, {})
            link = root / "linked"
            link.symlink_to(root / "quality-results", target_is_directory=True)
            with self.assertRaises(ValueError):
                runner.private_directory(link)

    def test_interruption_and_prompt_replay_preserve_prior_records(self):
        spec = importlib.util.spec_from_file_location(
            "benchmark_replay",
            Path(__file__).resolve().parents[1] / "scripts/quality_benchmark.py",
        )
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        from types import SimpleNamespace

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "docs/planning").mkdir(parents=True)
            fixtures = [
                {
                    "id": str(i),
                    "facts": "Draft exists",
                    "required": ["draft"],
                    "unknown": "cause",
                }
                for i in range(10)
            ]
            (root / "docs/planning/quality-fixtures-v1.json").write_text(
                json.dumps(fixtures)
            )
            (root / "workflows").mkdir()
            (root / "workflows/output_quality.py").write_text("fixture")

            def interrupt(base, endpoint, payload=None):
                if endpoint == "/api/tags":
                    return {"models": [{"name": "synthetic", "digest": "test"}]}
                raise KeyboardInterrupt

            args = SimpleNamespace(
                model="synthetic", base_url="http://localhost", prompt_version=None
            )
            with (
                patch.object(runner, "ROOT", root),
                patch.object(runner, "local_request", interrupt),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    runner.run(args)
            first = next((root / "quality-results").glob("*/report.json"))
            original = first.read_bytes()
            self.assertEqual(json.loads(original)["summary"]["incomplete"], 30)
            args.prompt_version = runner.digest(runner.PROMPT)

            def generate(base, endpoint, payload=None):
                if endpoint == "/api/tags":
                    return {"models": [{"name": "synthetic", "digest": "test"}]}
                self.assertTrue(payload["prompt"].startswith(runner.PROMPT))
                return {
                    "done": True,
                    "response": json.dumps(
                        {
                            "findings": ["draft exists"],
                            "unknowns": ["cause unknown"],
                            "next_action": "Review",
                        }
                    ),
                }

            with (
                patch.object(runner, "ROOT", root),
                patch.object(runner, "PROMPT", "new version"),
                patch.object(runner, "local_request", generate),
            ):
                # Replay must use the saved version even after the default changes.
                expected = json.loads(
                    (
                        root
                        / "quality-results/prompts"
                        / (args.prompt_version + ".json")
                    ).read_text()
                )["prompt"]

                def replay(base, endpoint, payload=None):
                    if payload:
                        self.assertTrue(payload["prompt"].startswith(expected))
                    if endpoint == "/api/tags":
                        return {"models": [{"name": "synthetic", "digest": "test"}]}
                    return {
                        "done": True,
                        "response": json.dumps(
                            {
                                "findings": ["draft exists"],
                                "unknowns": ["cause unknown"],
                                "next_action": "Review",
                            }
                        ),
                    }

                with patch.object(runner, "local_request", replay):
                    self.assertEqual(runner.run(args), 0)
            self.assertEqual(first.read_bytes(), original)
            with patch.object(runner, "ROOT", root):
                self.assertEqual(runner.recheck(first), 0)
            derived = [
                p
                for p in (root / "quality-results").glob("*/report.json")
                if "source_report_hash" in json.loads(p.read_text())
            ]
            self.assertEqual(len(derived), 1)
            self.assertEqual(
                json.loads(derived[0].read_text())["summary"]["incomplete"], 30
            )
            self.assertEqual(first.read_bytes(), original)
            invalid = json.loads(original)
            invalid["dataset_hash"] = "different"
            bad = root / "changed.json"
            bad.write_text(json.dumps(invalid))
            with patch.object(runner, "ROOT", root), self.assertRaises(ValueError):
                runner.recheck(bad)

    def test_prompt_changes_do_not_change_checker_identity(self):
        from workflows import quality_benchmark

        before = checker_identity()
        with patch.object(quality_benchmark, "PROMPT", "different prompt"):
            self.assertEqual(checker_identity(), before)
        with patch.object(quality_benchmark, "RUBRIC_VERSION", "different rubric"):
            self.assertNotEqual(checker_identity(), before)
