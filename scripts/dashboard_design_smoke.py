"""Visual and navigation regression check with disposable company records."""

from browser_navigation import open_business_section, open_view

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
        from playwright.sync_api import (
            sync_playwright,
            expect,
            TimeoutError as BrowserTimeout,
        )

        f = CompanyKnowledgeTests()
        f.setUp()
        try:
            _, _, action_id, _ = f.chain()
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
                    fail_actions = False

                    def route(route):
                        req = route.request
                        p = urlsplit(req.url)
                        if p.netloc == "127.0.0.1:8001":
                            assert req.method in {
                                "GET",
                                "OPTIONS",
                            }, "Visual review must not mutate company records"
                            if fail_actions and p.path == "/actions/history":
                                route.fulfill(
                                    status=503,
                                    content_type="application/json",
                                    body='{"detail":"Synthetic unavailable records"}',
                                )
                                return
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
                    open_view(page, "Virtual office")
                    room = page.get_by_role(
                        "region", name="3D executive floor", exact=True
                    )
                    room.get_by_text(
                        "Idle presentation — no executing action in loaded records",
                        exact=True,
                    ).wait_for()
                    room.get_by_label("Office camera angle", exact=True).fill("-45")
                    room.get_by_label("Office room zoom", exact=True).fill("75")
                    room.get_by_role("button", name="Reset camera", exact=True).click()
                    assert (
                        room.get_by_label(
                            "Office camera angle", exact=True
                        ).input_value()
                        == "-28"
                    )
                    page.screenshot(
                        path="/private/tmp/office-floor-desktop.png", full_page=True
                    )
                    page.emulate_media(reduced_motion="reduce")
                    room.get_by_role(
                        "button", name="Enable decorative movement", exact=True
                    ).wait_for()
                    expect(
                        room.get_by_role(
                            "button", name="Enable decorative movement", exact=True
                        )
                    ).to_be_disabled()
                    page.emulate_media(reduced_motion="no-preference")
                    expect(
                        room.get_by_role(
                            "button", name="Enable decorative movement", exact=True
                        )
                    ).to_be_enabled()
                    room.get_by_role(
                        "button", name="Enable decorative movement", exact=True
                    ).click()
                    expect(room.locator(".office-3d-person")).to_have_css(
                        "animation-play-state", "running"
                    )
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    expect(room.locator(".office-3d-person")).to_have_css(
                        "animation-play-state", "paused"
                    )
                    room.scroll_into_view_if_needed()
                    expect(room.locator(".office-3d-person")).to_have_css(
                        "animation-play-state", "running"
                    )
                    frame_gaps = page.evaluate(
                        """() => new Promise(resolve => { const gaps=[]; let previous; function frame(t) { if(previous !== undefined) gaps.push(t-previous); previous=t; if(gaps.length===60) resolve(gaps); else requestAnimationFrame(frame); } requestAnimationFrame(frame); })"""
                    )
                    ordered = sorted(frame_gaps)
                    print(
                        f"OFFICE local Chromium frame intervals: median {ordered[30]:.1f}ms, p95 {ordered[57]:.1f}ms; synthetic room only"
                    )
                    page.evaluate(
                        "Object.defineProperty(document, 'hidden', {configurable:true, value:true}); document.dispatchEvent(new Event('visibilitychange'))"
                    )
                    expect(room.locator(".office-3d-person")).to_have_css(
                        "animation-play-state", "paused"
                    )
                    page.evaluate(
                        "Object.defineProperty(document, 'hidden', {configurable:true, value:false}); document.dispatchEvent(new Event('visibilitychange'))"
                    )
                    from memory.database import get_connection

                    with get_connection() as connection:
                        connection.execute(
                            "UPDATE action_queue SET proposed_by='ceo', status='executing'"
                        )
                        connection.commit()
                    page.get_by_role(
                        "button", name="Refresh company data", exact=True
                    ).click()
                    room.get_by_text(
                        f"Recorded execution · Action #{action_id}", exact=True
                    ).wait_for()
                    fail_actions = True
                    page.get_by_role(
                        "button", name="Refresh company data", exact=True
                    ).click()
                    room.get_by_text(
                        "Unknown — records unavailable or stale", exact=True
                    ).wait_for()
                    fail_actions = False
                    with get_connection() as connection:
                        connection.execute(
                            "UPDATE action_queue SET proposed_by='cto', status='pending'"
                        )
                        connection.commit()
                    page.get_by_role(
                        "button", name="Refresh company data", exact=True
                    ).click()
                    room.get_by_text(
                        "Idle presentation — no executing action in loaded records",
                        exact=True,
                    ).wait_for()
                    page.set_viewport_size({"width": 390, "height": 844})
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= innerWidth"
                    )
                    page.screenshot(
                        path="/private/tmp/office-floor-mobile.png", full_page=True
                    )
                    bounds = room.locator(".office-3d-person").bounding_box()
                    viewport = room.locator(".office-3d-viewport").bounding_box()
                    assert (
                        bounds["x"] >= viewport["x"]
                        and bounds["x"] + bounds["width"]
                        <= viewport["x"] + viewport["width"]
                    )

                    room.get_by_role(
                        "button", name="Inspect CEO records", exact=True
                    ).click()
                    assert room.count() == 0
                    page.get_by_role(
                        "complementary", name="Executive inspector", exact=True
                    ).wait_for()
                    page.set_viewport_size({"width": 1440, "height": 1000})
                    names = [b.inner_text() for b in nav.get_by_role("button").all()]
                    open_view(page, "Overview")
                    page.evaluate("""() => {
                        window.navigationRegression = event => {
                            if (event.target.closest('button')?.textContent.trim() === 'Company knowledge') {
                                event.preventDefault(); event.stopImmediatePropagation();
                            }
                        };
                        document.querySelector('nav[aria-label="Company views"]').addEventListener('click', window.navigationRegression, true);
                    }""")
                    page.set_default_timeout(1000)
                    try:
                        open_view(page, "Company knowledge")
                    except BrowserTimeout:
                        print(
                            "PASS navigation check detects a deliberately blocked destination"
                        )
                    else:
                        raise AssertionError(
                            "Navigation regression escaped the destination check"
                        )
                    finally:
                        page.set_default_timeout(15000)
                        page.evaluate(
                            "document.querySelector('nav[aria-label=\"Company views\"]').removeEventListener('click', window.navigationRegression, true)"
                        )
                    open_view(page, "Company knowledge")
                    for name in names:
                        open_view(page, name)
                        page.get_by_role(
                            "heading", level=1, name=name, exact=True
                        ).wait_for()
                        assert page.evaluate(
                            "document.documentElement.scrollWidth <= window.innerWidth"
                        ), name
                    open_view(page, "Business research")
                    tabs = page.get_by_role(
                        "navigation", name="Business research sections", exact=True
                    )
                    page.get_by_label("Research title", exact=True).fill(
                        "Private draft retained while navigating"
                    )
                    open_business_section(page, "Executive skills")
                    page.get_by_role(
                        "region", name="Executive skill library", exact=True
                    ).wait_for()
                    assert not page.get_by_label(
                        "Research title", exact=True
                    ).is_visible()
                    open_business_section(page, "Run inspector")
                    page.get_by_role(
                        "region", name="Run inspector", exact=True
                    ).wait_for()
                    open_business_section(page, "Research & practice")
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
                    open_view(page, "Company knowledge")
                    assert (
                        page.get_by_label(
                            "Find a company view", exact=True
                        ).input_value()
                        == ""
                    )
                    page.set_viewport_size({"width": 390, "height": 844})
                    assert not nav.is_visible()
                    for name in names:
                        open_view(page, name)
                        assert (
                            not nav.is_visible()
                        ), "Mobile menu did not close after navigation"
                        assert page.evaluate(
                            "document.documentElement.scrollWidth <= innerWidth"
                        ), name
                    menu = page.get_by_role(
                        "button", name="Toggle company navigation", exact=True
                    )
                    menu.click()
                    assert nav.is_visible()
                    page.keyboard.press("Escape")
                    assert not nav.is_visible()
                    menu.click()
                    open_view(page, "Overview")
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
                        "PASS office camera, state snapshots, reduced motion, hidden/offscreen pause, mobile framing; all workspace destinations, overview loaded counts, retained practice draft, business tabs, view finder, live-mode confirmation cancellation, responsive navigation/Escape and no external traffic"
                    )
                finally:
                    browser.close()
        finally:
            f.tearDown()


if __name__ == "__main__":
    main()
