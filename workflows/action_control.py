"""
workflows/action_control.py

Single owner-control path for action approval/rejection/execution.
Every interface (FastAPI, Telegram, future UI) must call these functions so
goal gates and treasury semantics cannot drift between control surfaces.
"""

from memory.database import (
    get_action_by_id,
    get_company_goal,
    approve_action_with_treasury,
    reject_action_with_treasury,
)
from workflows.action_executor import execute_action


class ActionControlError(ValueError):
    pass


def _require_linked_goal_active(action: dict, operation: str) -> None:
    goal_id = action.get("source_goal_id")
    if goal_id is None:
        return
    goal = get_company_goal(goal_id)
    if goal is None:
        raise ActionControlError(
            f"Cannot {operation}: linked company goal no longer exists."
        )
    if goal["status"] != "active":
        raise ActionControlError(
            f"Cannot {operation}: linked company goal #{goal_id} is "
            f"'{goal['status']}', not active."
        )


def approve_action_control(action_id: int) -> dict:
    action = get_action_by_id(action_id)
    if action is None:
        raise ActionControlError("Action not found")
    _require_linked_goal_active(action, "approve action")
    try:
        return approve_action_with_treasury(action_id)
    except ValueError as exc:
        raise ActionControlError(str(exc)) from exc


def reject_action_control(action_id: int) -> dict:
    action = get_action_by_id(action_id)
    if action is None:
        raise ActionControlError("Action not found")
    try:
        return reject_action_with_treasury(action_id)
    except ValueError as exc:
        raise ActionControlError(str(exc)) from exc


def execute_action_control(action_id: int) -> dict:
    action = get_action_by_id(action_id)
    if action is None:
        raise ActionControlError("Action not found")
    _require_linked_goal_active(action, "execute action")
    return execute_action(action_id)
