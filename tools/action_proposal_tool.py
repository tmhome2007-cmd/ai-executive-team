"""
tools/action_proposal_tool.py

CrewAI tool waarmee agenten acties voorstellen in plaats van ze direct uit te voeren.
Slaat voorstellen op in de action_queue database en stuurt een Telegram-notificatie.
"""

from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from memory.database import propose_action
from notifications.telegram_interactive import send_proposal_notification
from tools._dedupe_guard import check_and_register_proposal


class ActionProposalInput(BaseModel):
    """Input schema voor ProposeActionTool."""
    action_description: str = Field(
        ..., 
        description="A clear, human-readable description of what action is being proposed."
    )
    action_detail: str = Field(
        ...,
        description="A concrete shell command string to propose. For file changes use propose_file_operation; for web navigation use propose_browser_action."
    )
    expected_outcome: str | None = Field(
        default=None,
        description="What concrete business/operational result should happen if this action works. Do not invent metrics."
    )
    expected_impact: str | None = Field(
        default=None,
        description="Qualitative impact expected from the action. Keep unsupported claims explicitly conditional."
    )
    expected_cost_amount: float | None = Field(
        default=None,
        ge=0,
        description="Expected monetary cost only when known from evidence. Leave empty if unknown."
    )
    currency: str | None = Field(
        default=None,
        description="3-letter currency code such as EUR or USD when expected_cost_amount is known."
    )


class ProposeActionTool(BaseTool):
    name: str = "propose_action"
    description: str = (
        "Use this ONLY to propose a concrete shell command for human review. "
        "Do not use it for file reads/writes or browser navigation; use the dedicated "
        "propose_file_operation / propose_browser_action tools for those. This does NOT execute "
        "anything — it only logs the command for a human to approve or reject later."
    )
    args_schema: Type[BaseModel] = ActionProposalInput
    
    # De rol van de agent wordt ingesteld bij het aanmaken van de tool-instantie
    role: str

    def __init__(self, role: str, **data):
        super().__init__(role=role, **data)

    def _run(
        self,
        action_description: str,
        action_detail: str,
        expected_outcome: str | None = None,
        expected_impact: str | None = None,
        expected_cost_amount: float | None = None,
        currency: str | None = None,
    ) -> str:
        # Breekt een runaway herhaal-loop: dezelfde (rol + actie) binnen het
        # dedupe-venster wordt niet opnieuw gelogd of genotificeerd.
        dedupe_key = f"action:{self.role}:{action_detail}"
        duplicate_message = check_and_register_proposal(dedupe_key)
        if duplicate_message:
            return duplicate_message

        # 1. Sla het voorstel op in de database
        action_id = propose_action(
            proposed_by=self.role,
            action_description=action_description,
            action_detail=action_detail,
            expected_outcome=expected_outcome,
            expected_impact=expected_impact,
            expected_cost_amount=expected_cost_amount,
            currency=currency,
        )

        # 2. Verstuur interactieve Telegram notificatie met Approve/Reject knoppen
        try:
            send_proposal_notification(
                action_id=action_id,
                proposed_by=self.role,
                action_description=action_description,
                action_detail=action_detail,
            )
        except Exception as e:
            print(f"Warning: Failed to send Telegram notification for action proposal #{action_id}: {e}")

        # 3. Retourneer de bevestiging naar de agent
        return (
            f"Action proposal logged successfully with ID #{action_id}. "
            f"It is now pending human review and approval."
        )