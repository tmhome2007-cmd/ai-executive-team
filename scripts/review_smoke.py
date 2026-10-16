"""Short-report browser review on disposable records. No live model/company mutations."""

from browser_navigation import open_view

import os
import json
import hashlib
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
        from workflows.decision_intake import IntakeInput, build_intake

        fixture_intake = build_intake(
            IntakeInput(
                request="Find a first tester for a fictional tool",
                lead_status="recent_reply",
                tool_status="working",
                owner_minutes=30,
            ),
            lambda _: None,
        )
        cases.append(
            (
                "Checklist with separate executive proposal",
                fixture_intake["checklist"]
                + "\n\nExecutive proposals — generated separately\n\n"
                + render_brief(
                    {"ceo": Contribution(**{**contribution, "objections": []})}
                ),
            )
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
            trigger_mode = ["network"]
            trigger_attempts = []
            request_ids = []
            from memory import decision_requests

            page.on("pageerror", lambda e: errors.append(str(e)))

            def respond(route):
                req = route.request
                urls.append(req.url)
                path = req.url.removeprefix("http://127.0.0.1:8001")
                if req.method == "POST" and path == "/decisions/trigger":
                    trigger_attempts.append(trigger_mode[0])
                    body = json.loads(req.post_data)
                    request_ids.append(body["workflow_run_id"])
                    if trigger_mode[0] == "network":
                        route.abort("failed")
                    else:
                        # Simulate a claimed generation whose HTTP response was lost.
                        # No model runs: a synthetic saved result is inserted below.
                        decision_requests.claim(
                            body["workflow_run_id"],
                            hashlib.sha256(
                                json.dumps(
                                    {
                                        k: v
                                        for k, v in body.items()
                                        if k != "workflow_run_id"
                                    },
                                    sort_keys=True,
                                ).encode()
                            ).hexdigest(),
                        )
                        route.fulfill(
                            status=500,
                            content_type="text/plain",
                            body="Internal Server Error",
                        )
                    return  # Never reach the real generation handler or write a decision.
                assert req.method == "GET" or (
                    req.method == "POST"
                    and (
                        path in {"/decisions/intake", "/decisions/intake/confirm"}
                        or (
                            path.startswith("/decisions/requests/")
                            and path.endswith("/close")
                        )
                    )
                ), "Review permits intake and request recovery only; no generated meeting or action approval"
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
            intake.get_by_role("region", name="Your next step").wait_for()
            assert not intake.get_by_label("Intake brief preview").is_visible()
            intake.get_by_text(
                "Full context and instructions sent to the team", exact=True
            ).click()
            intake.get_by_label("Intake brief preview").wait_for()
            intake.get_by_text(
                "Practical owner checklist (application guidance)", exact=True
            ).click()
            assert intake.locator("select").count() == 3
            checklist = intake.get_by_label("Application owner checklist")
            assert "Time budget unknown" in checklist.inner_text()
            assert "1. Owner" in checklist.inner_text()
            assert "Draft message" not in checklist.inner_text()
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
            intake.get_by_role("region", name="Your next step").wait_for()
            assert (
                "Reuse a current working confirmation"
                in intake.get_by_label("Intake brief preview").text_content()
            )
            intake.get_by_text(
                "Practical owner checklist (application guidance)", exact=True
            ).click()
            assert "Draft message — NOT SENT" in checklist.inner_text()
            assert "never paste credentials" in checklist.inner_text()
            assert "Tool readiness: already confirmed by you" in checklist.inner_text()
            assert "Record today's owner confirmation" not in checklist.inner_text()
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
            intake.get_by_role("region", name="Your next step").wait_for()
            intake.get_by_text(
                "Practical owner checklist (application guidance)", exact=True
            ).click()
            assert (
                "Do not assume the silent contact"
                in intake.get_by_label("Intake brief preview").text_content()
            )
            assert "Draft message" not in checklist.inner_text()
            assert (
                "Do not assume the silent contact is uninterested"
                in checklist.inner_text()
            )
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
            assert briefs.count() == 3
            saved_checklist = briefs.filter(
                has_text="Application checklist — not an executive recommendation"
            )
            assert saved_checklist.count() == 1
            saved_checklist.get_by_role("region", name="Your next step").wait_for()
            saved_checklist.screenshot(
                path="/private/tmp/sprint7-compact-answer-desktop.png"
            )
            page.set_viewport_size({"width": 390, "height": 844})
            saved_checklist.screenshot(
                path="/private/tmp/sprint7-compact-answer-mobile.png"
            )
            assert page.evaluate(
                "document.documentElement.scrollWidth<=window.innerWidth+1"
            )
            page.set_viewport_size({"width": 1440, "height": 1000})
            assert not saved_checklist.get_by_text(
                "CEO proposal:", exact=False
            ).is_visible()
            assert not saved_checklist.get_by_text(
                "Draft message — NOT SENT", exact=False
            ).is_visible()
            saved_checklist.get_by_text(
                "Full application checklist and entered context", exact=True
            ).click()
            assert "Draft message — NOT SENT" in saved_checklist.inner_text()
            assert "1. Owner — 5 minutes" in saved_checklist.inner_text()
            for index in range(briefs.count()):
                briefs.nth(index).get_by_text(
                    "AI proposals, objections and evidence — unverified", exact=True
                ).click()
            assert "CEO proposal:" in saved_checklist.inner_text()
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
            for failure in ("network", "server"):
                trigger_mode[0] = failure
                page.get_by_placeholder("E.g. Expansion into the German market").fill(
                    "Fictional connection recovery"
                )
                page.get_by_placeholder(
                    "Provide a detailed explanation of the situation and question..."
                ).fill(
                    "Private fictional connection-recovery test. No real meeting or contact."
                )
                page.get_by_role("button", name="Start Decision", exact=True).click()
                recovery = page.get_by_role("status", name="Decision request recovery")
                recovery.wait_for()
                recovery.get_by_text(
                    "An empty history is not proof", exact=False
                ).wait_for()
                attempts = len(trigger_attempts)
                with page.expect_request(
                    lambda r: "/decisions/history" in r.url and r.method == "GET"
                ):
                    recovery.get_by_role(
                        "button", name="Refresh Decision History"
                    ).click()
                self_report = page.get_by_role(
                    "heading", name="Decision History", exact=True
                )
                self_report.wait_for()
                assert len(trigger_attempts) == attempts
                assert all(
                    get_decision_by_id(ident)["approval_status"] == "pending"
                    for ident in ids
                )
                assert page.get_by_role(
                    "button", name="Start Decision", exact=True
                ).is_disabled()
                recovery.get_by_role("button", name="Check Request Status").click()
                if failure == "network":
                    recovery.get_by_text(
                        "Delivery may still be pending", exact=False
                    ).wait_for()
                    page.reload()
                    page.get_by_placeholder("API Key").fill(config.API_SECRET_KEY)
                    page.get_by_role("button", name="Confirm", exact=True).click()
                    open_view(page, "Decisions")
                    recovery = page.get_by_role(
                        "status", name="Decision request recovery"
                    )
                    recovery.wait_for()
                    assert len(trigger_attempts) == attempts
                    assert page.get_by_role(
                        "button", name="Start Decision", exact=True
                    ).is_disabled()
                    recovery.get_by_role("button", name="Close Recovery").click()
                    recovery.wait_for(state="hidden")
                    assert (
                        decision_requests.inspect(request_ids[-1])["status"] == "closed"
                    )
                else:
                    recovery.get_by_text(
                        "The meeting is queued or running", exact=False
                    ).wait_for()
                    recovery.get_by_role("button", name="Close Recovery").click()
                    recovery.get_by_text(
                        "This request cannot be closed yet", exact=False
                    ).wait_for()
                    assert page.get_by_role(
                        "button", name="Start Decision", exact=True
                    ).is_disabled()
                    saved = log_decision(
                        "Synthetic saved recovery",
                        ["ceo"],
                        "Fictional request only",
                        "Private synthetic result. Pending owner review.",
                        workflow_key=request_ids[-1],
                    )
                    decision_requests.finish(request_ids[-1], decision_id=saved)
                    recovery.get_by_role("button", name="Check Request Status").click()
                    recovery.get_by_text(
                        f"Saved as decision #{saved}", exact=False
                    ).wait_for()
                    assert get_decision_by_id(saved)["approval_status"] == "pending"
                    recovery.get_by_role("button", name="Close Recovery").click()
                    recovery.wait_for(state="hidden")
                assert len(trigger_attempts) == attempts
            assert trigger_attempts == ["network", "server"]
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
            "PASS: short-request intake/skip/changed-answer confirmation, evidence/unknown/next-action visibility, conflict and blocking warnings, legacy fallback/full report, persisted request/status/history recovery, reload, blocked running closure and saved completion without retry or real generation/approval mutation, mobile and text/key safety"
        )


if __name__ == "__main__":
    main()
