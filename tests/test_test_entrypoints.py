"""Test discovery and opt-in demos must not inherit company authority or initialize agents."""

import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from scripts import company_cli
from scripts.run_tests import disposable_environment

ROOT = Path(__file__).resolve().parents[1]


class TestEntrypointTests(unittest.TestCase):
    def test_launcher_dispatches_without_loading_owner_environment(self):
        with (
            patch.object(company_cli, "environment") as environment,
            patch.object(
                company_cli.subprocess, "run", return_value=Mock(returncode=0)
            ) as run,
        ):
            self.assertEqual(company_cli.main(["test", "--list"]), 0)
        environment.assert_not_called()
        self.assertEqual(
            run.call_args.args[0],
            [sys.executable, str(ROOT / "scripts/run_tests.py"), "--list"],
        )

    def test_disposable_settings_replace_and_restore_company_paths_and_credentials(
        self,
    ):
        private = {
            "DATABASE_PATH": "/synthetic-owner/company.db",
            "LOG_DIR": "/synthetic-owner/logs",
            "API_SECRET_KEY": "private-owner-sentinel",
            "TELEGRAM_BOT_TOKEN": "private-transport-sentinel",
            "RUN_DOCKER_INTEGRATION": "1",
            "ALLOW_REMOTE_LLM": "true",
        }
        with patch.dict(os.environ, private):
            with disposable_environment() as temp:
                self.assertTrue(Path(os.environ["DATABASE_PATH"]).is_relative_to(temp))
                self.assertTrue(Path(os.environ["LOG_DIR"]).is_relative_to(temp))
                self.assertNotEqual(
                    os.environ["API_SECRET_KEY"], private["API_SECRET_KEY"]
                )
                self.assertEqual(os.environ["TELEGRAM_BOT_TOKEN"], "")
                self.assertEqual(os.environ["ALLOW_REMOTE_LLM"], "false")
                self.assertEqual(os.environ["RUN_DOCKER_INTEGRATION"], "0")
            self.assertFalse(temp.exists())
            for name, value in private.items():
                self.assertEqual(os.environ[name], value)

    def test_manual_imports_and_help_do_not_import_application_or_model_packages(self):
        # A fresh process has no cached config/framework imports that could hide initialization.
        code = r"""
import importlib.abc, importlib.util, pathlib, sys
class BlockAppImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'config','agents','crewai','memory','notifications','tools','dotenv','privacy_bootstrap'}:
            raise AssertionError('Manual import initialized application: ' + fullname)
sys.meta_path.insert(0, BlockAppImports())
for index, path in enumerate(pathlib.Path('scripts/manual_checks').glob('test_*.py')):
    spec = importlib.util.spec_from_file_location('manual_check_' + str(index), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        module.main(['--help'])
    except SystemExit as error:
        assert error.code == 0
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_generation_demos_require_explicit_opt_in(self):
        for name in ["test_crew.py", "test_cso_tool.py"]:
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/manual_checks" / name)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("no application was initialized", result.stderr)

    def test_clean_copy_discovery_uses_only_tests_folder(self):
        # No .git, .env, databases, dependencies or manual scripts in the copied checkout.
        import shutil
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            copy = Path(raw)
            (copy / "scripts").mkdir()
            (copy / "tests").mkdir()
            shutil.copyfile(
                ROOT / "scripts/run_tests.py", copy / "scripts/run_tests.py"
            )
            (copy / "tests/test_isolated.py").write_text(
                "import os, unittest\n"
                'assert os.environ["API_SECRET_KEY"] != "PRIVATE-CLEAN-COPY-SENTINEL"\n'
                'assert os.environ["TELEGRAM_BOT_TOKEN"] == ""\n'
                "class Isolated(unittest.TestCase):\n"
                '    def test_discovery(self): self.fail("--list must not execute this test")\n'
            )
            (copy / "test_unsafe.py").write_text(
                'raise AssertionError("Root demo discovered")\n'
            )
            result = subprocess.run(
                [sys.executable, str(copy / "scripts/run_tests.py"), "--list"],
                cwd=copy,
                env={**os.environ, "API_SECRET_KEY": "PRIVATE-CLEAN-COPY-SENTINEL"},
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Discovered 1 cases; no tests executed.", result.stdout)
            self.assertNotIn(
                "PRIVATE-CLEAN-COPY-SENTINEL", result.stdout + result.stderr
            )
