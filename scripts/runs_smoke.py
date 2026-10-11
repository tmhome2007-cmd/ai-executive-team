"""Chromium stop/continue against disposable SQLite and a controlled local worker."""

from browser_navigation import open_business_section, open_view

import concurrent.futures
import os
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    with tempfile.TemporaryDirectory(prefix="runs-ui-") as raw:
        temp = Path(raw).resolve()
        os.environ.update(
            CREWAI_STORAGE_DIR=str(temp / "crewai"),
            LOG_DIR=str(temp / "logs"),
            TELEGRAM_BOT_TOKEN="",
            TELEGRAM_CHAT_ID="",
            CREWAI_DISABLE_TELEMETRY="true",
            CREWAI_TRACING_ENABLED="false",
            SANDBOX_MODE="true",
        )
        from tests.test_run_inspector import InspectorTests
        from memory.run_inspector import list_runs
        from memory.business_discovery import get_brief
        from workflows.business_discovery import run_stage
        from config import config
        from fastapi.testclient import TestClient
        from main import app
        from playwright.sync_api import sync_playwright

        fixture = InspectorTests()
        fixture.setUp()
        release = threading.Event()
        entered = threading.Event()
        calls = []
        text = "Fictional input A is the only supplied fact for this private summary. Missing outcome details remain unknown. No action has been taken; the owner must assess this sample separately."

        def reason(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                entered.set()
                release.wait(30)
            return text

        try:
            b = fixture.brief()
            with (
                patch.object(config, "API_SECRET_KEY", "run-browser-fixture-key"),
                patch("workflows.business_discovery._reason", side_effect=reason),
                concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool,
                sync_playwright() as runtime,
            ):
                worker = pool.submit(run_stage, b["id"], b["version"], "practice")
                assert entered.wait(10)
                ident = list_runs()["private_runs"][0]["id"]
                client = TestClient(app)
                browser = runtime.chromium.launch()
                try:
                    page = browser.new_page(viewport={"width": 1440, "height": 1000})
                    page.clock.install()
                    page.set_default_timeout(30000)
                    errors = []
                    run_reads = []
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    dashboard = os.environ.get(
                        "DASHBOARD_SMOKE_URL", "http://127.0.0.1:3002"
                    )
                    allowed = urlsplit(dashboard).netloc

                    def route(route):
                        req = route.request
                        parsed = urlsplit(req.url)
                        if parsed.netloc == "127.0.0.1:8001":
                            if parsed.path == "/runs" and req.method == "GET":
                                run_reads.append(req.url)
                            response = client.request(
                                req.method,
                                parsed.path
                                + ("?" + parsed.query if parsed.query else ""),
                                headers={"X-API-Key": req.headers.get("x-api-key", "")},
                                json=req.post_data_json if req.post_data else None,
                            )
                            route.fulfill(
                                status=response.status_code,
                                headers=dict(response.headers),
                                body=response.content,
                            )
                        elif parsed.netloc == allowed:
                            route.continue_()
                        else:
                            errors.append("Unexpected network destination")
                            route.abort()

                    page.route("**/*", route)
                    page.goto(dashboard)
                    page.get_by_placeholder("API Key").fill(config.API_SECRET_KEY)
                    page.get_by_role("button", name="Confirm", exact=True).click()
                    open_view(page, "Business research")
                    open_business_section(page, "Run inspector")
                    panel = page.get_by_role("region", name="Run inspector")
                    panel.get_by_text("Prompt and model versions", exact=True).click()
                    panel.get_by_text(
                        "Model digest: " + "a" * 64, exact=True
                    ).wait_for()
                    panel.get_by_text("Inference settings:", exact=False).wait_for()
                    panel.get_by_role(
                        "button", name=f"Stop private run #{ident}", exact=True
                    ).click()
                    panel.get_by_text(
                        "Wait for the current local model call to finish; its output will be discarded.",
                        exact=True,
                    ).wait_for()
                    assert not panel.get_by_role(
                        "button", name=f"Continue private run #{ident}", exact=True
                    ).count()
                    release.set()
                    try:
                        worker.result(timeout=15)
                    except RuntimeError:
                        pass
                    else:
                        raise AssertionError("Stopped worker published its result")
                    assert not get_brief(b["id"])["attempts"]
                    panel.get_by_role("button", name="Refresh runs", exact=True).click()
                    panel.get_by_role(
                        "button", name=f"Continue private run #{ident}", exact=True
                    ).click()
                    panel.get_by_text("Phase: completed", exact=False).wait_for()
                    assert len(get_brief(b["id"])["attempts"]) == 1
                    assert len(calls) == 2
                    open_business_section(page, "Research & practice")
                    reads_when_hidden = len(run_reads)
                    page.clock.fast_forward(16000)
                    page.wait_for_timeout(250)
                    assert (
                        len(run_reads) == reads_when_hidden
                    ), "Hidden run inspector kept polling"
                    open_business_section(page, "Run inspector")
                    panel.get_by_text("Phase: completed", exact=False).wait_for()
                    page.evaluate(
                        "Object.defineProperty(document, 'hidden', {configurable:true, value:true}); document.dispatchEvent(new Event('visibilitychange'))"
                    )
                    reads_when_document_hidden = len(run_reads)
                    page.clock.fast_forward(16000)
                    page.wait_for_timeout(250)
                    assert (
                        len(run_reads) == reads_when_document_hidden
                    ), "Hidden browser document kept polling"
                    page.evaluate(
                        "Object.defineProperty(document, 'hidden', {configurable:true, value:false}); document.dispatchEvent(new Event('visibilitychange'))"
                    )
                    with page.expect_request("**/runs?*"):
                        page.clock.fast_forward(16000)
                    # Re-entry loads current metadata without starting another generation.
                    assert len(get_brief(b["id"])["attempts"]) == 1
                    # Corrected source reviews invalidate a bound skill after interruption.
                    from tests.test_sprint5_recovery import RecoveryTests

                    recovery = RecoveryTests()
                    recovery.ids = (
                        fixture.ids
                    )  # Share this smoke's disposable database.
                    blocked_brief, _, _ = recovery.bound()
                    blocked = recovery.interrupted(blocked_brief)
                    recovery.assess(
                        recovery.examples[0], [False, True], correction=True
                    )
                    panel.get_by_role("button", name="Refresh runs", exact=True).click()
                    panel.get_by_text(
                        "Source assessments changed or skill acceptance is missing.",
                        exact=True,
                    ).wait_for()
                    panel.get_by_text(
                        "Next step: Propose and review a new skill version", exact=False
                    ).wait_for()
                    assert not panel.get_by_role(
                        "button",
                        name=f"Continue private run #{blocked['id']}",
                        exact=True,
                    ).count()
                    assert not get_brief(blocked_brief["id"])["attempts"]
                    assert len(calls) == 2
                    page.set_viewport_size({"width": 390, "height": 844})
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth"
                    )
                    assert not errors, errors
                    print(
                        "PASS run metadata, cooperative stop, blocked premature continuation, one continued sample and mobile layout"
                    )
                finally:
                    release.set()
                    browser.close()
        finally:
            release.set()
            fixture.tearDown()


if __name__ == "__main__":
    main()
