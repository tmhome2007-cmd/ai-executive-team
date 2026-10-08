"""
tools/file_operation_tool.py

CrewAI tool waarmee agenten een GESTRUCTUREERDE bestandsoperatie voorstellen
(read/write/append) in plaats van een ruwe shell-string. Dit is bewust
veiliger dan het bestaande ProposeActionTool voor dit soort taken: er komt
geen shell aan te pas (dus geen command-injection-oppervlak), de operatie
wordt opgeslagen als expliciete JSON-velden, en uitvoering gebeurt via
gewone Python file I/O binnen dezelfde workspace-confinement grens als
workflows/action_executor.py al gebruikt voor shell-commando's.
"""

import privacy_bootstrap  # apply local-first telemetry defaults before CrewAI imports


import json
from typing import Type, Literal
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from memory.database import propose_action
from notifications.telegram_interactive import send_proposal_notification
from tools._dedupe_guard import check_and_register_proposal


class FileOperationInput(BaseModel):
    """Input schema voor ProposeFileOperationTool."""
    operation: Literal["read", "write", "append"] = Field(
        ...,
        description="The file operation to propose: 'read' (view contents), 'write' (overwrite/create), or 'append' (add to end)."
    )
    file_path: str = Field(
        ...,
        description="Path to the file, relative to the project's workspace directory. Cannot escape the workspace."
    )
    content: str = Field(
        default="",
        description="The text content to write or append. Not used for 'read' operations."
    )
    reason: str = Field(
        ...,
        description="A short, human-readable explanation of why this file operation is being proposed."
    )
    expected_outcome: str | None = Field(
        default=None,
        description="What concrete result should exist after this file operation is approved and executed."
    )
    expected_impact: str | None = Field(
        default=None,
        description="Qualitative impact expected from creating/reading/updating the file."
    )
    expected_cost_amount: float | None = Field(
        default=None,
        ge=0,
        description="Expected monetary cost only when evidence supports one; otherwise leave empty."
    )
    currency: str | None = Field(
        default=None,
        description="3-letter currency code such as EUR or USD when expected_cost_amount is known."
    )


class ProposeFileOperationTool(BaseTool):
    name: str = "propose_file_operation"
    description: str = (
        "Use this to propose a structured file operation (read, write, or append) within the "
        "project's workspace directory, for human review. This is safer and more precise than "
        "propose_action for file tasks — it does NOT execute anything itself, it only logs the "
        "proposal for a human to approve. Prefer this over propose_action whenever the task is "
        "specifically about reading, writing, or appending to a file."
    )
    args_schema: Type[BaseModel] = FileOperationInput

    # De rol van de agent wordt ingesteld bij het aanmaken van de tool-instantie
    role: str

    def __init__(self, role: str, **data):
        super().__init__(role=role, **data)

    def _run(
        self,
        operation: str,
        file_path: str,
        content: str,
        reason: str,
        expected_outcome: str | None = None,
        expected_impact: str | None = None,
        expected_cost_amount: float | None = None,
        currency: str | None = None,
    ) -> str:
        # Breekt een runaway herhaal-loop: dezelfde (rol + operatie + pad)
        # binnen het dedupe-venster wordt niet opnieuw gelogd of genotificeerd.
        # Bewust NIET op 'content' of 'reason' meegewogen — het incident dat
        # dit veroorzaakte liet de agent exact dezelfde write herhalen met
        # steeds licht andere reason-tekst, wat een content/reason-gebaseerde
        # sleutel niet zou hebben opgevangen.
        dedupe_key = f"file_operation:{self.role}:{operation}:{file_path}"
        duplicate_message = check_and_register_proposal(dedupe_key)
        if duplicate_message:
            return duplicate_message

        # De actie wordt opgeslagen als JSON in action_detail, met
        # action_type='file_operation' zodat de executor weet dit via
        # gewone file I/O af te handelen, niet via subprocess/shell.
        action_detail_dict = {
            "operation": operation,
            "file_path": file_path,
            "content": content,
        }
        action_detail_json = json.dumps(action_detail_dict)

        description = f"{operation.capitalize()} file '{file_path}': {reason}"

        action_id = propose_action(
            proposed_by=self.role,
            action_description=description,
            action_detail=action_detail_json,
            action_type="file_operation",
            expected_outcome=expected_outcome,
            expected_impact=expected_impact,
            expected_cost_amount=expected_cost_amount,
            currency=currency,
        )

        try:
            send_proposal_notification(
                action_id=action_id,
                proposed_by=self.role,
                action_description=description,
                action_detail=f"[{operation}] {file_path}" + (f"\n\n{content[:200]}" if content else ""),
            )
        except Exception as e:
            print(f"Warning: Failed to send Telegram notification for file operation proposal #{action_id}: {e}")

        return (
            f"File operation proposal logged successfully with ID #{action_id}. "
            f"It is now pending human review and approval."
        )