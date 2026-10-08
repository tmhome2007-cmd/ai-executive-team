"""tools/resource_request_tool.py

CrewAI tool for proposing structured resources/capabilities the team needs.
This never grants access, stores secrets, or executes anything.
"""

from typing import Type, Literal
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from memory.database import propose_resource_request
from notifications.telegram_bot import send_notification, escape_html
from tools._dedupe_guard import check_and_register_proposal


class ResourceRequestInput(BaseModel):
    resource_type: Literal[
        "access", "credential", "plugin", "data",
        "budget", "service", "hardware", "other"
    ] = Field(
        ...,
        description=(
            "Type of resource needed. Use credential only to request that a "
            "credential be configured; never include the actual secret value."
        ),
    )
    resource_name: str = Field(
        ...,
        description="Short human-readable name, e.g. 'Gmail access' or 'Market data source'.",
    )
    reason: str = Field(
        ...,
        description="Why this resource is needed and what blocker it removes.",
    )
    required_for: str | None = Field(
        default=None,
        description="Concrete task/step this resource is required for.",
    )
    amount: float | None = Field(
        default=None,
        ge=0,
        description=(
            "Requested numeric amount for budget requests only. OMIT this field for "
            "non-budget requests or when the amount is unknown. Never send text like "
            "'Unknown — evidence required'."
        ),
    )
    currency: str | None = Field(
        default=None,
        description=(
            "3-letter currency code only when a numeric budget amount is known. "
            "OMIT this field otherwise; never use placeholder text."
        ),
    )


class ProposeResourceRequestTool(BaseTool):
    name: str = "propose_resource_request"
    description: str = (
        "Use this to create a structured request for a missing capability/resource "
        "such as access, credentials, a plugin, data, budget, service, or hardware. "
        "This does NOT grant access, spend money, connect anything, or store secrets. "
        "Never put an API key/password/token in any field. For non-budget resources "
        "omit amount/currency entirely; for unknown budget amounts omit them too."
    )
    args_schema: Type[BaseModel] = ResourceRequestInput
    role: str

    def __init__(self, role: str, **data):
        super().__init__(role=role, **data)

    def _run(
        self,
        resource_type: str,
        resource_name: str,
        reason: str,
        required_for: str | None = None,
        amount: float | None = None,
        currency: str | None = None,
    ) -> str:
        dedupe_key = f"resource:{self.role}:{resource_type}:{resource_name.strip().lower()}"
        duplicate_message = check_and_register_proposal(dedupe_key)
        if duplicate_message:
            return duplicate_message

        request_id = propose_resource_request(
            requested_by=self.role,
            resource_type=resource_type,
            resource_name=resource_name,
            reason=reason,
            required_for=required_for,
            amount=amount,
            currency=currency,
        )

        try:
            amount_text = (
                f"\n<b>Amount:</b> {amount} {escape_html((currency or '').upper())}"
                if amount is not None else ""
            )
            send_notification(
                f"🧩 <b>RESOURCE REQUEST #{request_id}</b>\n\n"
                f"<b>Requested by:</b> {escape_html(self.role)}\n"
                f"<b>Type:</b> {escape_html(resource_type)}\n"
                f"<b>Resource:</b> {escape_html(resource_name)}\n"
                f"<b>Reason:</b> {escape_html(reason)}"
                f"{amount_text}\n\n"
                "Pending owner review. No access has been granted and no secret was stored."
            )
        except Exception as e:
            print(f"Warning: Failed to send resource request notification #{request_id}: {e}")

        return (
            f"Resource request logged successfully with ID #{request_id}. "
            "It is pending owner review. No access was granted and no secret was stored."
        )
