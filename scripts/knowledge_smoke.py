"""Chromium knowledge navigation over disposable history; no external traffic."""

import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    with tempfile.TemporaryDirectory(prefix="knowledge-ui-") as raw:
        os.environ.update(
            CREWAI_STORAGE_DIR=raw + "/crewai",
            LOG_DIR=raw + "/logs",
            CREWAI_DISABLE_TELEMETRY="true",
            CREWAI_TRACING_ENABLED="false",
            TELEGRAM_BOT_TOKEN="",
            TELEGRAM_CHAT_ID="",
        )
        from tests.test_company_knowledge import CompanyKnowledgeTests
        from memory.memory_reconciliation import reconcile_memory
        from config import config
        from main import app
        from fastapi.testclient import TestClient
        from playwright.sync_api import sync_playwright

        fixture = CompanyKnowledgeTests()
        fixture.setUp()
        try:
            goal, decision, action, old = fixture.chain()
            correction = reconcile_memory(
                old,
                expected_version=1,
                operation="correct",
                source_ids=[fixture.ids[0]],
                note="Synthetic browser correction",
                lesson="Corrected browser lesson",
            )
            new = correction["replacement_id"]
            with (
                patch.object(config, "API_SECRET_KEY", "knowledge-browser-fixture-key"),
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
                            assert req.method in {
                                "GET",
                                "OPTIONS",
                            }, "Knowledge browser test must remain read-only"
                            r = client.request(
                                req.method,
                                p.path + ("?" + p.query if p.query else ""),
                                headers={"X-API-Key": req.headers.get("x-api-key", "")},
                            )
                            route.fulfill(
                                status=r.status_code,
                                headers=dict(r.headers),
                                body=r.content,
                            )
                        elif p.netloc == allowed:
                            route.continue_()
                        else:
                            errors.append("Unexpected external request")
                            route.abort()

                    page.route("**/*", route)
                    page.goto(dashboard)
                    page.get_by_placeholder("API Key").fill(config.API_SECRET_KEY)
                    page.get_by_role("button", name="Confirm", exact=True).click()
                    page.get_by_role("navigation", name="Company views").get_by_role(
                        "button", name="Company knowledge", exact=True
                    ).click()
                    panel = page.get_by_role(
                        "region", name="Company knowledge", exact=True
                    )
                    panel.get_by_role(
                        "button", name=f"Inspect goal #{goal}", exact=True
                    ).click()
                    detail = panel.get_by_role("region", name="Knowledge record detail")
                    detail.get_by_role(
                        "button", name=f"Follow decision #{decision}", exact=True
                    ).click()
                    detail.get_by_role(
                        "button", name=f"Follow action #{action}", exact=True
                    ).click()
                    detail.get_by_role(
                        "button", name=f"Follow outcome #{action}", exact=True
                    ).click()
                    detail.get_by_role(
                        "heading", name="Expected private result", exact=True
                    ).wait_for()
                    detail.get_by_role(
                        "button", name="Back to previous record", exact=True
                    ).click()
                    detail.get_by_role(
                        "button", name=f"Follow lesson #{old}", exact=True
                    ).click()
                    detail.get_by_text(
                        "Current agent memory context: withheld", exact=False
                    ).first.wait_for()
                    detail.get_by_role(
                        "button", name=f"Follow lesson #{new}", exact=True
                    ).click()
                    detail.get_by_text(
                        "Current agent memory context: eligible as advisory context",
                        exact=False,
                    ).first.wait_for()
                    detail.get_by_role(
                        "button", name="Close record", exact=True
                    ).click()
                    panel.get_by_label("Record kind", exact=False).select_option(
                        "lesson"
                    )
                    panel.get_by_label("Memory visibility", exact=False).select_option(
                        "current"
                    )
                    panel.get_by_role(
                        "button", name=f"Inspect lesson #{new}", exact=True
                    ).wait_for()
                    assert not panel.get_by_role(
                        "button", name=f"Inspect lesson #{old}", exact=True
                    ).count()
                    panel.get_by_label(
                        "Search record titles and excerpts", exact=True
                    ).fill("' OR 1=1 --")
                    panel.get_by_role(
                        "button", name="Search knowledge", exact=True
                    ).click()
                    panel.get_by_text(
                        "No matching records on this page.", exact=True
                    ).wait_for()
                    page.set_viewport_size({"width": 390, "height": 844})
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth"
                    )
                    assert not errors, errors
                    print(
                        "PASS recorded goal/decision/action/outcome links, correction history, current-context exclusions, bound search, read-only requests and mobile layout"
                    )
                finally:
                    browser.close()
        finally:
            fixture.tearDown()


if __name__ == "__main__":
    main()
