"""Opt-in local API generation using retained development inputs and disposable data."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid
from unittest.mock import patch


def run_check(root, source_run):
    from scripts.run_tests import disposable_environment

    with (
        disposable_environment() as temporary,
        patch("pathlib.Path.home", return_value=temporary / "test-home"),
    ):
        from config import config
        from fastapi.testclient import TestClient
        from memory.database import init_db, get_decision_by_id
        from memory.evidence import create_source, review_source
        from workflows.structured_decision import private_save
        import main

        old = json.loads((source_run / "freeze.json").read_text())["cases"]["C_silent"]
        directory = (
            root / "audit-results/sprint7-reasoning" / ("run-" + uuid.uuid4().hex)
        )
        init_db()
        ids = []
        for number, record in enumerate(old["intake"]["records"], 1):
            source = create_source(
                source_key=f"fictional-api-{number}",
                title="Historical fixture copy: " + record["title"][:170],
                reference="Retained fictional development record, never fetched",
                summary=(
                    "Historical fixture; no business facts reverified today. "
                    f"Original date label: {record['observed_at']}\n{record['summary']}"
                ),
                observed_at=datetime.now(timezone.utc).isoformat(),
                source_kind="document",
            )
            review_source(source["id"], source["version"], "owner_confirmed")
            ids.append(source["id"])
        value = {**old["input"], "source_ids": ids}
        client = TestClient(main.app, raise_server_exceptions=False)
        headers = {"X-API-Key": config.API_SECRET_KEY}
        preview_response = client.post("/decisions/intake", json=value, headers=headers)
        preview_response.raise_for_status()
        preview = preview_response.json()
        request = {
            "workflow_run_id": "decision:" + uuid.uuid4().hex,
            "topic": "Fictional first-user API regression",
            "task_description": preview["brief"],
            "source_ids": ids,
            "output_mode": "structured",
            "meeting_type": "strategy",
            "agent_keys": ["cso", "cfo", "ceo"],
            "intake_confirmation": {**value, "review_hash": preview["review_hash"]},
        }
        private_save(
            directory,
            "freeze.json",
            {
                "source_commit": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=root, text=True
                ).strip(),
                "script_sha256": hashlib.sha256(
                    Path(__file__).read_bytes()
                ).hexdigest(),
                "source_run": str(source_run),
                "model": config.OLLAMA_MODEL,
                "scope": "One real default-model API request plus saved-result replay if successful; fictional development data, not owner acceptance or held-out comparison. Registry observation is the fixture-copy registration time, not the original business-event date; original date label retained verbatim and no business facts reverified. Absent expiry stays unknown. Lifespan/scheduler omitted, notifications stubbed; framework home isolated. Existing structured path permits one repair per role; retain every raw attempt. No application default changed.",
            },
        )
        private_save(directory, "input.json", {"request": request, "preview": preview})
        started = time.monotonic()
        with patch.object(main, "send_notification") as notification:
            response = client.post("/decisions/trigger", json=request, headers=headers)
            data = response.json()
            replay = None
            if response.status_code == 200:
                saved = get_decision_by_id(data["database_id"])
                assert saved["approval_status"] == "pending"
                assert saved["decision_outcome"] == data["final_decision"]
                before = sorted(Path(config.WORKSPACE_ROOT).rglob("*.json"))
                repeated = client.post(
                    "/decisions/trigger", json=request, headers=headers
                )
                assert repeated.status_code == 200
                assert repeated.json()["database_id"] == data["database_id"]
                assert repeated.json()["final_decision"] == data["final_decision"]
                assert sorted(Path(config.WORKSPACE_ROOT).rglob("*.json")) == before
                assert notification.call_count == 1
                replay = "Saved HTTP200 result, no new artifact or notification"
            artifacts = {
                str(path.relative_to(config.WORKSPACE_ROOT)): json.loads(
                    path.read_text()
                )
                for path in Path(config.WORKSPACE_ROOT).rglob("*.json")
            }
            private_save(
                directory,
                "C_silent-1.json",
                {
                    "http_status": response.status_code,
                    "response": data,
                    "raw_artifacts": artifacts,
                    "replay": replay,
                    "seconds": round(time.monotonic() - started, 2),
                },
            )
        private_save(
            directory,
            "summary.json",
            {
                "http_status": response.status_code,
                "replay": replay,
                "raw_artifact_count": len(artifacts),
                "semantic_review": "pending",
                "owner_accepted": False,
                "merged": False,
            },
        )
        print(
            json.dumps(
                {
                    "report": str(directory),
                    "http_status": response.status_code,
                    "replay": replay,
                }
            ),
            flush=True,
        )
        return 0 if response.status_code == 200 else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-local", action="store_true")
    parser.add_argument("--source-run", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.run_local:
        parser.error("Explicit --run-local required; no application was initialized.")
    root = Path(__file__).resolve().parents[2]
    source = args.source_run.resolve()
    if (
        source.parent != root / "audit-results/sprint7-independent"
        or not source.name.startswith("run-")
    ):
        parser.error("Use a retained local independent development run.")
    sys.path.insert(0, str(root))
    return run_check(root, source)


if __name__ == "__main__":
    raise SystemExit(main())
