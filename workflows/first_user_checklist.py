"""Disclosed application guidance from typed intake; no model call or action."""

from workflows import plan_delivery as rules

VERSION = "first-user-checklist-v1"


def build_checklist(value, records):
    """Keep the actionable fallback separate from executives' actual positions."""
    lead = value.lead_status or "unknown"
    tool = value.tool_status or "unknown"
    minutes = value.owner_minutes
    lines = [
        "Application checklist — not an executive recommendation",
        "Proposed owner steps only. No message has been sent and no action is authorized.",
    ]
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
    route = (
        rules.CHECKS[lead]
        if tool != "unavailable"
        else "Review existing outage information and note what is needed for a later private check. Keep missing causes or safe input unknown. Pause invitations until a new working confirmation."
    )
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
            "Total owner preparation: 30 minutes (estimate), within the confirmed limit. The recipient's proposed test time is separate.",
            "Draft message — NOT SENT:",
            invitation.message(),
            "Stop: pause invitations immediately if readiness, eligibility or willingness is unconfirmed. If you later choose to send the draft, review/change this route after 7 days without a reply, measured from your sending date. Seven days is a proposed review window, not a response prediction.",
        ]
    else:
        lines += [
            "Total: 15 minutes (estimate); confirm this budget first if unanswered. No invitation is proposed in this time block.",
            "Stop: record a blocker and pause if the tool is unavailable or no permitted eligible route is established. Review unresolved checks 7 days after starting this private review; no follow-up is implied.",
        ]
    keys = sorted(rules.allowed_unknowns(lead, tool))
    lines += [
        "Still unknown (selected by application rules): "
        + " ".join(rules.UNKNOWN_QUESTIONS[key] for key in keys),
        "Why this order: tool readiness and a permitted, willing person with their own relevant current input are prerequisites for a real test. An earlier offer alone proves neither eligibility nor present interest.",
        "Alternative: a new public invitation needs a suitable destination and permission; a consultant introduction needs an established willing intermediary. Neither is assumed available or authorized. Review existing permitted conversations before choosing either route.",
        "Most route-changing unknowns: "
        + " ".join(rules.PIVOT_REVIEW[key] for key in keys),
        "Success: a willing, eligible person uses their own current real input in the documented format and reports accuracy, unsupported details/placeholders and usefulness. Positive feedback is not required.",
        "Next owner choice: record the checks, update missing facts, and decide whether an invitation is ready for personal review or must pause. No step is assigned to an AI role.",
    ]
    return "\n".join(lines)
