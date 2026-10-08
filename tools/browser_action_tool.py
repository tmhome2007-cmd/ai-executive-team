"""
tools/browser_action_tool.py

CrewAI tool waarmee agenten een browser-actie voorstellen: naar een URL
navigeren en optioneel één element aanklikken. Bewust beperkt tot navigeren
+ klikken — GEEN het invullen van formuliervelden, aangezien tekst typen in
een veld (bijv. een inlogformulier) een aanzienlijk grotere vertrouwensvraag
is dan op een publieke knop klikken. Net als de andere propose_* tools:
dit voert niets zelf uit, het logt alleen het voorstel voor menselijke
goedkeuring.
"""

import json
from typing import Type, Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from memory.database import propose_action, browser_url_allowed_by_provenance
from notifications.telegram_interactive import send_proposal_notification
from tools._dedupe_guard import check_and_register_proposal


class BrowserActionInput(BaseModel):
    """Input schema voor ProposeBrowserActionTool."""
    url: str = Field(
        ...,
        description="The full URL to navigate to, including https://"
    )
    click_selector: Optional[str] = Field(
        default=None,
        description="Optional CSS selector of a single element to click after navigating (e.g. 'button.submit', '#accept-cookies'). Leave empty to only navigate and observe."
    )
    reason: str = Field(
        ...,
        description="A short, human-readable explanation of why this browser action is being proposed."
    )
    expected_outcome: str | None = Field(
        default=None,
        description="What observable result should follow from this browser action if it succeeds."
    )
    expected_impact: str | None = Field(
        default=None,
        description="Qualitative business/operational impact expected from the browser action."
    )
    expected_cost_amount: float | None = Field(
        default=None,
        ge=0,
        description="Expected monetary cost only when known from evidence; otherwise leave empty."
    )
    currency: str | None = Field(
        default=None,
        description="3-letter currency code such as EUR or USD when expected_cost_amount is known."
    )


class ProposeBrowserActionTool(BaseTool):
    name: str = "propose_browser_action"
    description: str = (
        "Use this to propose navigating to a web page and optionally clicking ONE element on it "
        "(e.g. accepting a cookie banner, opening a specific link), for human review. This does NOT "
        "execute anything itself and does NOT fill in any form fields — it only logs the proposal for "
        "a human to approve. A screenshot is taken after execution as proof of what happened."
    )
    args_schema: Type[BaseModel] = BrowserActionInput

    role: str

    def __init__(self, role: str, **data):
        super().__init__(role=role, **data)

    def _run(
        self,
        url: str,
        reason: str,
        click_selector: Optional[str] = None,
        expected_outcome: str | None = None,
        expected_impact: str | None = None,
        expected_cost_amount: float | None = None,
        currency: str | None = None,
    ) -> str:
        # LLMs frequently write the literal string "null" (or "none", "n/a",
        # empty string) instead of actually omitting an optional field. Treat
        # all of these as "no selector provided" so we never try to click an
        # element literally named "null".
        if click_selector is not None and click_selector.strip().lower() in ("null", "none", "n/a", ""):
            click_selector = None

        if not browser_url_allowed_by_provenance(url):
            return (
                "Browser action proposal rejected: this URL was not present in the "
                "trusted preparation context. Do not invent domains or URLs. Ask for "
                "the exact URL/resource instead."
            )

        dedupe_key = f"browser_action:{self.role}:{url}:{click_selector}"
        duplicate_message = check_and_register_proposal(dedupe_key)
        if duplicate_message:
            return duplicate_message

        action_detail_dict = {
            "url": url,
            "click_selector": click_selector,
        }
        action_detail_json = json.dumps(action_detail_dict)

        description = f"Navigate to '{url}'" + (f" and click '{click_selector}'" if click_selector else "") + f": {reason}"

        action_id = propose_action(
            proposed_by=self.role,
            action_description=description,
            action_detail=action_detail_json,
            action_type="browser_action",
            expected_outcome=expected_outcome,
            expected_impact=expected_impact,
            expected_cost_amount=expected_cost_amount,
            currency=currency,
        )

        summary = f"[navigate] {url}" + (f"\n[click] {click_selector}" if click_selector else "")
        try:
            send_proposal_notification(
                action_id=action_id,
                proposed_by=self.role,
                action_description=description,
                action_detail=summary,
            )
        except Exception as e:
            print(f"Warning: Failed to send Telegram notification for browser action proposal #{action_id}: {e}")

        return (
            f"Browser action proposal logged successfully with ID #{action_id}. "
            f"It is now pending human review and approval."
        )