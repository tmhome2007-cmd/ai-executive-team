"""Run backend regressions with disposable paths and no inherited company credentials."""

import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def disposable_environment(*, docker=False):
    """Apply test settings before application imports; restore the calling environment."""
    previous = os.environ.copy()
    with tempfile.TemporaryDirectory(prefix="ai-executive-tests-") as raw:
        temp = Path(raw).resolve()
        os.environ.update(
            {
                "DATABASE_PATH": str(temp / "history.db"),
                "WORKSPACE_ROOT": str(temp / "workspace"),
                "LOG_DIR": str(temp / "logs"),
                "CREWAI_STORAGE_DIR": str(temp / "crewai"),
                "SYNC_EXPORT_DIR": str(temp / "sync"),
                "API_SECRET_KEY": "disposable-tests-key-1234567890",
                "ACTION_APPROVAL_HMAC_KEY": "disposable-tests-action-signing-key",
                "SYNC_HMAC_KEY": "disposable-tests-sync-key",
                "BACKUP_ENCRYPTION_KEY": "",
                "TELEGRAM_BOT_TOKEN": "",
                "TELEGRAM_CHAT_ID": "",
                "OPENAI_API_KEY": "ollama-local-test-placeholder",
                "SANDBOX_MODE": "true",
                "ALLOW_REMOTE_LLM": "false",
                "ALLOW_INSECURE_REMOTE_HTTP": "false",
                "BIND_HOST": "127.0.0.1",
                "ALLOW_UNSAFE_RAW_SHELL": "false",
                "TELEGRAM_ALLOW_REMOTE_CONTROL": "false",
                "TELEGRAM_INCLUDE_SENSITIVE_DETAILS": "false",
                "CREWAI_DISABLE_TELEMETRY": "true",
                "CREWAI_TRACING_ENABLED": "false",
                "OLLAMA_BASE_URL": "http://localhost:11434",
                "OLLAMA_MODEL": "llama3.1",
                "RUN_DOCKER_INTEGRATION": "1" if docker else "0",
            }
        )
        try:
            yield temp
        finally:
            os.environ.clear()
            os.environ.update(previous)


def iter_cases(suite):
    """Flatten discovered cases without executing them."""
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from iter_cases(item)
        else:
            yield item


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pattern", default="test_*.py", help="Filename pattern inside tests/."
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Discover and list cases without running them.",
    )
    parser.add_argument(
        "--docker",
        action="store_true",
        help="Include real Docker tests; requires the existing pinned image. Does not pull it.",
    )
    args = parser.parse_args(argv)
    if (
        "/" in args.pattern
        or "\\" in args.pattern
        or not args.pattern.startswith("test_")
        or not args.pattern.endswith(".py")
    ):
        parser.error("Use a test_*.py filename pattern inside tests/.")
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    with disposable_environment(docker=args.docker):
        loader = unittest.TestLoader()
        suite = loader.discover(str(ROOT / "tests"), pattern=args.pattern)
        if loader.errors:
            for error in loader.errors:
                print(error, file=sys.stderr)
            return 1
        if args.list:
            cases = list(iter_cases(suite))
            for case in cases:
                print(case.id())
            print(f"Discovered {len(cases)} cases; no tests executed.")
            return 0
        return (
            0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
        )


if __name__ == "__main__":
    raise SystemExit(main())
