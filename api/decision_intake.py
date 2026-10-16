"""Stateless authenticated preview/confirmation; no generation, persistence or tools."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from memory.evidence import get_source
from workflows.decision_intake import IntakeInput, build_intake


class IntakeConfirmation(IntakeInput):
    review_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


def confirm_intake(value):
    """Recompute context and routing; never trust a client-supplied assembled brief."""
    result = build_intake(
        IntakeInput.model_validate(value.model_dump(exclude={"review_hash"})),
        get_source,
    )
    if result["review_hash"] != value.review_hash:
        raise ValueError("The reviewed brief changed")
    return {**result, "confirmed": True}


def make_intake_router(verify_api_key):
    router = APIRouter(dependencies=[Depends(verify_api_key)])

    def preview(value):
        try:
            return build_intake(value, get_source)
        except (ValueError, LookupError):
            raise HTTPException(
                400, "Check the short request and selected reviewed context."
            ) from None

    @router.post("/decisions/intake")
    def intake(value: IntakeInput):
        return preview(value)

    @router.post("/decisions/intake/confirm")
    def confirm(value: IntakeConfirmation):
        try:
            return confirm_intake(value)
        except (ValueError, LookupError):
            raise HTTPException(
                409, "The brief changed. Review the updated brief before using it."
            ) from None

    return router
