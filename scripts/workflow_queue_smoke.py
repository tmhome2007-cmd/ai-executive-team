"""Real Chromium owner controls against disposable SQLite; public reader is mocked."""

from browser_navigation import open_view

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    with tempfile.TemporaryDirectory(prefix="workflow-ui-") as raw:
        os.environ.update(
            CREWAI_STORAGE_DIR=raw + "/crewai",
            LOG_DIR=raw + "/logs",
            CREWAI_DISABLE_TELEMETRY="true",
            CREWAI_TRACING_ENABLED="false",
            TELEGRAM_BOT_TOKEN="",
            TELEGRAM_CHAT_ID="",
        )
        from tests.test_workflow_queue import WorkflowQueueTests
        from config import config
        from main import app
        from fastapi.testclient import TestClient
        from playwright.sync_api import sync_playwright
        from memory.research_queue import list_proposals
        from memory.business_discovery import list_briefs

        fixture = WorkflowQueueTests()
        fixture.setUp()
        try:
            with (
                patch.object(config, "API_SECRET_KEY", "workflow-browser-fixture-key"),
                patch(
                    "workflows.research_queue.fetch_public_source",
                    side_effect=fixture.payload,
                ) as fetch,
                sync_playwright() as runtime,
            ):
                client = TestClient(app)
                browser = runtime.chromium.launch()
                try:
                    page = browser.new_page(viewport={"width": 1440, "height": 1000})
                    page.set_default_timeout(30000)
                    errors = []
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    dashboard = os.environ.get(
                        "DASHBOARD_SMOKE_URL", "http://127.0.0.1:3002"
                    )
                    allowed = urlsplit(dashboard).netloc

                    def route(route):
                        req = route.request
                        p = urlsplit(req.url)
                        if p.netloc == "127.0.0.1:8001":
                            r = client.request(
                                req.method,
                                p.path + ("?" + p.query if p.query else ""),
                                headers={"X-API-Key": req.headers.get("x-api-key", "")},
                                json=req.post_data_json if req.post_data else None,
                            )
                            route.fulfill(
                                status=r.status_code,
                                headers=dict(r.headers),
                                body=r.content,
                            )
                        elif p.netloc == allowed:
                            route.continue_()
                        else:
                            errors.append("Unexpected network destination")
                            route.abort()

                    page.route("**/*", route)
                    page.goto(dashboard)
                    page.get_by_placeholder("API Key").fill(config.API_SECRET_KEY)
                    page.get_by_role("button", name="Confirm", exact=True).click()
                    open_view(page, "Business research")
                    panel = page.get_by_role(
                        "region", name="Workflow templates and research queue"
                    )
                    panel.get_by_label("Template review note", exact=True).fill(
                        "Browser review of inputs and gates"
                    )
                    panel.get_by_role(
                        "button", name="Review template for reuse", exact=True
                    ).click()
                    panel.get_by_role(
                        "button", name="Withdraw template version", exact=True
                    ).wait_for()
                    print("Template reviewed", flush=True)
                    panel.get_by_label("Proposed public URL", exact=True).fill(
                        "https://docs.python.org/3/"
                    )
                    panel.get_by_label("Research purpose", exact=True).fill(
                        "Synthetic browser source classification test"
                    )
                    panel.get_by_label(
                        "Category hypothesis", exact=False
                    ).select_option("buyer")
                    panel.get_by_role("button", name="Queue source", exact=True).click()
                    panel.get_by_text("Not an evidence record.", exact=True).wait_for()
                    assert fetch.call_count == 0
                    q = list_proposals()[0]
                    panel.get_by_role(
                        "button", name=f'Read queued public page #{q["id"]}', exact=True
                    ).click()
                    panel.get_by_text(
                        f"Fetched evidence record #{fixture.ids[-1]+1}.", exact=False
                    ).wait_for()
                    assert fetch.call_count == 1
                    page.get_by_label(
                        "Reviewed workflow template (optional)", exact=False
                    ).select_option("1")
                    page.get_by_text("Available evidence records", exact=False).click()
                    for ident in fixture.ids:
                        # Evidence labels include the fixture title and record number.
                        page.locator("label").filter(
                            has_text=f"#{ident} Fictional buyer fixture"
                        ).locator("input").check()
                    page.get_by_role(
                        "button", name="Save research brief", exact=True
                    ).click()
                    page.get_by_role(
                        "button", name="Compare options with local AI", exact=True
                    ).wait_for()
                    b = list_briefs()[0]
                    assert b["workflow_template"]["id"] == 1
                    assert b["state"] == "draft"
                    assert not b["attempts"]
                    page.set_viewport_size({"width": 390, "height": 844})
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth"
                    )
                    assert not errors, errors
                    print(
                        "PASS template review, queue without fetching, explicit read, immutable binding, no automatic approval and mobile layout"
                    )
                finally:
                    browser.close()
        finally:
            fixture.tearDown()


if __name__ == "__main__":
    main()
