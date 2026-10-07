"""
workflows/preparation.py

Phase 2 preparation workflow:
approved executive decision -> concrete, decision-linked action proposals.

This phase may CREATE proposals, but it never approves or executes them.
Every proposed shell/file/browser action remains in the existing human action
approval queue and must be approved separately before execute_action() can run.
"""

from typing import Any

from agents.executive_agents import build_preparation_agents
from memory.database import (
    claim_decision_for_preparation,
    finalize_decision_preparation,
    get_decision_by_id,
)
from workflows.meeting import run_executive_meeting


PREPARATION_AGENT_KEYS = ["cfo", "general_counsel", "cto", "coo"]


def run_decision_preparation(decision_id: int) -> dict[str, Any]:
    decision = get_decision_by_id(decision_id)
    if decision is None:
        return {"success": False, "error": "Decision not found"}

    if decision.get("approval_status") != "approved":
        return {
            "success": False,
            "error": (
                f"Decision status is '{decision.get('approval_status')}', "
                "must be 'approved' before preparation."
            ),
        }

    if not claim_decision_for_preparation(decision_id):
        refreshed = get_decision_by_id(decision_id)
        return {
            "success": False,
            "error": (
                "Decision could not be claimed for preparation; current "
                f"preparation status is '{refreshed.get('preparation_status') if refreshed else 'unknown'}'."
            ),
        }

    agents = build_preparation_agents(decision_id)

    preparation_prompt = f"""
OWNER-APPROVED DECISION #{decision_id}

Topic:
{decision['topic']}

Original question/context:
{decision['task_description']}

Approved executive decision:
{decision['decision_outcome']}

Owner feedback:
{decision.get('owner_feedback') or '(none provided)'}

You are now in the PREPARATION phase, not the decision phase.

Your job is to determine what concrete work, access, information, files,
browser steps, commands, integrations, or other resources are needed to carry
out the approved direction.

Rules:
- The owner's approval authorizes PREPARATION ONLY. It does NOT authorize any
  real-world action to execute.
- Use proposal tools only when a concrete action is genuinely needed.
- Every tool call creates a separate action proposal that must still be
  approved by the human owner before execution.
- Never claim that a proposed action has already happened.
- Do not create speculative busywork. Propose only steps directly needed for
  this approved decision.
- If a required capability/access cannot be represented by an available tool,
  state exactly what access/plugin/credential/resource the owner would need to
  provide, without requesting secrets in the response.
- Preserve the evidence discipline from the approved meeting. Do not invent
  budgets, ROI, timelines, accounts, credentials, customers, infrastructure,
  or capabilities that are not known.
- End with a concise preparation status: what was proposed, what still
  requires owner-provided access/resources, and what remains blocked.
""".strip()

    try:
        result = run_executive_meeting(
            topic=f"Preparation for approved decision #{decision_id}: {decision['topic']}",
            task_description=preparation_prompt,
            agent_keys=PREPARATION_AGENT_KEYS,
            agents_source=agents,
        )
        summary = result.get("final_decision", "")
        if not finalize_decision_preparation(decision_id, "prepared", summary):
            return {
                "success": False,
                "error": "Preparation completed but decision state could not be finalized.",
                "meeting_result": result,
            }
        return {
            "success": True,
            "decision_id": decision_id,
            "preparation_summary": summary,
            "meeting_result": result,
        }
    except Exception as exc:
        error_summary = f"Preparation failed: {exc}"
        finalize_decision_preparation(decision_id, "preparation_failed", error_summary)
        return {
            "success": False,
            "decision_id": decision_id,
            "error": error_summary,
        }
