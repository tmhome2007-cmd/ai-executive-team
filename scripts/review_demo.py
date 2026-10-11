"""Disposable owner review of the current dashboard; no scheduler/model/network work."""

import contextvars
import json
import os
from pathlib import Path
import signal
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import ProxyHandler, build_opener

REPO = Path(__file__).resolve().parents[1]
KEY = "sprint5-review-demo-key-fictional-only"


def backend():
    sys.path.insert(0, str(REPO))
    from contextlib import asynccontextmanager
    from unittest.mock import patch
    from tests.test_local_model_identity import PrivateIdentityTests
    from memory.database import get_connection
    from config import config

    fixture = PrivateIdentityTests()
    fixture.setUp()
    config.API_SECRET_KEY = KEY
    titles = [
        "Can continue safely",
        "Model changed",
        "Model unavailable",
        "Older identity unknown",
    ]
    for title in titles:
        b = fixture.brief()
        with get_connection() as conn:
            conn.execute(
                "UPDATE business_discovery SET title=? WHERE id=?",
                ("FICTIONAL REVIEW: " + title, b["id"]),
            )
            conn.commit()
        run = fixture.interrupted(b)
        if title == titles[-1]:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE workflow_run_inspection SET model_digest=NULL,model_config_json=NULL WHERE id=?",
                    (run["id"],),
                )
                conn.commit()
    selected = contextvars.ContextVar("review_case", default=1)
    identity = {
        "digest": "a" * 64,
        "configuration": {"provider": "ollama", "tag": "synthetic", "temperature": 0.0},
    }

    def resolve(*args, **kwargs):
        if selected.get() == 3:
            raise RuntimeError(
                "Local model identity unavailable; restore the installed local model and retry. No model is downloaded."
            )
        return {**identity, "digest": "b" * 64 if selected.get() == 2 else "a" * 64}

    patch("workflows.local_model_identity.resolve_model", side_effect=resolve).start()
    patch(
        "workflows.business_discovery._reason",
        return_value="Fictional input A is the only supplied fact for this private summary. Missing outcome details remain unknown. No action has been taken; the owner must assess this sample separately.",
    ).start()
    import api.run_inspector as controls

    original = controls.continue_private_run

    def continuation(ident, *args, **kwargs):
        token = selected.set(ident)
        try:
            return original(ident, *args, **kwargs)
        finally:
            selected.reset(token)

    controls.continue_private_run = continuation
    from main import app

    @asynccontextmanager
    async def review_lifespan(app):
        yield  # Explicitly omit the company scheduler and startup reconciliation.

    app.router.lifespan_context = review_lifespan
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[os.environ["REVIEW_ORIGIN"]],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    from starlette.responses import JSONResponse

    @app.middleware("http")
    async def read_only_elsewhere(request, call_next):
        if request.method not in {
            "GET",
            "HEAD",
            "OPTIONS",
        } and request.url.path not in {
            "/runs/1/continue",
            "/runs/2/continue",
            "/runs/3/continue",
            "/runs/4/continue",
        }:
            return JSONResponse(
                {
                    "detail": "This fictional review allows only the four continuation examples."
                },
                status_code=403,
                headers={"Cache-Control": "no-store"},
            )
        return await call_next(request)

    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.environ["REVIEW_BACKEND_PORT"]),
        log_level="warning",
    )


def launcher():
    with tempfile.TemporaryDirectory(prefix="sprint5-owner-review-") as raw:
        launch_servers(Path(raw))


def launch_servers(root):
    children = []
    reservations = []
    try:
        serve(root, children, reservations)
    finally:
        for reservation in reservations:
            reservation.close()
        for child in children:
            if child.poll() is None:
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        runtime = REPO / "audit-results" / "owner-review-runtime.json"
        if (
            runtime.exists()
            and json.loads(runtime.read_text()).get("pid") == os.getpid()
        ):
            runtime.unlink()


def serve(root, children, reservations):
    root.chmod(0o700)
    (REPO / "audit-results").mkdir(mode=0o700, exist_ok=True)
    for _ in range(2):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        reservations.append(s)
    backend_port, frontend_port = [s.getsockname()[1] for s in reservations]
    env = {
        **os.environ,
        "DATABASE_PATH": str(root / "disposable.db"),
        "API_SECRET_KEY": KEY,
        "CREWAI_STORAGE_DIR": str(root / "crewai"),
        "LOG_DIR": str(root / "logs"),
        "WORKSPACE_ROOT": str(root / "workspace"),
        "NEXT_PUBLIC_API_BASE": f"http://127.0.0.1:{frontend_port}/review-api",
        "REVIEW_BACKEND_PORT": str(backend_port),
        "REVIEW_ORIGIN": f"http://127.0.0.1:{frontend_port}",
        "NEXT_TELEMETRY_DISABLED": "1",
        "CREWAI_DISABLE_TELEMETRY": "true",
        "CREWAI_TRACING_ENABLED": "false",
        "PYTHONDONTWRITEBYTECODE": "1",
        "OPENAI_API_KEY": "ollama-local-test",
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": "",
        "BACKUP_ENCRYPTION_KEY": "",
        "SYNC_HMAC_KEY": "",
        "ACTION_APPROVAL_HMAC_KEY": "",
        "SANDBOX_MODE": "true",
        "ALLOW_REMOTE_LLM": "false",
        "ALLOW_UNSAFE_RAW_SHELL": "false",
    }
    front = root / "executive-dashboard"
    shutil.copytree(
        REPO / "executive-dashboard",
        front,
        ignore=shutil.ignore_patterns("node_modules", ".next", ".env*", "*.log"),
    )
    (front / "node_modules").symlink_to(
        REPO / "executive-dashboard/node_modules", target_is_directory=True
    )
    layout = front / "app/layout.tsx"
    layout.write_text(
        layout.read_text().replace(
            "{children}</body>",
            '<div style={{padding:"12px", background:"#92400e", color:"white", fontWeight:700}}>FICTIONAL SPRINT 5 REVIEW · Run 1: can continue · Run 2: changed model · Run 3: unavailable model · Run 4: unknown old identity</div>{children}</body>',
        )
    )
    next_config = front / "next.config.ts"
    next_config.write_text(
        next_config.read_text().replace(
            "  poweredByHeader: false,",
            "  poweredByHeader: false,\n  async rewrites() { return [{source: '/review-api/:path*', destination: 'http://127.0.0.1:"
            + str(backend_port)
            + "/:path*'}]; },",
        )
    )
    logfile = root / "review.log"
    with logfile.open("w") as log:
        logfile.chmod(0o600)
        result = subprocess.run(
            ["npm", "run", "build", "--", "--webpack"],
            cwd=front,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        if result.returncode:
            retain_failure(logfile)
            for reservation in reservations:
                reservation.close()
            raise RuntimeError(
                "Demo build failed; inspect audit-results/owner-review-failure.log"
            )
        for s in reservations:
            s.close()
        children.append(
            subprocess.Popen(
                [str(REPO / ".venv/bin/python"), __file__, "backend"],
                cwd=REPO,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        )
        children.append(
            subprocess.Popen(
                [
                    "npm",
                    "run",
                    "start",
                    "--",
                    "--hostname",
                    "127.0.0.1",
                    "--port",
                    str(frontend_port),
                ],
                cwd=front,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        )

        def stop(*args):
            raise SystemExit()

        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)
        opener = build_opener(ProxyHandler({}))
        try:
            deadline = time.monotonic() + 45
            for url in [
                f"http://127.0.0.1:{backend_port}/runs",
                f"http://127.0.0.1:{frontend_port}",
            ]:
                ready = False
                while time.monotonic() < deadline:
                    if any(child.poll() is not None for child in children):
                        raise RuntimeError(f"Demo server failed; inspect {logfile}")
                    try:
                        from urllib.request import Request

                        with opener.open(
                            Request(url, headers={"X-API-Key": KEY}), timeout=1
                        ) as response:
                            ready = response.status == 200
                        if ready:
                            break
                    except OSError:
                        time.sleep(0.3)
                if not ready:
                    raise RuntimeError(f"Demo startup timed out; inspect {logfile}")
            state = {
                "url": f"http://127.0.0.1:{frontend_port}",
                "api": f"http://127.0.0.1:{backend_port}",
                "demo_key": KEY,
                "private_log": str(logfile),
                "pid": os.getpid(),
            }
            (REPO / "audit-results" / "owner-review-runtime.json").write_text(
                json.dumps(state)
            )
            (REPO / "audit-results" / "owner-review-runtime.json").chmod(0o600)
            print(json.dumps(state), flush=True)
            while all(child.poll() is None for child in children):
                time.sleep(1)
        except Exception:
            retain_failure(logfile)
            raise RuntimeError(
                "Demo startup failed; inspect audit-results/owner-review-failure.log"
            ) from None


def retain_failure(logfile):
    target = REPO / "audit-results" / "owner-review-failure.log"
    shutil.copyfile(logfile, target)
    target.chmod(0o600)


if __name__ == "__main__":
    backend() if len(sys.argv) > 1 else launcher()
