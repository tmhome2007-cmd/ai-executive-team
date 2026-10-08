"""
workflows/autonomous_followup.py

Deterministic autonomous follow-up watcher.

The watcher decides WHEN follow-up is required using persisted state only.
Only selected follow-up types may start a TOOL-FREE executive reasoning
meeting. Generated recommendations are stored as normal pending decisions and
still require the existing human approval -> preparation -> action/resource
approval gates before any real-world effect.
"""

import asyncio
import datetime
from typing import Any

from agents.executive_agents import EXECUTIVE_AGENTS_NO_TOOLS
from memory.database import (
    create_followup_event,
    get_company_goals,
    get_company_goal_lineage,
    get_followup_event,
    link_followup_generated_decision,
    log_decision,
)
from notifications.telegram_bot import send_notification, escape_html
from workflows.meeting import run_executive_meeting


_REASONING_EVENT_TYPES = {
    "strategy_review",
    "adverse_outcome_review",
    "overdue_goal_review",
}


def classify_goal_followups(
    goal: dict,
    lineage: dict,
    *,
    today: datetime.date | None = None,
) -> list[dict]:
    """
    Pure deterministic classification. No LLM call and no side effects.

    A fingerprint changes only when the underlying follow-up condition changes,
    so hourly scans do not create duplicate alerts/meetings.
    """
    today = today or datetime.date.today()
    candidates: list[dict] = []
    goal_sync = goal["sync_uuid"]
    decisions = lineage.get("decisions", [])

    target_date = goal.get("target_date")
    if target_date:
        target = datetime.date.fromisoformat(target_date)
        if target < today:
            candidates.append({
                "event_type": "overdue_goal_review",
                "severity": "critical",
                "reason": (
                    f"Active goal '{goal['title']}' passed its target date "
                    f"({target_date}) and needs an evidence-based strategy review."
                ),
                "fingerprint": f"goal:{goal_sync}:overdue:{target_date}",
                "meeting_required": True,
                "source_decision_id": decisions[-1]["decision"]["id"] if decisions else None,
                "source_action_id": None,
            })

    if not decisions:
        candidates.append({
            "event_type": "strategy_review",
            "severity": "attention",
            "reason": (
                f"Active goal '{goal['title']}' has no linked executive decision yet. "
                "A tool-free strategy review is required before any preparation."
            ),
            "fingerprint": f"goal:{goal_sync}:strategy-review:v1",
            "meeting_required": True,
            "source_decision_id": None,
            "source_action_id": None,
        })
        return candidates

    # Owner-facing unresolved gates are surfaced without generating extra
    # strategy meetings. The owner already has a concrete item to review.
    for decision_lineage in decisions:
        decision = decision_lineage.get("decision", {})
        approval = decision.get("approval_status")
        preparation = decision.get("preparation_status")

        if approval == "pending":
            candidates.append({
                "event_type": "owner_decision_review",
                "severity": "attention",
                "reason": (
                    f"Decision #{decision['id']} for goal '{goal['title']}' is waiting "
                    "for owner approval/rejection."
                ),
                "fingerprint": f"decision:{decision['sync_uuid']}:approval:pending",
                "meeting_required": False,
                "source_decision_id": decision["id"],
                "source_action_id": None,
            })
        elif approval == "approved" and preparation == "not_started":
            candidates.append({
                "event_type": "owner_preparation_review",
                "severity": "attention",
                "reason": (
                    f"Approved Decision #{decision['id']} for goal '{goal['title']}' "
                    "is waiting for owner-triggered preparation."
                ),
                "fingerprint": f"decision:{decision['sync_uuid']}:preparation:not-started",
                "meeting_required": False,
                "source_decision_id": decision["id"],
                "source_action_id": None,
            })

        for resource in decision_lineage.get("resource_requests", []):
            if resource.get("status") in {"pending", "approved"}:
                candidates.append({
                    "event_type": "owner_resource_review",
                    "severity": "attention",
                    "reason": (
                        f"Resource request #{resource['id']} ({resource['resource_name']}) "
                        f"for goal '{goal['title']}' is {resource['status']} and needs owner attention."
                    ),
                    "fingerprint": (
                        f"resource:{resource['sync_uuid']}:status:{resource['status']}"
                    ),
                    "meeting_required": False,
                    "source_decision_id": decision.get("id"),
                    "source_action_id": None,
                })

        for action in decision_lineage.get("actions", []):
            action_status = action.get("status")
            outcome_status = action.get("outcome_status")

            if action_status in {"pending", "approved"}:
                candidates.append({
                    "event_type": "owner_action_review",
                    "severity": "attention",
                    "reason": (
                        f"Action #{action['id']} for goal '{goal['title']}' is "
                        f"{action_status} and needs owner review/execution."
                    ),
                    "fingerprint": f"action:{action['sync_uuid']}:status:{action_status}",
                    "meeting_required": False,
                    "source_decision_id": decision.get("id"),
                    "source_action_id": action["id"],
                })

            if outcome_status == "measurement_pending":
                candidates.append({
                    "event_type": "outcome_measurement",
                    "severity": "attention",
                    "reason": (
                        f"Action #{action['id']} executed for goal '{goal['title']}', "
                        "but its business outcome still needs measurement."
                    ),
                    "fingerprint": (
                        f"action:{action['sync_uuid']}:outcome:measurement-pending:"
                        f"{action.get('updated_at') or action.get('measured_at') or 'current'}"
                    ),
                    "meeting_required": False,
                    "source_decision_id": decision.get("id"),
                    "source_action_id": action["id"],
                })

            if outcome_status in {"failed", "partial", "inconclusive"}:
                candidates.append({
                    "event_type": "adverse_outcome_review",
                    "severity": "critical" if outcome_status == "failed" else "attention",
                    "reason": (
                        f"Action #{action['id']} for goal '{goal['title']}' has measured "
                        f"business outcome '{outcome_status}'. A new tool-free executive "
                        "review should decide what to recommend next."
                    ),
                    "fingerprint": (
                        f"action:{action['sync_uuid']}:adverse:{outcome_status}:"
                        f"{action.get('updated_at') or action.get('measured_at') or 'current'}"
                    ),
                    "meeting_required": True,
                    "source_decision_id": decision.get("id"),
                    "source_action_id": action["id"],
                })

    return candidates


def _followup_meeting_prompt(goal: dict, event: dict, lineage: dict) -> str:
    recent_decision = None
    if lineage.get("decisions"):
        recent_decision = lineage["decisions"][-1].get("decision")

    return (
        "AUTONOMOUS FOLLOW-UP — TOOL-FREE REASONING ONLY\n\n"
        f"Company goal: {goal['title']}\n"
        f"Mission: {goal['description']}\n"
        f"Success criteria: {goal['success_criteria']}\n"
        f"Priority: {goal['priority']}\n"
        f"Target date: {goal.get('target_date') or 'none'}\n\n"
        f"Detected follow-up condition: {event['reason']}\n\n"
        + (
            f"Most recent linked decision: #{recent_decision['id']} — "
            f"{recent_decision['topic']}\n"
            f"Current approval state: {recent_decision.get('approval_status')}\n"
            f"Current preparation state: {recent_decision.get('preparation_status')}\n\n"
            if recent_decision else ""
        )
        + "Produce a concise follow-up recommendation. This meeting has NO tools. "
        "Do not claim any action was executed, do not invent URLs/resources/costs, "
        "and do not mark the goal complete. Any recommendation becomes a normal "
        "pending decision requiring owner approval before preparation."
    )


async def run_autonomous_followup() -> dict:
    """
    Scan all active goals. New reasoning events create at most one tool-free
    pending decision per deterministic fingerprint. Owner-gate events only
    create auditable follow-up records and notifications.
    """
    active_goals = get_company_goals(statuses=("active",), limit=100)
    created_event_ids: list[int] = []
    generated_decision_ids: list[int] = []
    existing_event_ids: list[int] = []
    errors: list[str] = []

    for goal in active_goals:
        lineage = get_company_goal_lineage(goal["id"])
        if lineage is None:
            continue

        candidates = classify_goal_followups(goal, lineage)
        for candidate in candidates:
            try:
                event_id, created = create_followup_event(
                    event_type=candidate["event_type"],
                    severity=candidate["severity"],
                    reason=candidate["reason"],
                    fingerprint=candidate["fingerprint"],
                    goal_id=goal["id"],
                    source_action_id=candidate.get("source_action_id"),
                    source_decision_id=candidate.get("source_decision_id"),
                )
            except Exception as exc:
                errors.append(
                    f"Goal #{goal['id']} {candidate['event_type']}: {exc}"
                )
                continue

            if not created:
                existing_event_ids.append(event_id)
                continue

            created_event_ids.append(event_id)

            try:
                send_notification(
                    "🔁 <b>AUTONOMOUS FOLLOW-UP</b>\n\n"
                    f"<b>Goal:</b> #{goal['id']} — {escape_html(goal['title'])}\n"
                    f"<b>Type:</b> {escape_html(candidate['event_type'])}\n"
                    f"<b>Severity:</b> {escape_html(candidate['severity'])}\n\n"
                    f"{escape_html(candidate['reason'])}"
                )
            except Exception:
                # Notification failure must never change persisted follow-up state.
                pass

            if not candidate.get("meeting_required"):
                continue

            try:
                prompt = _followup_meeting_prompt(goal, candidate, lineage)
                meeting = await asyncio.to_thread(
                    run_executive_meeting,
                    topic=f"Autonomous follow-up for Goal #{goal['id']}",
                    task_description=prompt,
                    agent_keys=["cso", "coo", "ceo"],
                    agents_source=EXECUTIVE_AGENTS_NO_TOOLS,
                    evidence_text=prompt,
                )
                decision_id = log_decision(
                    topic=f"Autonomous follow-up: {goal['title']}",
                    agents_involved=meeting.get("participants", ["cso", "coo", "ceo"]),
                    task_description=prompt,
                    decision_outcome=meeting.get("final_decision", ""),
                    sandbox_mode=True,
                    goal_id=goal["id"],
                )
                link_followup_generated_decision(event_id, decision_id)
                generated_decision_ids.append(decision_id)

                try:
                    send_notification(
                        "🧠 <b>FOLLOW-UP DECISION READY</b>\n\n"
                        f"<b>Goal:</b> #{goal['id']} — {escape_html(goal['title'])}\n"
                        f"<b>Decision:</b> #{decision_id}\n"
                        "Status: pending owner approval. No preparation or execution occurred."
                    )
                except Exception:
                    pass
            except Exception as exc:
                errors.append(
                    f"Follow-up meeting for event #{event_id} failed: {exc}"
                )

    return {
        "success": len(errors) == 0,
        "scanned_goal_count": len(active_goals),
        "created_event_ids": created_event_ids,
        "existing_event_ids": existing_event_ids,
        "generated_decision_ids": generated_decision_ids,
        "errors": errors,
    }
