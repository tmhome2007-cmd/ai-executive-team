"""Opt-in real Docker confinement test. No mocks; CI pre-pulls Alpine."""

import os
import tempfile
import unittest

from workflows.container_executor import run_in_container


@unittest.skipUnless(
    os.environ.get("RUN_DOCKER_INTEGRATION") == "1",
    "requires explicit Docker integration opt-in",
)
class RealDockerBoundaryTests(unittest.TestCase):
    def test_real_worker_is_nonroot_offline_and_workspace_only(self):
        with (
            tempfile.TemporaryDirectory() as workspace,
            tempfile.TemporaryDirectory() as outside,
        ):
            secret_path = os.path.join(outside, "host-private.txt")
            with open(secret_path, "w", encoding="utf-8") as fh:
                fh.write("DO-NOT-EXPOSE-TO-AGENT")

            benign = run_in_container("id -u; pwd", workspace)
            self.assertEqual(benign.returncode, 0, benign.stderr)
            self.assertNotEqual(benign.stdout.splitlines()[0].strip(), "0")
            self.assertIn("/workspace", benign.stdout)

            # We must not see host paths outside the single workspace mount.
            outside_check = run_in_container(
                "test ! -e /host-private.txt && test ! -e /var/run/docker.sock",
                workspace,
            )
            self.assertEqual(outside_check.returncode, 0, outside_check.stderr)

            # Use the actual host sentinel path, including a mounted symlink,
            # to exercise attempted escape rather than only absent fixed paths.
            direct = run_in_container(f"cat '{secret_path}'", workspace)
            self.assertNotEqual(direct.returncode, 0)
            self.assertNotIn("DO-NOT-EXPOSE-TO-AGENT", direct.stdout)
            os.symlink(secret_path, os.path.join(workspace, "host-link"))
            through_link = run_in_container("cat /workspace/host-link", workspace)
            self.assertNotEqual(through_link.returncode, 0)
            self.assertNotIn("DO-NOT-EXPOSE-TO-AGENT", through_link.stdout)

            privileges = run_in_container(
                "grep '^NoNewPrivs:' /proc/self/status", workspace
            )
            self.assertEqual(privileges.returncode, 0)
            self.assertEqual(privileges.stdout.split()[-1], "1")

            # Network namespace must not allow any outbound TCP request.
            network = run_in_container(
                "wget -T 2 -q -O /dev/null http://1.1.1.1 2>/dev/null",
                workspace,
            )
            self.assertNotEqual(
                network.returncode, 0, "worker unexpectedly reached the internet"
            )

            # Container root filesystem must remain read-only.
            read_only = run_in_container(
                "touch /should-not-exist 2>/dev/null",
                workspace,
            )
            self.assertNotEqual(
                read_only.returncode, 0, "worker wrote outside the bind mount"
            )


if __name__ == "__main__":
    unittest.main()
