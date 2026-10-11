"""Private example runs preserve unsuccessful raw drafts and sanitize errors."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class PrivateExamplesTests(unittest.TestCase):
    def test_incomplete_generation_retains_raw_without_reviewable_claim(self):
        spec = importlib.util.spec_from_file_location(
            "private_examples", Path(__file__).resolve().parents[1]
            / "scripts/sprint5_private_examples.py",
        )
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            (root / "docs/planning").mkdir(parents=True)
            (root / "docs/planning/be35-examples.json").write_text(json.dumps([
                {"id": "example", "audience": "fictional", "facts": "none",
                 "request": "private draft", "checks": ["No invented facts"]}
            ]))

            def respond(base, endpoint, payload=None):
                if endpoint == "/api/tags":
                    return {"models": [{"name": "llama3.1:latest", "digest": "test"}]}
                return {"done": True, "done_reason": "length", "response": "unfinished"}

            with patch.object(runner, "ROOT", root), patch.object(runner, "local_request", respond):
                self.assertEqual(runner.main(), 1)
            directory = next((root / "quality-results").iterdir())
            self.assertEqual(json.loads((directory / "example-response.json").read_text())["response"], "unfinished")
            self.assertFalse((directory / "example-review.json").exists())
            self.assertEqual((directory / "example-response.json").stat().st_mode & 0o777, 0o600)

    def test_transport_error_does_not_expose_exception_contents(self):
        spec = importlib.util.spec_from_file_location(
            "private_examples_error", Path(__file__).resolve().parents[1]
            / "scripts/sprint5_private_examples.py",
        )
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            (root / "docs/planning").mkdir(parents=True)
            (root / "docs/planning/be35-examples.json").write_text(json.dumps([
                {"id": "example", "audience": "fictional", "facts": "none",
                 "request": "private draft", "checks": []}
            ]))

            def respond(base, endpoint, payload=None):
                if endpoint == "/api/tags":
                    return {"models": [{"name": "llama3.1:latest", "digest": "test"}]}
                raise OSError("private secret must not be retained")

            with patch.object(runner, "ROOT", root), patch.object(runner, "local_request", respond):
                self.assertEqual(runner.main(), 1)
            path = next((root / "quality-results").glob("*/example-error.json"))
            self.assertNotIn("private secret", path.read_text())


if __name__ == "__main__":
    unittest.main()
