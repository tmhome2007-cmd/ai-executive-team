"""Thin owner-authenticated HTTP boundary for approved decision preparation."""

from typing import Callable
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from workflows.decision_preparation import (
    DecisionPreparation,
    PreparationDependencies,
    PreparationError,
)


class PreparationRequest(BaseModel):
    agent_keys: list[str] = Field(
        default_factory=lambda: ["coo", "cto", "ceo"], min_length=1, max_length=11
    )


class PreparationResponse(BaseModel):
    source_decision_id: int
    final_plan: str
    participants: list[str]
    individual_outputs: dict[str, str]
    quality_warnings: dict = Field(default_factory=dict)


def build_decision_preparation_router(
    verify_api_key: Callable, dependencies: Callable[[], PreparationDependencies]
) -> APIRouter:
    """Bind application callbacks without importing the application or starting services."""
    router = APIRouter()

    @router.post(
        "/decisions/{decision_id}/prepare",
        response_model=PreparationResponse,
        summary="Prepare an Approved Decision for Execution",
        dependencies=[Depends(verify_api_key)],
    )
    def prepare_approved_decision(decision_id: int, request: PreparationRequest):
        try:
            return DecisionPreparation(
                decision_id, request.agent_keys, dependencies()
            ).prepare()
        except PreparationError as error:
            raise HTTPException(
                status_code=error.status_code, detail=error.detail
            ) from None

    return router
