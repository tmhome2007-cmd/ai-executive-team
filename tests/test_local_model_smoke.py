"""The final audit cannot implicitly pull a missing model or follow redirects."""

import contextlib
import io
import json
import unittest
from unittest.mock import Mock, patch
from scripts import local_model_smoke as smoke


class LocalModelSmokeTests(unittest.TestCase):
    def test_missing_identity_never_starts_generation(self):
        with (
            patch.object(
                smoke, "resolve_model", side_effect=RuntimeError("Unavailable")
            ),
            patch.object(smoke, "build_opener") as opener,
        ):
            with self.assertRaises(RuntimeError):
                smoke.greeting()
            opener.assert_not_called()

    def test_native_greeting_uses_only_resolved_tag_and_bounded_local_request(self):
        identity = {
            "digest": "a" * 64,
            "configuration": {"resolved_tag": "llama3.1:latest"},
        }
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps(
            {"done": True, "response": "Hello."}
        ).encode()
        with (
            patch.object(smoke, "resolve_model", return_value=identity),
            patch.object(smoke, "build_opener") as opener,
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            opener.return_value.open.return_value = response
            smoke.greeting()
        request = opener.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, "http://localhost:11434/api/generate")
        self.assertEqual(request.method, "POST")
        self.assertEqual(json.loads(request.data)["model"], "llama3.1:latest")
        self.assertEqual(opener.call_args.args[0].proxies, {})
        self.assertIsNone(
            opener.call_args.args[1].redirect_request(
                None, None, None, None, None, None
            )
        )
        self.assertEqual(response.read.call_args.args[0], 1024 * 1024 + 1)
        self.assertIn("Real local tool-free greeting", output.getvalue())
