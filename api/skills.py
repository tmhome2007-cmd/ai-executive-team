"""Owner-only skill proposals and decisions; no business execution authority."""

from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Path, Query
from pydantic import Field
from api.common import StrictRequest, invoke, private_response
from memory.executive_skills import (
    create_skill,
    decide_skill,
    eligible_reviews,
    get_skill,
    list_skills,
)

router = APIRouter(dependencies=[Depends(private_response)])
Identity = Annotated[int, Field(strict=True, ge=1, le=9223372036854775807)]


class SkillProposal(StrictRequest):
    skill_key: str = Field(
        min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9-]{0,79}$"
    )
    name: str = Field(min_length=1, max_length=200)
    procedure: str = Field(min_length=1, max_length=8000)
    prerequisites: str = Field(min_length=1, max_length=2000)
    limitations: str = Field(min_length=1, max_length=2000)
    review_ids: list[Identity] = Field(min_length=2, max_length=2)


class SkillDraft(StrictRequest):
    skill_key: str = Field(
        min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9-]{0,79}$"
    )
    name: str = Field(min_length=1, max_length=200)
    review_ids: list[Identity] = Field(min_length=2, max_length=2)


class SkillDecision(StrictRequest):
    expected_version: Identity
    state: Literal["accepted", "revoked"]
    note: str = Field(min_length=1, max_length=2000)


@router.get("/skills/evidence")
def skill_evidence():
    return invoke(eligible_reviews)


@router.get("/skills")
def skills_list(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=9223372036854775807),
):
    return invoke(list_skills, limit, offset)


@router.post("/skills")
def skill_propose(request: SkillProposal):
    return invoke(create_skill, **request.model_dump())


@router.post("/skills/draft")
def skill_draft(request: SkillDraft):
    from workflows.executive_skills import draft_skill

    return invoke(draft_skill, **request.model_dump())


@router.get("/skills/{ident}")
def skill_get(ident: Annotated[int, Path(ge=1, le=9223372036854775807)]):
    return invoke(get_skill, ident)


@router.post("/skills/{ident}/decision")
def skill_decide(
    ident: Annotated[int, Path(ge=1, le=9223372036854775807)], request: SkillDecision
):
    return invoke(decide_skill, ident, **request.model_dump())
