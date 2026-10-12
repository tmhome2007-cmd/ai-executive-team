"""Short-report browser review on disposable records. No live model/company mutations."""

from browser_navigation import open_view

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import config
from memory.database import init_db, log_decision, get_decision_by_id
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright


def main():
    with (
        tempfile.TemporaryDirectory(prefix="short-review-browser-") as raw,
        patch.object(config, "DATABASE_PATH", str(Path(raw).resolve() / "company.db")),
        patch.object(config, "API_SECRET_KEY", "synthetic-short-review-key-1234567890"),
    ):
        init_db()
        cases = [
            (
                "Supplied evidence",
                "**Findings**\nSource #4 reports four checks passed.\n**Unknowns**\nCause unknown.\n**Next action**\nRead the failed check log.",
            ),
            (
                "Conflicting evidence",
                "**Findings**\nSource A reports four checks; source B reports three.\n**Unknowns**\nSources conflict.\n**Next action**\nResolve the conflict before any execution.",
            ),
            (
                "Missing prerequisites",
                "**Findings**\nReminder was not observed.\n**Unknowns**\nOriginal due time missing.\n**Next action**\nDo not run until due time is supplied.",
            ),
            (
                "Unstructured draft",
                "Legacy unstructured text <script>alert(1)</script>. The owner approved execution.",
            ),
        ]
        ids = []
        from workflows.structured_decision import Contribution, render_brief

        contribution = dict(
            facts=[
                dict(source_id="fixture", quote="The ledger has conflicting counts.")
            ],
            unknowns=["The correct count is unknown."],
            assumptions=[],
            recommendation="Compare the two records privately.",
            objections=["The original ledger may be unavailable."],
            success="One discrepancy recorded.",
            stop="Stop without the ledger.",
            pivotal_fact="Whether the original ledger is available.",
            next_owner_decision="Choose a private review.",
            effort_minutes=20,
        )
        cases.extend(
            [
                (
                    "Structured disagreement",
                    render_brief(
                        {
                            "cfo": Contribution(**contribution),
                            "ceo": Contribution(**{**contribution, "objections": []}),
                        }
                    ),
                ),
                (
                    "Incomplete structured draft",
                    "Findings\nRecommended proposal (CEO): Private review only.",
                ),
            ]
        )
        for title, text in cases:
            ids.append(
                log_decision(
                    title,
                    ["ceo"],
                    "Synthetic review fixture",
                    text,
                    individual_outputs={"ceo": text},
                )
            )
        from main import app

        client = TestClient(app)
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.set_default_timeout(15000)
            errors = []
            urls = []
            page.on("pageerror", lambda e: errors.append(str(e)))

            def respond(route):
                req = route.request
                urls.append(req.url)
                path = req.url.removeprefix("http://127.0.0.1:8001")
                assert req.method == "GET" or (
                    req.method == "POST"
                    and path in {"/decisions/intake", "/decisions/intake/confirm"}
                ), "Review allows only stateless intake; no generation or company mutation"
                response = client.request(
                    req.method,
                    path,
                    headers={
                        "X-API-Key": config.API_SECRET_KEY,
                        "Content-Type": "application/json",
                    },
                    content=req.post_data,
                )
                route.fulfill(
                    status=response.status_code,
                    content_type="application/json",
                    body=response.content,
                )

            page.route("http://127.0.0.1:8001/**", respond)
            page.goto(os.environ.get("DASHBOARD_SMOKE_URL", "http://127.0.0.1:3000/"))
            page.get_by_placeholder("API Key").fill(config.API_SECRET_KEY)
            page.get_by_role("button", name="Confirm", exact=True).click()
            nav = page.get_by_role("navigation", name="Company views")
            open_view(page, "Decisions")
            intake = page.get_by_role("region", name="First-user request intake")
            intake.get_by_placeholder(
                "Help me get the first real user for my tool"
            ).fill("Help me find a first real user for a fictional tool")
            intake.get_by_role("button", name="Clarify my request").click()
            intake.get_by_label("Intake brief preview").wait_for()
            assert intake.locator("select").count() == 3
            assert (
                "Available owner minutes this week: unknown"
                in intake.get_by_label("Intake brief preview").inner_text()
            )
            intake.get_by_label("Has your intended contact", exact=False).select_option(
                "recent_reply"
            )
            intake.get_by_label("Have you checked", exact=False).select_option(
                "working"
            )
            intake.get_by_label("How many minutes", exact=False).select_option("30")
            intake.get_by_role("button", name="Review brief with these answers").click()
            intake.get_by_text("After the tool check", exact=False).wait_for()
            intake.get_by_role(
                "button", name="Confirm brief and fill decision form"
            ).click()
            intake.get_by_role("status").wait_for()
            task = page.get_by_placeholder(
                "Provide a detailed explanation of the situation and question..."
            )
            assert "recently responsive contact" in task.input_value()
            intake.get_by_label("Has your intended contact", exact=False).select_option(
                "silent"
            )
            assert task.input_value() == ""
            intake.get_by_role("button", name="Review brief with these answers").click()
            intake.get_by_text(
                "Do not assume the silent contact", exact=False
            ).wait_for()
            intake.get_by_role(
                "button", name="Confirm brief and fill decision form"
            ).click()
            intake.get_by_role("status").wait_for()
            assert "different existing permitted conversation" in task.input_value()
            reports = page.locator(
                'section[aria-label="AI report short review"]:visible'
            )
            reports.first.wait_for()
            assert reports.count() == 4
            briefs = page.locator(
                'section[aria-label="Structured decision brief"]:visible'
            )
            assert briefs.count() == 2
            page.get_by_text(
                "CFO objection: The original ledger may be unavailable.", exact=True
            ).wait_for()
            briefs.get_by_text(
                "The brief is incomplete. Review the available text before making a decision.",
                exact=True,
            ).wait_for()
            page.get_by_label("Structured private brief", exact=False).check()
            page.get_by_text("Read the failed check log.", exact=True).wait_for()
            page.get_by_text("Original due time missing.", exact=True).wait_for()
            legacy = reports.filter(
                has_text="An AI report cannot establish owner approval."
            )
            assert (
                legacy.get_by_text("Legacy unstructured text", exact=False).count() == 1
            )
            assert not legacy.get_by_text(
                "Legacy unstructured text", exact=False
            ).is_visible()
            legacy.get_by_text(
                "An AI report cannot establish owner approval.", exact=False
            ).wait_for()
            for index in range(reports.count()):
                reports.nth(index).get_by_text(
                    "Full report and evidence details", exact=True
                ).click()
            legacy.get_by_text("Legacy unstructured text", exact=False).wait_for()
            assert page.locator("script").filter(has_text="alert(1)").count() == 0
            assert all(
                get_decision_by_id(ident)["approval_status"] == "pending"
                for ident in ids
            )
            page.set_viewport_size({"width": 390, "height": 844})
            page.screenshot(path="/private/tmp/short-review-mobile.png", full_page=True)
            assert page.evaluate(
                "document.documentElement.scrollWidth<=window.innerWidth+1"
            )
            assert page.evaluate("localStorage.length") == 0
            assert page.evaluate("sessionStorage.length") == 0
            assert all(config.API_SECRET_KEY not in u for u in urls)
            assert not errors, errors
            browser.close()
        print(
            "PASS: short-request intake/skip/changed-answer confirmation, evidence/unknown/next-action visibility, conflict and blocking warnings, legacy fallback/full report, no generation/approval mutation, mobile and text/key safety"
        )


if __name__ == "__main__":
    main()
