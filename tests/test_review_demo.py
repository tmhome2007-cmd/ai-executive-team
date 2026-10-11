"""Demo shutdown reaps only its children and clears only its own runtime record."""

import json
import os
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import Mock, patch
from scripts import review_demo as demo


class ReviewDemoTests(unittest.TestCase):
    def test_interrupt_and_failed_startup_clean_owned_resources_once(self):
        for failure in (SystemExit(), RuntimeError("Synthetic failure")):
            with (
                self.subTest(failure=type(failure).__name__),
                tempfile.TemporaryDirectory() as raw,
            ):
                root = Path(raw)
                (root / "audit-results").mkdir()
                runtime = root / "audit-results/owner-review-runtime.json"
                runtime.write_text(json.dumps({"pid": os.getpid()}))
                alive = Mock(pid=12345)
                alive.poll.return_value = None
                stopped = Mock(pid=54321)
                stopped.poll.return_value = 0
                reservation = Mock()

                def serve(root, children, reservations):
                    children.extend([alive, stopped])
                    reservations.append(reservation)
                    raise failure

                with (
                    patch.object(demo, "REPO", root),
                    patch.object(demo, "serve", side_effect=serve),
                    patch.object(demo.os, "killpg") as kill,
                ):
                    with self.assertRaises(type(failure)):
                        demo.launch_servers(root)
                kill.assert_called_once_with(12345, signal.SIGTERM)
                alive.wait.assert_called_once()
                stopped.wait.assert_called_once()
                reservation.close.assert_called_once()
                self.assertFalse(runtime.exists())

    def test_shutdown_preserves_another_demos_runtime_metadata(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "audit-results").mkdir()
            runtime = root / "audit-results/owner-review-runtime.json"
            other = {"pid": os.getpid() + 1}
            runtime.write_text(json.dumps(other))
            with patch.object(demo, "REPO", root), patch.object(demo, "serve"):
                demo.launch_servers(root)
            self.assertEqual(json.loads(runtime.read_text()), other)
