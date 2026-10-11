"""Early production-browser checks with isolated data; no live backend or model calls."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid

from browser_navigation import SMOKE_FEATURES

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("features", nargs="*", metavar="FEATURE")
    parser.add_argument(
        "--all", action="store_true", help="Run all existing browser features"
    )
    args = parser.parse_args(argv)
    if any(feature not in SMOKE_FEATURES for feature in args.features):
        parser.error("Unknown feature; choose from: " + ", ".join(SMOKE_FEATURES))
    features = list(
        dict.fromkeys(
            SMOKE_FEATURES
            if args.all
            else args.features
            or ["dashboard_design", "runs", "experiments", "business_discovery"]
        )
    )
    report = ROOT / "audit-results" / ("be37-" + uuid.uuid4().hex)
    report.mkdir(mode=0o700, parents=True)
    results = []
    with tempfile.TemporaryDirectory(prefix="early-browser-") as raw:
        env = dict(os.environ)
        env.update(
            NEXT_PUBLIC_API_BASE="http://127.0.0.1:8001",
            NEXT_TELEMETRY_DISABLED="1",
            DATABASE_PATH=raw + "/disposable.db",
            LOG_DIR=raw + "/logs",
            CREWAI_STORAGE_DIR=raw + "/crewai",
            WORKSPACE_ROOT=raw + "/workspace",
            API_SECRET_KEY="synthetic-early-browser-key",
            OPENAI_API_KEY="ollama-local-test",
            BACKUP_ENCRYPTION_KEY="",
            SYNC_HMAC_KEY="",
            ACTION_APPROVAL_HMAC_KEY="",
            TELEGRAM_BOT_TOKEN="",
            TELEGRAM_CHAT_ID="",
            SANDBOX_MODE="true",
            ALLOW_REMOTE_LLM="false",
            ALLOW_UNSAFE_RAW_SHELL="false",
            CREWAI_DISABLE_TELEMETRY="true",
            CREWAI_TRACING_ENABLED="false",
            PYTHONDONTWRITEBYTECODE="1",
        )

        def run(name, command, cwd=ROOT, overrides=None):
            path = report / (name + ".log")
            with path.open("x") as log:
                path.chmod(0o600)
                try:
                    result = subprocess.run(
                        command,
                        cwd=cwd,
                        env={**env, **(overrides or {})},
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        timeout=180,
                    )
                    status = "PASS" if result.returncode == 0 else "FAIL"
                except subprocess.TimeoutExpired:
                    status = "TIMEOUT"
            results.append({"check": name, "status": status})
            print(name + ": " + status, flush=True)
            return status == "PASS"

        try:
            if not run(
                "production-build",
                ["npm", "run", "build", "--", "--webpack"],
                ROOT / "executive-dashboard",
            ):
                return 1
            with socket.socket() as reserved:
                reserved.bind(("127.0.0.1", 0))
                port = reserved.getsockname()[1]
            env["DASHBOARD_SMOKE_URL"] = f"http://127.0.0.1:{port}/"
            with (report / "server.log").open("x") as log:
                (report / "server.log").chmod(0o600)
                server = subprocess.Popen(
                    [
                        "npm",
                        "run",
                        "start",
                        "--",
                        "--hostname",
                        "127.0.0.1",
                        "--port",
                        str(port),
                    ],
                    cwd=ROOT / "executive-dashboard",
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                try:
                    opener = urllib.request.build_opener(
                        urllib.request.ProxyHandler({})
                    )
                    deadline = time.monotonic() + 30
                    ready = False
                    while time.monotonic() < deadline and server.poll() is None:
                        try:
                            with opener.open(
                                env["DASHBOARD_SMOKE_URL"], timeout=1
                            ) as response:
                                ready = response.status == 200
                            if ready:
                                break
                        except OSError:
                            time.sleep(0.2)
                    if not ready:
                        results.append({"check": "production-server", "status": "FAIL"})
                        return 1
                    for feature in features:
                        zones = (
                            ("UTC", "Europe/Brussels")
                            if feature == "experiments"
                            else (None,)
                        )
                        for zone in zones:
                            name = feature + (
                                "-" + zone.replace("/", "_") if zone else ""
                            )
                            run(
                                name,
                                [
                                    sys.executable,
                                    str(ROOT / "scripts" / (feature + "_smoke.py")),
                                ],
                                overrides=(
                                    {"DASHBOARD_SMOKE_TIMEZONE": zone} if zone else None
                                ),
                            )
                finally:
                    # Only this runner's server is stopped; existing company servers remain intact.
                    import signal

                    try:
                        os.killpg(server.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    try:
                        server.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(server.pid, signal.SIGKILL)
                        server.wait()
            return 0 if all(item["status"] == "PASS" for item in results) else 1
        finally:
            paths = [ROOT / "scripts" / (name + "_smoke.py") for name in features]
            paths += [
                ROOT / "scripts/browser_navigation.py",
                Path(__file__),
                ROOT / "memory/experiments.py",
            ]
            summary = {
                "checks": results,
                "implementation_commit": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
                ).strip(),
                "source_hashes": {
                    str(path.relative_to(ROOT)): hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
                    for path in paths
                },
                "scope": "Production dashboard, disposable SQLite/in-process APIs and synthetic public reads. Not the complete audit or owner usefulness acceptance.",
            }
            path = report / "results.json"
            path.write_text(json.dumps(summary, indent=2) + "\n")
            path.chmod(0o600)
            print("Report:", report, flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
