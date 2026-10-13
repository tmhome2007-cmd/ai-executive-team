"""Launcher safety: existing credentials/data/processes are never replaced."""

import contextlib
import io
import signal
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from scripts import company_cli as cli


class CompanyCliTests(unittest.TestCase):
    def test_review_commands_do_not_load_or_replace_company_credentials(self):
        for options in ([], ["--demo"], ["--check"]):
            with (
                self.subTest(options=options),
                patch.object(cli, "environment") as environment,
                patch.object(
                    cli.subprocess, "run", return_value=Mock(returncode=0)
                ) as run,
                contextlib.redirect_stdout(io.StringIO()) as output,
                patch.dict("os.environ", {"API_SECRET_KEY": "existing-private-key"}),
            ):
                self.assertEqual(cli.main(["review", *options]), 0)
                environment.assert_not_called()
                self.assertNotIn("existing-private-key", output.getvalue())
                if options == ["--demo"]:
                    self.assertEqual(
                        run.call_args.args[0][-1],
                        str(cli.ROOT / "scripts/review_demo.py"),
                    )
                elif options == ["--check"]:
                    self.assertIn(
                        "tests.test_sprint5_acceptance", run.call_args.args[0]
                    )
                    self.assertEqual(
                        run.call_args.kwargs["env"]["API_SECRET_KEY"],
                        "existing-private-key",
                    )
                else:
                    run.assert_not_called()
                    self.assertIn("exactly where to go", output.getvalue())

    def test_early_browser_dispatch_never_loads_company_environment(self):
        with (
            patch.object(cli, "environment") as environment,
            patch.object(cli.subprocess, "run", return_value=Mock(returncode=0)) as run,
        ):
            self.assertEqual(cli.main(["check-ui", "runs", "experiments"]), 0)
        environment.assert_not_called()
        self.assertEqual(run.call_args.args[0][-2:], ["runs", "experiments"])
        self.assertEqual(
            run.call_args.args[0][1], str(cli.ROOT / "scripts/feature_smoke.py")
        )

    def test_environment_preserves_existing_values_and_enforces_local_sandbox(self):
        with patch.dict(
            "os.environ",
            {
                "API_SECRET_KEY": "owner-secret",
                "DATABASE_PATH": "/existing/company.db",
                "SANDBOX_MODE": "false",
            },
            clear=True,
        ):
            env = cli.environment()
        self.assertEqual(env["API_SECRET_KEY"], "owner-secret")
        self.assertEqual(env["DATABASE_PATH"], "/existing/company.db")
        self.assertEqual(env["SANDBOX_MODE"], "true")
        self.assertEqual(env["ALLOW_REMOTE_LLM"], "false")
        self.assertEqual(env["TELEGRAM_BOT_TOKEN"], "")

    def test_ollama_probe_rejects_remote_credentials_redirect_paths_and_invalid_urls(
        self,
    ):
        for value in [
            "https://remote.example",
            "http://127.0.0.1@evil.example",
            "http://secret:password@localhost:11434",
            "http://localhost:11434/path",
            "http://localhost:11434/?api_key=private",
            "http://[invalid",
        ]:
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                cli.local_url(value)
        self.assertEqual(
            cli.local_url("http://127.0.0.1:11434/"), "http://127.0.0.1:11434"
        )

    def test_key_copy_never_prints_or_changes_key(self):
        env = {"API_SECRET_KEY": "existing-private-key-" + "x" * 32}
        output = io.StringIO()
        with (
            patch.object(cli.sys, "platform", "darwin"),
            patch.object(cli.shutil, "which", return_value="/usr/bin/pbcopy"),
            patch.object(cli.subprocess, "run") as run,
            contextlib.redirect_stdout(output),
        ):
            cli.copy_key(env)
        self.assertEqual(run.call_args.kwargs["input"], env["API_SECRET_KEY"])
        self.assertNotIn(env["API_SECRET_KEY"], output.getvalue())
        self.assertEqual(run.call_args.args[0], ["pbcopy"])

    def test_missing_key_is_not_generated_and_occupied_ports_are_not_killed(self):
        with self.assertRaises(RuntimeError):
            cli.copy_key({"API_SECRET_KEY": ""})
        with (
            patch.object(cli, "doctor", return_value=True),
            patch.object(cli, "available", return_value=False),
            patch.object(cli.subprocess, "Popen") as spawn,
            patch.object(cli.os, "killpg") as kill,
        ):
            with self.assertRaises(RuntimeError):
                cli.start({})
        spawn.assert_not_called()
        kill.assert_not_called()

    def test_cleanup_stops_only_children_it_created(self):
        alive = Mock(pid=12345)
        alive.poll.return_value = None
        stopped = Mock(pid=54321)
        stopped.poll.return_value = 0
        with patch.object(cli.os, "killpg") as kill:
            cli.stop_children([alive, stopped])
        kill.assert_called_once_with(12345, signal.SIGTERM)

    def test_probe_uses_no_proxy_and_disallows_redirects(self):
        with patch.object(cli.urllib.request, "build_opener") as opener:
            opener.return_value.open.side_effect = cli.urllib.error.HTTPError(
                "http://127.0.0.1/", 302, "Redirect", {}, None
            )
            self.assertFalse(cli.reachable("http://127.0.0.1/"))
        self.assertEqual(opener.call_args.args[0].proxies, {})
        self.assertIsNone(
            opener.call_args.args[1].redirect_request(
                None, None, None, None, None, None
            )
        )

    def test_start_readiness_interrupt_cleans_only_owned_servers(self):
        env = {"API_SECRET_KEY": "synthetic-key-" + "x" * 32}
        backend = Mock(pid=123)
        frontend = Mock(pid=456)
        backend.poll.return_value = None
        frontend.poll.return_value = None
        with (
            patch.object(cli, "doctor", return_value=True),
            patch.object(cli, "available", return_value=True),
            patch.object(cli.subprocess, "run"),
            patch.object(
                cli.subprocess, "Popen", side_effect=[backend, frontend]
            ) as spawn,
            patch.object(cli, "reachable", return_value=True),
            patch.object(cli, "copy_key"),
            patch.object(cli.time, "sleep", side_effect=KeyboardInterrupt),
            patch.object(cli, "stop_children") as stop,
        ):
            with self.assertRaises(KeyboardInterrupt):
                cli.start(env)
        self.assertEqual(spawn.call_count, 2)
        self.assertTrue(
            all(c.kwargs["start_new_session"] for c in spawn.call_args_list)
        )
        stop.assert_called_once_with([backend, frontend])

    def test_explicit_fresh_setup_is_private_and_does_not_inherit_or_print_keys(self):
        with tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        ) as tmp:
            root = Path(tmp)
            with (
                patch.object(cli, "ROOT", root),
                patch.dict(
                    "os.environ",
                    {"API_SECRET_KEY": "existing-parent-secret"},
                    clear=True,
                ),
                patch.object(cli, "environment") as environment,
                contextlib.redirect_stdout(io.StringIO()) as out,
            ):
                self.assertEqual(cli.main(["init-local"]), 0)
                environment.assert_not_called()
            from dotenv import dotenv_values

            values = dotenv_values(root / ".env")
            keys = [
                values[name]
                for name in [
                    "API_SECRET_KEY",
                    "SYNC_HMAC_KEY",
                    "ACTION_APPROVAL_HMAC_KEY",
                ]
            ]
            self.assertEqual(len(set(keys)), 3)
            self.assertTrue(all(len(k) == 64 for k in keys))
            self.assertTrue(all(k not in out.getvalue() for k in keys))
            self.assertNotIn("existing-parent-secret", (root / ".env").read_text())
            self.assertEqual((root / ".env").stat().st_mode & 0o777, 0o600)
            self.assertEqual(values["ALLOW_REMOTE_LLM"], "false")
            self.assertEqual(values["OLLAMA_MODEL"], "llama3.1")
            self.assertFalse((root / "memory").exists())

    def test_setup_refuses_existing_env_database_and_symlink_without_changes(self):
        for existing in [
            "env",
            "database",
            "symlink",
            "workspace",
            "inherited_database",
        ]:
            with (
                self.subTest(existing=existing),
                tempfile.TemporaryDirectory(
                    dir=Path(tempfile.gettempdir()).resolve()
                ) as tmp,
            ):
                root = Path(tmp)
                if existing == "env":
                    (root / ".env").write_text("API_SECRET_KEY=owner-kept-key")
                elif existing == "database":
                    (root / "memory").mkdir()
                    (root / "memory/executive_team.db").write_bytes(b"owner database")
                elif existing == "symlink":
                    (root / ".env").symlink_to(root / "absent-owner-env")
                elif existing == "workspace":
                    (root / "workspace").mkdir()
                    (root / "workspace/owner-report.txt").write_text("owner artifact")
                else:
                    (root / "another-company.db").write_bytes(b"owner database")
                with (
                    patch.object(cli, "ROOT", root),
                    patch.dict(
                        "os.environ",
                        (
                            {"DATABASE_PATH": "another-company.db"}
                            if existing == "inherited_database"
                            else {}
                        ),
                        clear=True,
                    ),
                    self.assertRaises(RuntimeError),
                ):
                    cli.init_local()
                if existing == "env":
                    self.assertEqual(
                        (root / ".env").read_text(), "API_SECRET_KEY=owner-kept-key"
                    )
                if existing == "database":
                    self.assertEqual(
                        (root / "memory/executive_team.db").read_bytes(),
                        b"owner database",
                    )
                    self.assertFalse((root / ".env").exists())
                if existing == "workspace":
                    self.assertEqual(
                        (root / "workspace/owner-report.txt").read_text(),
                        "owner artifact",
                    )
                    self.assertFalse((root / ".env").exists())
                if existing == "inherited_database":
                    self.assertEqual(
                        (root / "another-company.db").read_bytes(), b"owner database"
                    )
                    self.assertFalse((root / ".env").exists())
                if existing == "symlink":
                    self.assertTrue((root / ".env").is_symlink())
                    self.assertFalse((root / "absent-owner-env").exists())

    def test_setup_collision_never_overwrites_and_placeholder_key_is_not_copied(self):
        with tempfile.TemporaryDirectory(
            dir=Path(tempfile.gettempdir()).resolve()
        ) as tmp:
            with (
                patch.object(cli, "ROOT", Path(tmp)),
                patch.dict("os.environ", {}, clear=True),
                patch.object(cli.os, "open", side_effect=FileExistsError),
                self.assertRaises(RuntimeError),
            ):
                cli.init_local()
        self.assertFalse(
            cli.configured_key({"API_SECRET_KEY": "generate_with_openssl_rand_hex_32"})
        )
        with (
            patch.object(cli.subprocess, "run") as run,
            self.assertRaises(RuntimeError),
        ):
            cli.copy_key({"API_SECRET_KEY": "generate_with_openssl_rand_hex_32"})
        run.assert_not_called()
