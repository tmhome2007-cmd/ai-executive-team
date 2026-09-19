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
        description="The specific technical detail of the action (e.g., shell command string, file path + operation)."
    )


class ProposeActionTool(BaseTool):
    name: str = "propose_action"
    description: str = (
        "Use this to propose a real-world action (like running a command, modifying a file, "
        "or making a change outside this conversation) for human review. This does NOT execute "
        "anything — it only logs the proposal for a human to approve or reject later. "
        "You should use this instead of claiming you performed an action directly."
    )
    args_schema: Type[BaseModel] = ActionProposalInput
    
    # De rol van de agent wordt ingesteld bij het aanmaken van de tool-instantie
    role: str

    def __init__(self, role: str, **data):
        super().__init__(role=role, **data)

    def _run(self, action_description: str, action_detail: str) -> str:
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
            action_detail=action_detail
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