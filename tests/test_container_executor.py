"""Unit tests for fail-closed Docker execution (never start a real container)."""
import os
from pathlib import Path
import subprocess
import socket
import tempfile
import unittest
from unittest.mock import patch

from workflows.container_executor import (
    ContainerExecutionError, ContainerTimeoutError, run_in_container, WORKER_IMAGE,
)


@unittest.skipUnless(hasattr(os, "getuid") and getattr(os, "getuid", lambda: 0)() != 0, "non-root Unix only")
class ContainerWorkerTests(unittest.TestCase):
    def test_docker_missing_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            with patch("workflows.container_executor.shutil.which", return_value=None):
                with self.assertRaises(ContainerExecutionError):
                    run_in_container("echo hello", root)

    def test_fixed_worker_limits_no_host_shell(self):
        with tempfile.TemporaryDirectory() as root:
            fake = subprocess.CompletedProcess(["docker"], 0, "ok", "")
            with patch("workflows.container_executor.shutil.which", return_value="/usr/bin/docker"), patch(
                "workflows.container_executor.subprocess.run", return_value=fake
            ) as mocked:
                result = run_in_container("echo hello", root)
                self.assertEqual(result.returncode, 0)
                args = mocked.call_args.args[0]
                self.assertEqual(args[0], "/usr/bin/docker")
                self.assertIn("--network=none", args)
                self.assertIn("--read-only", args)
                self.assertIn("--cap-drop=ALL", args)
                self.assertIn("--security-opt=no-new-privileges", args)
                self.assertIn("--pull=never", args)
                self.assertIn(WORKER_IMAGE, args)
                self.assertEqual(args[-3:], ["/bin/sh", "-c", "echo hello"])
                self.assertFalse(mocked.call_args.kwargs["shell"])
                self.assertNotIn("/var/run/docker.sock", " ".join(args))

    def test_output_cap_enforced(self):
        with tempfile.TemporaryDirectory() as root:
            fake = subprocess.CompletedProcess([], 0, "x" * 70000, "")
            with patch("workflows.container_executor.shutil.which", return_value="/usr/bin/docker"), patch(
                "workflows.container_executor.subprocess.run", return_value=fake
            ):
                with self.assertRaises(ContainerExecutionError):
                    run_in_container("echo hello", root)

    def test_timeout_forces_container_cleanup(self):
        with tempfile.TemporaryDirectory() as root:
            def execute(args, **kwargs):
                if args[1] == "run":
                    raise subprocess.TimeoutExpired(args, 30)
                return subprocess.CompletedProcess(args, 0, "", "")
            with patch("workflows.container_executor.shutil.which", return_value="/usr/bin/docker"), patch(
                "workflows.container_executor.subprocess.run", side_effect=execute
            ) as mocked:
                with self.assertRaises(ContainerTimeoutError):
                    run_in_container("echo safe", root)
                self.assertEqual(mocked.call_count, 2)
                original_args = mocked.call_args_list[0].args[0]
                cleanup_args = mocked.call_args_list[1].args[0]
                self.assertEqual(cleanup_args[:3], ["/usr/bin/docker", "rm", "-f"])
                self.assertEqual(cleanup_args[3], original_args[original_args.index("--name") + 1])

    def test_host_socket_in_workspace_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            sock = socket.socket(socket.AF_UNIX)
            try:
                sock.bind(str(Path(root) / "docker.sock"))
                with patch("workflows.container_executor.shutil.which", return_value="/usr/bin/docker"), patch(
                    "workflows.container_executor.subprocess.run"
                ) as invoked:
                    with self.assertRaises(ContainerExecutionError):
                        run_in_container("echo hello", root)
                    invoked.assert_not_called()
            finally:
                sock.close()

    def test_empty_command_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ContainerExecutionError):
                run_in_container(" ", root)


if __name__ == "__main__":
    unittest.main()
