"""Disclosed application guidance from typed intake; no model call or action."""

from workflows import plan_delivery as rules

VERSION = "first-user-checklist-v3"


def quick_answer(value, records):
    """Disclosed rules, using current typed answers rather than model conclusions."""
    lead = value.lead_status or "unknown"
    tool = value.tool_status or "unknown"
    minutes = value.owner_minutes
    fallback = "If no suitable conversation is known, privately compare a relevant community invitation and a personal introduction as possible routes. Neither access nor permission is established; choose a permitted route before any outreach."
    if minutes is not None and minutes < 15:
        step = "Record the missing prerequisite in private notes; leave invitations paused."
        why = (
            "The confirmed time block is too short for the full preparation checklist."
        )
        fallback = "Choose a later preparation block; do not assume extra time today."
        effort = f"Up to {minutes} minutes, your confirmed limit."
    elif tool == "unavailable":
        step = "Keep invitations paused and record the known tool error for a later private check."
        why = "You reported that the tool is unavailable. The cause remains unknown."
        fallback = "Resume eligibility planning only after working status is confirmed; no repair or new feature is assumed."
        effort = "Up to 15 minutes of private preparation; confirm this time first if unanswered."
    elif tool == "unknown":
        step = "Find the correct tool link and documented input format, then privately check it with compatible fictional data."
        why = "Today's tool availability is unknown; an invitation would be premature."
        fallback = "If the link, safe input or working result cannot be established, record that blocker and pause invitations."
        effort = "15 minutes for the conditional checklist; confirm this time first if unanswered."
    else:
        step = {
            "silent": "Review existing messages for another possible tester with their own current case and explicit willingness.",
            "none": "Review existing messages for a possible tester; do not assume a recipient or permission exists.",
            "unknown": "Privately check the intended contact's identity and latest reply in existing messages; keep different people separate.",
            "recent_reply": "Check existing records for the responsive contact's own current case and explicit willingness to test.",
        }[lead]
        why = {
            "silent": "The intended contact stopped responding. That does not establish their interest; tool availability is already confirmed.",
            "none": "No intended contact is established. Tool availability is already confirmed.",
            "unknown": "The intended contact's current status is unknown. Tool availability is already confirmed.",
            "recent_reply": "A recent reply establishes responsiveness, but not own-case eligibility. Tool availability is already confirmed.",
        }[lead]
        effort = "15 minutes for the two private checks; confirm this time first if unanswered."
        if minutes is not None and rules.outreach_required(lead, minutes, tool):
            effort = "30 minutes including private draft review; the first two checks take 15 minutes."
    return [
        "Quick answer — application guidance",
        "First step: " + step,
        "Why: " + why,
        "If blocked: " + fallback,
        "Effort: " + effort,
        "Context: "
        + (
            f"{len(records)} reviewed project record(s) selected; historical facts still need current confirmation."
            if records
            else "No saved project records selected. Advice uses only your current answers and entered context."
        ),
        "End quick answer",
    ]


def build_checklist(value, records):
    """Keep the actionable fallback separate from executives' actual positions."""
    lead = value.lead_status or "unknown"
    tool = value.tool_status or "unknown"
    minutes = value.owner_minutes
    lines = [
        "Application checklist — not an executive recommendation",
        "Proposed owner steps only. No message has been sent and no action is authorized.",
    ]
    lines += quick_answer(value, records)
    if value.correction.strip():
        lines += ["Owner correction (verbatim):", value.correction.strip()]
    lines += [
        f"Current owner answers: contact = {lead}; tool = {tool}; available minutes = {minutes if minutes is not None else 'unknown'}.",
        "These answers apply to the reviewed day; historical records are not current confirmation.",
        "If the correction conflicts with these answers, resolve that conflict before using this checklist. The application does not infer who a person is or parse free text into a current status.",
    ]
    if minutes is not None and minutes < 15:
        lines += [
            f"Owner step — {minutes} minutes (estimate): record the missing prerequisite or known outage in private notes. Do not start an invitation plan in this time block.",
            "Next owner choice: confirm a separate block of at least 15 minutes before selecting the two-step private checklist.",
            "Stop: pause when this time block ends; do not contact anyone or assume additional time.",
        ]
        return "\n".join(lines)
    if minutes is None:
        lines.append(
            "Time budget unknown. The following 15-minute checklist is conditional: confirm that time first. No 60-minute allowance is assumed."
        )
    readiness = {
        "working": "Record today's owner confirmation that the tool works. Recheck only if it becomes stale or an error appears; do not ask the same availability question again.",
        "unavailable": "Record the confirmed outage and any supplied error; keep missing causes unknown. Pause invitations. Do not claim a repair or add features.",
        "unknown": "Find the intended tool link in your reviewed records and confirm its documented input format. If either is missing, record that blocker and pause. Use a safe fictional example only if it fits that format, with no personal details or credentials. Record errors and unsupported output; a failed check blocks invitations. A fictional check is not real-user validation.",
    }[tool]
    if tool == "unknown":
        readiness += (
            " Only for a suspension-notice text tool, this safe example may fit: "
            + rules.FICTIONAL_TEST
            + " For another input format, use a documented safe example or pause; do not submit this notice in an incompatible format."
        )
    route = (
        rules.CHECKS[lead]
        if tool != "unavailable"
        else "Review existing outage information and note what is needed for a later private check. Keep missing causes or safe input unknown. Pause invitations until a new working confirmation."
    )
    if tool == "working":
        lines += [
            "Tool readiness: already confirmed by you for today; no repeated availability check or separate recording task.",
            "1. Owner — 5 minutes (estimate): "
            + {
                "silent": "Find another existing conversation where follow-up is permitted; do not recheck the known silent contact's reply status.",
                "none": "Look for an existing permitted conversation; record a blocker if none is known.",
                "unknown": "Check the intended contact's identity, latest reply and date in existing messages; do not merge different people.",
                "recent_reply": "Review the responsive contact's existing messages for evidence of their own current input.",
            }[lead],
            "2. Owner — 10 minutes (estimate): For any identified candidate, record evidence of own-case eligibility and explicit willingness. Keep missing facts unknown; do not contact anyone. Do not assume the silent contact is uninterested. If no route is established, privately compare a community invitation and a personal introduction as unverified options within this time block. Access and permission must be confirmed before outreach.",
        ]
    else:
        lines += [
            f"1. Owner — 5 minutes (estimate): {readiness}",
            f"2. Owner — 10 minutes (estimate): {route}",
        ]
    draft = minutes is not None and rules.outreach_required(lead, minutes, tool)
    if draft:
        sources = {f"record:{r['id']}": r["summary"] for r in records}
        if value.correction.strip():
            sources["owner-correction"] = value.correction.strip()
        invitation = rules.recorded_invitation(sources)
        lines += [
            "3. Owner — 15 minutes (estimate): review the draft below. Verify that the recorded link is the intended tool and is accessible to the recipient; resolve any placeholder first. Sending remains a separate owner choice, conditional on a working tool, permitted input and willingness. The team must not send it.",
            f"Total owner preparation: 30 minutes (estimate), within the confirmed limit. The recipient's proposed test time is separate.",
            "Draft message — NOT SENT:",
            invitation.message(),
            "Stop: pause invitations immediately if readiness, eligibility or willingness is unconfirmed. If you later choose to send the draft, review/change this route after 7 days without a reply, measured from your sending date. Seven days is a proposed review window, not a response prediction.",
        ]
    else:
        lines += [
            f"Total: 15 minutes (estimate); confirm this budget first if unanswered. No invitation is proposed in this time block.",
            "Stop: record a blocker and pause if the tool is unavailable or no permitted eligible route is established. Review unresolved checks 7 days after starting this private review; no follow-up is implied.",
        ]
    keys = sorted(rules.allowed_unknowns(lead, tool))
    pivotal = (
        "tool_recovery"
        if tool == "unavailable"
        else "tool_availability" if tool == "unknown" else keys[0]
    )
    yes, no = rules.PIVOT_BRANCHES[pivotal]
    lines += [
        "Still unknown (selected by application rules): "
        + " ".join(rules.UNKNOWN_QUESTIONS[key] for key in keys),
        "Why this order: tool readiness and a permitted, willing person with their own relevant current input are prerequisites for a real test. An earlier offer alone proves neither eligibility nor present interest.",
        "Alternative: a new public invitation needs a suitable destination and permission; a consultant introduction needs an established willing intermediary. Neither is assumed available or authorized. Review existing permitted conversations before choosing either route.",
        "Most decision-changing unknown (selected by application rules): "
        + rules.UNKNOWN_QUESTIONS[pivotal],
        "Why: " + rules.PIVOT_REVIEW[pivotal],
        "If yes: " + yes,
        "If no: " + no,
        "Success: a willing, eligible person uses their own current real input in the documented format and reports accuracy, unsupported details/placeholders and usefulness. Positive feedback is not required.",
        "Next owner choice: record the checks, update missing facts, and decide whether an invitation is ready for personal review or must pause. No step is assigned to an AI role.",
    ]
    return "\n".join(lines)
