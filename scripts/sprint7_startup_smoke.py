"""Exercise fresh setup/start/auth/intake on a tracked-source archive and empty data.

No clipboard writes, generation or scheduler jobs; occupied normal ports refuse
rather than disrupting existing apps. This is not owner/scheduler acceptance.
"""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    report = ROOT / "audit-results/be62-startup" / uuid.uuid4().hex
    report.mkdir(parents=True, mode=0o700)
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    results = {
        "commit": commit,
        "model_calls": 0,
        "clipboard_writes": 0,
        "scheduler": "omitted in isolated lifespan",
        "owner_accepted": False,
    }
    with tempfile.TemporaryDirectory(prefix="be62-normal-start-") as raw:
        temp = Path(raw).resolve()
        archive = temp / "source.tar"
        checkout = temp / "checkout"
        checkout.mkdir()
        subprocess.run(
            ["git", "archive", "-o", str(archive), "HEAD"], cwd=ROOT, check=True
        )
        with tarfile.open(archive) as source:
            source.extractall(checkout, filter="data")
        (checkout / ".venv").symlink_to(ROOT / ".venv", target_is_directory=True)
        (checkout / "executive-dashboard/node_modules").symlink_to(
            ROOT / "executive-dashboard/node_modules", target_is_directory=True
        )
        # Validate actual config/init_db, omit only scheduled/background jobs.
        with (checkout / "main.py").open("a") as handle:
            handle.write(
                """\nfrom contextlib import asynccontextmanager as _startup_context
@_startup_context
async def _isolated_startup(application):
    from config import validate_config
    from memory.database import init_db
    validate_config()
    init_db()
    yield
app.router.lifespan_context = _isolated_startup
"""
            )
        spec = importlib.util.spec_from_file_location(
            "isolated_company_cli", checkout / "scripts/company_cli.py"
        )
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        if not all(cli.available(port) for port in (8001, 3000)):
            raise RuntimeError(
                "Normal ports occupied; no existing app was stopped or reused"
            )
        private_names = {
            "API_SECRET_KEY",
            "ACTION_APPROVAL_HMAC_KEY",
            "SYNC_HMAC_KEY",
            "DATABASE_PATH",
            "WORKSPACE_ROOT",
            "LOG_DIR",
            "CREWAI_STORAGE_DIR",
            "SYNC_EXPORT_DIR",
            "BACKUP_ENCRYPTION_KEY",
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_CHAT_ID",
            "OPENAI_API_KEY",
            "OLLAMA_MODEL",
            "OLLAMA_BASE_URL",
        }
        clean = {k: v for k, v in os.environ.items() if k not in private_names}
        clean.update(
            CREWAI_STORAGE_DIR=str(temp / "crewai"),
            LOG_DIR=str(temp / "logs"),
            SYNC_EXPORT_DIR=str(temp / "sync"),
            NEXT_TELEMETRY_DISABLED="1",
            CREWAI_DISABLE_TELEMETRY="true",
            CREWAI_TRACING_ENABLED="false",
        )
        with patch.dict(os.environ, clean, clear=True):
            cli.init_local()
            env = cli.environment()
            results["env_mode"] = (checkout / ".env").stat().st_mode & 0o777
            assert results["env_mode"] == 0o600
            assert not (checkout / "memory/executive_team.db").exists()

            def verify_ready(environment):
                from urllib.request import Request, ProxyHandler, build_opener

                opener = build_opener(
                    ProxyHandler({}), cli.urllib.request.HTTPRedirectHandler()
                )
                try:
                    opener.open(
                        "http://127.0.0.1:8001/decisions/history?limit=20", timeout=5
                    )
                except cli.urllib.error.HTTPError as error:
                    assert error.code == 401
                else:
                    raise AssertionError("History must require authentication")
                headers = {"X-API-Key": environment["API_SECRET_KEY"]}
                with opener.open(
                    Request(
                        "http://127.0.0.1:8001/decisions/history?limit=20",
                        headers=headers,
                    ),
                    timeout=5,
                ) as response:
                    assert json.load(response) == []
                payload = json.dumps(
                    {"request": "Help me find the first real user for a fictional tool"}
                ).encode()
                with opener.open(
                    Request(
                        "http://127.0.0.1:8001/decisions/intake",
                        data=payload,
                        headers={**headers, "Content-Type": "application/json"},
                    ),
                    timeout=5,
                ) as response:
                    preview = json.load(response)
                    assert len(preview["questions"]) == 3 and not preview["confirmed"]
                with opener.open("http://127.0.0.1:3000/", timeout=5) as response:
                    assert response.status == 200
                    assert (
                        "http://127.0.0.1:8001"
                        in response.headers["Content-Security-Policy"]
                    )
                results.update(
                    auth=True,
                    empty_history=True,
                    stateless_intake=True,
                    production_ui=True,
                    status="PASS",
                )
                raise KeyboardInterrupt  # Normal launcher finally cleans only its children.

            with patch.object(cli, "copy_key", side_effect=verify_ready):
                try:
                    cli.start(env)
                except KeyboardInterrupt:
                    pass
            assert results.get("status") == "PASS"
        assert cli.available(8001) and cli.available(3000)
        results["owned_servers_stopped"] = True
    target = report / "summary.json"
    target.write_text(json.dumps(results, indent=2) + "\n")
    target.chmod(0o600)
    print(
        "PASS: explicit fresh setup, real local API auth/empty history/intake, production UI, owned-server cleanup; clipboard/scheduler/generation omitted"
    )
    print("Report:", report)


if __name__ == "__main__":
    main()
