"""Real Chromium downloads and revision diff against a disposable owner API."""

import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    with tempfile.TemporaryDirectory(prefix="artifacts-ui-") as raw:
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
        from tests.test_practice_artifacts import ArtifactTests
        from memory.business_discovery import claim_stage, finish_stage
        from memory.practice_artifacts import download_artifact, list_artifacts
        from config import config
        from fastapi.testclient import TestClient
        from main import app
        from playwright.sync_api import sync_playwright

        fixture = ArtifactTests()
        fixture.setUp()
        try:
            b, first = fixture.saved()
            b = fixture.assess(b, [False, True])
            b = claim_stage(b["id"], b["version"], "revision")
            b = finish_stage(
                b["id"],
                "revision",
                "Revised fictional example. Missing details remain unknown.",
                b["version"],
            )
            second = b["attempts"][-1]["id"]
            with (
                patch.object(config, "API_SECRET_KEY", "artifact-browser-fixture-key"),
                sync_playwright() as runtime,
            ):
                client = TestClient(app)
                browser = runtime.chromium.launch()
                try:
                    page = browser.new_page(viewport={"width": 1440, "height": 1000})
                    page.set_default_timeout(15000)
                    errors = []
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    dashboard = os.environ.get(
                        "DASHBOARD_SMOKE_URL", "http://127.0.0.1:3002"
                    )
                    allowed = urlsplit(dashboard).netloc

                    def route(route):
                        req = route.request
                        parsed = urlsplit(req.url)
                        if parsed.netloc == "127.0.0.1:8001":
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
                    page.get_by_role("navigation", name="Company views").get_by_role(
                        "button", name="Business research", exact=True
                    ).click()
                    page.get_by_role(
                        "button",
                        name=f"#{b['id']} Private research · sample ready",
                        exact=True,
                    ).click()
                    panel = page.get_by_role(
                        "region", name="Private deliverable workspace"
                    )
                    panel.get_by_label("Sample to export").select_option(str(first))
                    panel.get_by_role(
                        "button", name="Export saved sample", exact=True
                    ).click()
                    panel.get_by_role(
                        "button", name="Download TXT sample 1", exact=True
                    ).wait_for()
                    panel.get_by_text(
                        "To compare revisions, export two different saved samples first.",
                        exact=False,
                    ).wait_for()
                    rows = list_artifacts(b["id"])
                    panel.get_by_label("Original artifact").select_option(
                        str(rows[0]["id"])
                    )
                    panel.get_by_label("Revised artifact").select_option(
                        str(rows[0]["id"])
                    )
                    assert panel.get_by_role(
                        "button", name="Compare files", exact=True
                    ).is_disabled()
                    with page.expect_download() as captured:
                        panel.get_by_role(
                            "button", name="Download TXT sample 1", exact=True
                        ).click()
                    downloaded = captured.value
                    assert (
                        downloaded.suggested_filename
                        == f"practice-{b['id']}-sample-1.txt"
                    )
                    rows = list_artifacts(b["id"])
                    assert (
                        Path(downloaded.path()).read_bytes()
                        == download_artifact(rows[0]["id"])[0]
                    )
                    panel.get_by_label("Sample to export").select_option(str(second))
                    panel.get_by_label("Artifact format").select_option("md")
                    panel.get_by_role(
                        "button", name="Export saved sample", exact=True
                    ).click()
                    panel.get_by_role(
                        "button", name="Download MD sample 2", exact=True
                    ).wait_for()
                    rows = list_artifacts(b["id"])
                    panel.get_by_text(
                        "Both fields select the same file.", exact=False
                    ).wait_for()
                    panel.get_by_label("Original artifact").select_option(
                        str(rows[0]["id"])
                    )
                    panel.get_by_label("Revised artifact").select_option(
                        str(rows[1]["id"])
                    )
                    panel.get_by_role(
                        "button", name="Compare files", exact=True
                    ).click()
                    panel.get_by_text(
                        "+Revised fictional example.", exact=False
                    ).wait_for()
                    page.set_viewport_size({"width": 390, "height": 844})
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth"
                    )
                    assert not errors, errors
                    print(
                        "PASS private authenticated download, exact bytes, two immutable versions, comparison and mobile layout"
                    )
                finally:
                    browser.close()
        finally:
            fixture.tearDown()


if __name__ == "__main__":
    main()
