"""Disposable SQLite/FastAPI/Chromium skill review and reuse; no live company API."""

import datetime
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
from types import SimpleNamespace
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    with tempfile.TemporaryDirectory(prefix="skills-ui-") as raw:
        temp = Path(raw).resolve()
        os.environ.update(
            CREWAI_STORAGE_DIR=str(temp / "crewai"),
            LOG_DIR=str(temp / "logs"),
            DATABASE_PATH=str(temp / "test.db"),
            TELEGRAM_BOT_TOKEN="",
            TELEGRAM_CHAT_ID="",
            CREWAI_DISABLE_TELEMETRY="true",
            CREWAI_TRACING_ENABLED="false",
            SANDBOX_MODE="true",
        )
        from config import config
        from tests.test_executive_skills import ExecutiveSkillsTests
        from memory.business_discovery import (
            create_brief,
            claim_stage,
            finish_stage,
            get_brief,
        )
        from memory.executive_skills import get_skill, list_skills
        from workflows.business_research_contract import render_research
        from fastapi.testclient import TestClient
        from playwright.sync_api import sync_playwright
        from main import app

        fixture = ExecutiveSkillsTests()
        fixture.setUp()
        try:
            review_ids = fixture.accepted_examples()
            fresh = create_brief(
                "Third fictional exercise",
                "Private only; no launch or spending",
                fixture.ids,
            )
            running = claim_stage(fresh["id"], fresh["version"], "research")
            fresh = finish_stage(
                fresh["id"],
                "research",
                render_research(fixture.payload(), running["research_sources"]),
                running["version"],
            )
            with (
                patch.object(config, "API_SECRET_KEY", "synthetic-skills-browser-key"),
                sync_playwright() as runtime,
            ):
                client = TestClient(app)
                browser = runtime.chromium.launch()
                try:
                    page = browser.new_page(viewport={"width": 1440, "height": 1000})
                    page.set_default_timeout(15000)
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    dashboard = os.environ.get(
                        "DASHBOARD_SMOKE_URL", "http://127.0.0.1:3002"
                    )
                    allowed = urlsplit(dashboard).netloc

                    def route(request):
                        req = request.request
                        parsed = urlsplit(req.url)
                        if parsed.netloc == "127.0.0.1:8001":
                            response = client.request(
                                req.method,
                                parsed.path
                                + ("?" + parsed.query if parsed.query else ""),
                                headers={"X-API-Key": req.headers.get("x-api-key", "")},
                                json=req.post_data_json if req.post_data else None,
                            )
                            request.fulfill(
                                status=response.status_code,
                                content_type="application/json",
                                body=response.content,
                            )
                        elif parsed.netloc == allowed:
                            request.continue_()
                        else:
                            errors.append("Unexpected network destination")
                            request.abort()

                    page.route("**/*", route)
                    page.goto(dashboard)
                    page.get_by_placeholder("API Key").fill(config.API_SECRET_KEY)
                    page.get_by_role("button", name="Confirm", exact=True).click()
                    page.get_by_role("navigation", name="Company views").get_by_role(
                        "button", name="Business research", exact=True
                    ).click()
                    page.get_by_role(
                        "navigation", name="Business research sections"
                    ).get_by_role("button", name="Executive skills", exact=True).click()
                    library = page.get_by_role("region", name="Executive skill library")
                    library.get_by_label("Skill key", exact=True).fill(
                        "private-summary"
                    )
                    library.get_by_label("Procedure name", exact=True).fill(
                        "Private evidence method"
                    )
                    for ident in review_ids:
                        library.get_by_label(f"Review #{ident} ·", exact=False).check()
                    method = "1. Preserve only supplied facts.\n2. Label missing evidence unknown.\n3. Request owner assessment of the private sample."
                    with patch(
                        "workflows.executive_skills._reason", return_value=method
                    ):
                        library.get_by_role(
                            "button",
                            name="Ask CSO to draft a proposed procedure",
                            exact=True,
                        ).click()
                        library.get_by_text(
                            "Private evidence method · version 1 · #1", exact=True
                        ).wait_for()
                    assert get_skill(1)["state"] == "proposed"
                    library.get_by_text(
                        "Procedure, prerequisites and exact rubric", exact=True
                    ).click()
                    library.get_by_text(method, exact=True).wait_for()
                    library.get_by_role(
                        "button",
                        name="Accept this private procedure version",
                        exact=True,
                    ).click()
                    library.get_by_text(
                        "accepted · available for compatible private exercises",
                        exact=True,
                    ).wait_for()
                    page.get_by_role(
                        "navigation", name="Business research sections"
                    ).get_by_role(
                        "button", name="Research & practice", exact=True
                    ).click()
                    page.get_by_role(
                        "button",
                        name=f"#{fresh['id']} Third fictional exercise · research ready",
                        exact=True,
                    ).click()
                    page.get_by_role(
                        "button", name="Refresh accepted procedures", exact=True
                    ).click()
                    page.get_by_label(
                        "Reusable private procedure (optional)", exact=True
                    ).select_option("1")
                    page.get_by_label("Audience", exact=True).fill("Owner")
                    page.get_by_label(
                        "Supplied facts and explicit unknowns", exact=True
                    ).fill(
                        "Fictional third case: one observation is recorded; reminder details remain unknown."
                    )
                    page.get_by_label("Chosen option", exact=True).fill(
                        "Private documentation"
                    )
                    page.get_by_label("Practice deliverable", exact=True).fill(
                        "Draft a private summary of these fictional facts and unknowns."
                    )
                    page.get_by_label("Review due (your local time)", exact=True).fill(
                        (datetime.datetime.now() + datetime.timedelta(days=1)).strftime(
                            "%Y-%m-%dT%H:%M"
                        )
                    )
                    page.get_by_role(
                        "button", name="Approve this practice plan only", exact=True
                    ).click()
                    page.get_by_text(
                        "Procedure: Private evidence method · version 1 · #1",
                        exact=True,
                    ).wait_for()
                    sample = "The fictional third case records one observation. Reminder details remain unknown. No cause is established, no messages were sent and no business action happened. Owner assessment of this private sample remains pending."
                    with (
                        patch(
                            "workflows.business_discovery._local_agent",
                            return_value=SimpleNamespace(
                                role="Fictional CSO",
                                backstory="Private test profile",
                                llm=SimpleNamespace(model="ollama/fictional"),
                            ),
                        ),
                        patch(
                            "workflows.business_discovery._reason", return_value=sample
                        ),
                    ):
                        page.get_by_role(
                            "button",
                            name="Generate private practice sample",
                            exact=True,
                        ).click()
                        page.get_by_text(
                            "Practice sample — AI self-checks are unverified",
                            exact=True,
                        ).wait_for()
                    assert get_brief(fresh["id"])["skill_version"]["id"] == 1
                    assert get_skill(1)["uses"][0]["owner_assessment"] == "not_assessed"
                    page.get_by_role(
                        "navigation", name="Business research sections"
                    ).get_by_role("button", name="Executive skills", exact=True).click()
                    library.get_by_role(
                        "button", name="Revoke version", exact=True
                    ).click()
                    library.get_by_text(
                        "revoked · Skill version revoked", exact=True
                    ).wait_for()
                    assert get_brief(fresh["id"])["sample"] == sample
                    assert len(list_skills()) == 1
                    page.set_viewport_size({"width": 390, "height": 844})
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth"
                    )
                    assert not errors, errors
                    print(
                        "PASS real browser: CSO proposal, separate owner acceptance, third-exercise reuse, preserved sample after revocation, mobile width and private API interception"
                    )
                finally:
                    browser.close()
        finally:
            fixture.tearDown()


if __name__ == "__main__":
    main()
