"""
tools/action_proposal_tool.py

CrewAI tool waarmee agenten acties voorstellen in plaats van ze direct uit te voeren.
Slaat voorstellen op in de action_queue database en stuurt een Telegram-notificatie.
"""

from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from memory.database import propose_action
from notifications.telegram_bot import send_notification


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
        # 1. Sla het voorstel op in de database
        action_id = propose_action(
            proposed_by=self.role,
            action_description=action_description,
            action_detail=action_detail
        )

        # 2. Verstuur Telegram notificatie
        notification_text = (
            f"⏳ **NEW ACTION PROPOSAL — needs your approval**\n\n"
            f"**ID:** #{action_id}\n"
            f"**Proposed By:** {self.role}\n"
            f"**Description:** {action_description}\n"
            f"**Detail:** `{action_detail}`"
        )
        
        try:
            send_notification(notification_text)
        except Exception as e:
            print(f"Warning: Failed to send Telegram notification for action proposal #{action_id}: {e}")

        # 3. Retourneer de bevestiging naar de agent
        return (
            f"Action proposal logged successfully with ID #{action_id}. "
            f"It is now pending human review and approval."
        )