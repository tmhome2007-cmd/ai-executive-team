"""Visual and navigation regression check with disposable company records."""

import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    with tempfile.TemporaryDirectory(prefix="design-ui-") as raw:
        os.environ.update(
            CREWAI_STORAGE_DIR=raw + "/crewai",
            LOG_DIR=raw + "/logs",
            CREWAI_DISABLE_TELEMETRY="true",
            CREWAI_TRACING_ENABLED="false",
            TELEGRAM_BOT_TOKEN="",
            TELEGRAM_CHAT_ID="",
        )
        from tests.test_company_knowledge import CompanyKnowledgeTests
        from config import config
        from main import app
        from fastapi.testclient import TestClient
        from playwright.sync_api import sync_playwright

        f = CompanyKnowledgeTests()
        f.setUp()
        try:
            f.chain()
            with (
                patch.object(config, "API_SECRET_KEY", "synthetic-design-key"),
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
                            }, "Visual review must not mutate company records"
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
                            errors.append("Unexpected external network request")
                            route.abort()

                    page.route("**/*", route)
                    page.goto(dashboard)
                    page.get_by_placeholder("API Key").fill(config.API_SECRET_KEY)
                    page.get_by_role("button", name="Confirm", exact=True).click()
                    nav = page.get_by_role(
                        "navigation", name="Company views", exact=True
                    )
                    page.get_by_text("Company pulse", exact=True).wait_for()
                    # Let fetched data replace loading placeholders before visual inspection.
                    page.get_by_role("button", name="Active goals", exact=False).filter(
                        has_text="1"
                    ).wait_for()
                    page.screenshot(
                        path="/private/tmp/dashboard-redesign-desktop.png",
                        full_page=True,
                    )
                    page.once("dialog", lambda d: d.dismiss())
                    page.get_by_role("button", name="Sandbox mode", exact=True).click()
                    assert page.get_by_role(
                        "button", name="Sandbox mode", exact=True
                    ).count()
                    names = [b.inner_text() for b in nav.get_by_role("button").all()]
                    for name in names:
                        nav.get_by_role("button", name=name, exact=True).click()
                        page.get_by_role(
                            "heading", level=1, name=name, exact=True
                        ).wait_for()
                        assert page.evaluate(
                            "document.documentElement.scrollWidth <= window.innerWidth"
                        ), name
                    nav.get_by_role(
                        "button", name="Business research", exact=True
                    ).click()
                    tabs = page.get_by_role(
                        "navigation", name="Business research sections", exact=True
                    )
                    page.get_by_label("Research title", exact=True).fill(
                        "Private draft retained while navigating"
                    )
                    tabs.get_by_role(
                        "button", name="Executive skills", exact=True
                    ).click()
                    page.get_by_role(
                        "region", name="Executive skill library", exact=True
                    ).wait_for()
                    assert not page.get_by_label(
                        "Research title", exact=True
                    ).is_visible()
                    tabs.get_by_role("button", name="Run inspector", exact=True).click()
                    page.get_by_role(
                        "region", name="Run inspector", exact=True
                    ).wait_for()
                    tabs.get_by_role(
                        "button", name="Research & practice", exact=True
                    ).click()
                    assert (
                        page.get_by_label("Research title", exact=True).input_value()
                        == "Private draft retained while navigating"
                    )
                    page.screenshot(
                        path="/private/tmp/dashboard-redesign-business.png",
                        full_page=True,
                    )
                    page.get_by_label("Find a company view", exact=True).fill(
                        "knowledge"
                    )
                    assert nav.get_by_role("button").count() == 1
                    nav.get_by_role(
                        "button", name="Company knowledge", exact=True
                    ).click()
                    assert (
                        page.get_by_label(
                            "Find a company view", exact=True
                        ).input_value()
                        == ""
                    )
                    page.set_viewport_size({"width": 390, "height": 844})
                    assert not nav.is_visible()
                    menu = page.get_by_role(
                        "button", name="Toggle company navigation", exact=True
                    )
                    menu.click()
                    assert nav.is_visible()
                    page.keyboard.press("Escape")
                    assert not nav.is_visible()
                    menu.click()
                    nav.get_by_role("button", name="Overview", exact=True).click()
                    assert not nav.is_visible()
                    page.get_by_role(
                        "heading", name="Overview", level=1, exact=True
                    ).wait_for()
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth"
                    )
                    page.screenshot(
                        path="/private/tmp/dashboard-redesign-mobile.png",
                        full_page=True,
                    )
                    assert not errors, errors
                    print(
                        "PASS all workspace destinations, overview loaded counts, retained practice draft, business tabs, view finder, live-mode confirmation cancellation, responsive navigation/Escape and no external traffic"
                    )
                finally:
                    browser.close()
        finally:
            f.tearDown()


if __name__ == "__main__":
    main()
