"""Experimental two-stage owner delivery; no API integration or execution."""

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from workflows.actionable_plan import OwnerStep, StopRule, validate_plan
from workflows.structured_decision import EvidenceQuote, OPTIONS, Text

VERSION = "owner-delivery-experiment-v1"


class PrivateStep(OwnerStep):
    """Preparation cannot label a private review as an outreach action."""

    kind: Literal["private_check"]


class Preparation(BaseModel):
    """Private prerequisites with no nullable message or outbound step."""

    model_config = ConfigDict(extra="forbid", strict=True)
    recommendation: Text
    why_this_step: Text
    facts: list[EvidenceQuote] = Field(min_length=1, max_length=3)
    unknowns: list[Text] = Field(min_length=1, max_length=3)
    assumptions: list[Text] = Field(max_length=3)
    steps: list[PrivateStep] = Field(min_length=2, max_length=3)
    stop: StopRule
    success: Text
    pivotal_fact: Text
    next_owner_decision: Text


class Invitation(BaseModel):
    """A complete unsent message, never permission to send."""

    model_config = ConfigDict(extra="forbid", strict=True)
    status: Literal["not_sent"]
    opening: Text
    live_case_request: Text
    safe_input_instructions: Text
    feedback_questions: list[Text] = Field(min_length=2, max_length=3)
    closing: Text

    def message(self):
        return "\n\n".join(
            [
                self.opening,
                self.live_case_request,
                self.safe_input_instructions,
                "Feedback:\n"
                + "\n".join(f"- {question}" for question in self.feedback_questions),
                self.closing,
            ]
        )


def outreach_required(lead_status):
    """Trusted typed intake controls scope, not model labels or source prose."""
    if lead_status not in {"recent_reply", "silent", "unknown", "none"}:
        raise ValueError("Unsupported contact status")
    return lead_status == "recent_reply"


def request(model, schema, prompt, context):
    """Same local options as prior comparisons; stages have distinct contracts."""
    shape = schema.model_json_schema()
    return {
        "model": model,
        "prompt": prompt + "\nInput:\n" + json.dumps(context, ensure_ascii=False),
        "format": shape,
        "stream": False,
        "keep_alive": 0,
        "options": dict(OPTIONS),
    }


def preparation_payload(model, question, personality, lead_status, owner_minutes):
    invitation = outreach_required(lead_status)
    reserve = 15 if invitation else 0
    if type(owner_minutes) is not int or owner_minutes <= reserve or owner_minutes > 60:
        raise ValueError("Insufficient confirmed owner time for this route")
    return request(
        model,
        Preparation,
        """Plan private preparation only. Every step must be a private check;
do not put sending, asking a contact or inviting anyone inside a private step.
Use exact source quotations. Historical facts remain unverified today. Do not
assume silent contacts are interested, or responsive contacts have a live case.
First check whether the tool works privately with fictional/redacted input.
Use the supplied route: unknown identity/status requires checking records;
silence requires reviewing another already known permitted route, or recording
a blocker if none is known. A recent reply requires privately identifying what
is still unknown about live-case eligibility before a conditional invitation.
No contacting, spending, publishing, team assignments or completed-action claims.
Give specific owner checks with estimated minutes within preparation_minutes.
Success is an own-live-case test plus structured feedback, not a sent message.
Stop on a blocker or no response within a proposed days window, never on success.
Explain why this route beats one relevant alternative. Assumptions may be empty.
Return the preparation JSON only; a separate stage supplies any unsent invitation.
""",
        {
            "question": question,
            "source_id": "owner-task",
            "personality": personality,
            "lead_status": lead_status,
            "preparation_minutes": owner_minutes - reserve,
            "conditional_invitation_follows": invitation,
        },
    )


def validate_preparation(raw, question, lead_status, owner_minutes):
    """Reject invalid preparation before invoking the drafting stage."""
    value = Preparation.model_validate_json(raw)
    reserve = 15 if outreach_required(lead_status) else 0
    return validate_plan(
        json.dumps({**value.model_dump(), "draft_message": None}),
        question,
        owner_minutes - reserve,
    )


def invitation_payload(model, question, preparation):
    return request(
        model,
        Invitation,
        """Write one actual short message for the human owner to review, NOT SENT.
Use only supplied facts; generic greeting, no invented names, eligibility,
consent, guarantees or claimed actions. Recipient replied recently but their
own current live suspension case is UNKNOWN. Ask whether they have such a case
and would voluntarily test; if not, no test request. Only invite after the owner
privately confirms the tool works. Say to paste their notice with seller/account
IDs, names, email, address and other personal details removed; never credentials.
Ask concrete feedback about diagnosis accuracy, unsupported details/placeholders,
and usefulness of the proposed plan. Keep all fields concise, combined message
under 600 characters. Return message components; do not describe a future draft.
""",
        {"question": question, "preparation": preparation.model_dump()},
    )


def assemble(preparation, draft_raw, question, lead_status, owner_minutes):
    """Deterministic composition with the original full-plan guard, no repair."""
    value = preparation.model_dump()
    if outreach_required(lead_status):
        if draft_raw is None:
            raise ValueError("Required drafting stage is missing")
        draft = Invitation.model_validate_json(draft_raw)
        components = [
            draft.opening,
            draft.live_case_request,
            draft.safe_input_instructions,
            draft.closing,
            *draft.feedback_questions,
        ]
        if any(not text.strip() for text in components):
            raise ValueError("Blank invitation component")
        value["steps"].append(
            {
                "actor": "owner",
                "kind": "outreach",
                "instruction": "Only after the private tool check passes, review the unsent draft and decide whether to send it personally. Request a test only if the recipient confirms their own current live case and willingness; otherwise record the blocker.",
                "minutes": 15,
            }
        )
        value["draft_message"] = {"status": "not_sent", "text": draft.message()}
    else:
        if draft_raw is not None:
            raise ValueError("Private-only route cannot contain an invitation")
        value["draft_message"] = None
    return validate_plan(json.dumps(value), question, owner_minutes)
