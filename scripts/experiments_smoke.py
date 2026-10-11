"""Real experiment forms/API/storage checks; no running company API is contacted."""

from browser_navigation import open_view

import os
import datetime
from zoneinfo import ZoneInfo
import sys
import tempfile
from pathlib import Path

os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["CREWAI_TRACING_ENABLED"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import config
from memory.database import (
    init_db,
    propose_action,
    approve_action_with_treasury,
    claim_action_for_execution,
    update_action_status,
    get_action_by_id,
    get_connection,
)
from memory.experiments import list_experiments, update_experiment, list_observations
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory(prefix="experiment-browser-") as raw:
        config.DATABASE_PATH = str(Path(raw).resolve() / "experiments.db")
        config.API_SECRET_KEY = "synthetic-experiment-browser-key-1234567890"
        config.TELEGRAM_BOT_TOKEN = ""
        config.TELEGRAM_CHAT_ID = ""
        config.SANDBOX_MODE = True
        init_db()
        action = propose_action(
            "CTO",
            "Synthetic observation trial",
            "printf synthetic",
            expected_cost_amount=0,
            currency="EUR",
        )
        from main import app

        client = TestClient(app)
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            zone = ZoneInfo(
                os.environ.get("DASHBOARD_SMOKE_TIMEZONE", "Europe/Brussels")
            )
            page = browser.new_page(
                viewport={"width": 1440, "height": 1000}, timezone_id=str(zone)
            )
            page.set_default_timeout(10000)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def respond(route):
                request = route.request
                path = request.url.replace("http://127.0.0.1:8001", "")
                if request.method != "GET":
                    assert path.startswith(
                        "/experiments"
                    ), "Unexpected business mutation"
                response = client.request(
                    request.method,
                    path,
                    headers={
                        "X-API-Key": config.API_SECRET_KEY,
                        "Content-Type": "application/json",
                    },
                    content=request.post_data,
                )
                route.fulfill(
                    status=response.status_code,
                    content_type="application/json",
                    headers={
                        "Access-Control-Allow-Origin": os.environ.get(
                            "DASHBOARD_SMOKE_URL", "http://127.0.0.1:3000/"
                        ).rstrip("/")
                    },
                    body=response.content,
                )

            page.route("http://127.0.0.1:8001/**", respond)
            page.goto(os.environ.get("DASHBOARD_SMOKE_URL", "http://127.0.0.1:3000/"))
            page.get_by_placeholder("API Key").fill(config.API_SECRET_KEY)
            page.get_by_role("button", name="Confirm", exact=True).click()
            open_view(page, "Experiments")
            page.get_by_text("No experiments recorded yet.", exact=True).wait_for()
            page.get_by_role("button", name="New experiment", exact=True).click()
            for field, value in {
                "title": "Synthetic demand test",
                "action_id": str(action),
                "hypothesis": "Synthetic demand improves",
                "baseline_note": "Synthetic counter baseline = 10",
                "baseline_value": "10",
                "metric_name": "requests",
                "unit": "count",
                "target_value": "20",
                "expected_result": "At least twenty requests",
                "budget_amount": "0",
                "risk_limit": "0",
                "currency": "EUR",
                "observation_due_at": "2030-01-01T12:00",
            }.items():
                page.get_by_label("Experiment " + field, exact=True).fill(value)
            page.get_by_role("button", name="Save experiment", exact=True).click()
            page.get_by_text("Assessment: not live executed", exact=True).wait_for()
            plan = list_experiments()[0]
            expected_due = (
                datetime.datetime(2030, 1, 1, 12, tzinfo=zone)
                .astimezone(datetime.timezone.utc)
                .isoformat(timespec="microseconds")
                .replace("+00:00", "Z")
            )
            assert plan["observation_due_at"] == expected_due
            assert get_action_by_id(action)["status"] == "pending"
            with get_connection() as conn:
                assert (
                    conn.execute("SELECT COUNT(*) FROM treasury_entries").fetchone()[0]
                    == 0
                )
            page.get_by_role("button", name="Edit plan", exact=True).click()
            update_experiment(
                plan["id"], plan["version"], title="Concurrent experiment update"
            )
            page.get_by_label("Experiment title", exact=True).fill("Stale overwrite")
            page.get_by_role("button", name="Save experiment", exact=True).click()
            page.get_by_role("alert").filter(has_text="Experiment changed").wait_for()
            page.get_by_role("button", name="Refresh experiments", exact=True).click()
            page.get_by_text("Assessment: not live executed", exact=True).wait_for()

            # Test fixture changes state only; no executor/model/tool is invoked.
            approve_action_with_treasury(action)
            assert claim_action_for_execution(action)
            update_action_status(action, "executed_dry_run")
            observed = datetime.datetime(2026, 10, 10, 12, 0, 0, 100000, tzinfo=zone)
            with get_connection() as conn:
                conn.execute(
                    "UPDATE action_queue SET reviewed_at=? WHERE id=?",
                    (
                        (
                            observed.astimezone(datetime.timezone.utc)
                            - datetime.timedelta(microseconds=1)
                        ).isoformat(),
                        action,
                    ),
                )
                conn.commit()
            page.get_by_role("button", name="Refresh experiments", exact=True).click()
            page.get_by_text("Assessment: simulation only", exact=True).wait_for()
            page.get_by_label("Observation value", exact=True).fill("25")
            page.get_by_label("Observation evidence", exact=True).fill(
                "Synthetic counter result <script>alert(1)</script>"
            )
            # Preserve sub-second order after execution; HTML inputs canonicalize trailing zeros.
            precise = (
                observed.replace(tzinfo=None)
                .isoformat(timespec="milliseconds")
                .rstrip("0")
                .rstrip(".")
            )
            page.get_by_label("Observation observed_at", exact=True).fill(precise)
            page.get_by_role("button", name="Save observation", exact=True).click()
            page.get_by_text(
                "Evidence: Synthetic counter result <script>alert(1)</script>",
                exact=True,
            ).wait_for()
            assert len(list_observations(plan["id"])) == 1
            assert list_observations(plan["id"])[0][
                "observed_at"
            ] == observed.astimezone(datetime.timezone.utc).isoformat(
                timespec="microseconds"
            ).replace(
                "+00:00", "Z"
            )
            assert page.get_by_text(
                "Assessment: simulation only", exact=True
            ).is_visible()
            assert page.locator(".contribution script").count() == 0
            assert page.get_by_role("button", name="Edit plan", exact=True).count() == 0
            page.screenshot(path="/private/tmp/backend-experiments.png", full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert (
                page.evaluate(
                    "Object.keys(localStorage).length + Object.keys(sessionStorage).length"
                )
                == 0
            )
            assert not errors, errors
            browser.close()
            print(
                f"PASS ({zone}): fixed local/UTC calendar conversion, fractional observation ordering, experiment creation, stale-plan conflict, evidence-safe observation, simulation labelling, mobile width and no business execution/spending."
            )


if __name__ == "__main__":
    main()
