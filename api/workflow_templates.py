"""Strict owner review of workflow patterns and explicit proposed-source reads."""

from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Path, Query
from pydantic import Field
from api.common import StrictRequest, invoke, private_response
from memory.workflow_templates import (
    list_templates,
    get_template,
    create_template,
    review_template,
)
from memory.research_queue import list_proposals, propose_source
from workflows.research_queue import read_proposal

router = APIRouter(dependencies=[Depends(private_response)])
Identity = Annotated[int, Field(strict=True, ge=1, le=9223372036854775807)]


class WorkflowStep(StrictRequest):
    id: str = Field(min_length=1, max_length=40, pattern=r"^[a-z][a-z0-9_-]{0,39}$")
    kind: Literal[
        "select_evidence",
        "compare_options",
        "approve_practice",
        "generate_sample",
        "review_sample",
    ]
    depends_on: list[str] = Field(max_length=5)
    capability: Literal["owner_input", "local_text"] | None = None
    gate: str | None = Field(default=None, max_length=80)


class WorkflowCreate(StrictRequest):
    key: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9-]{0,79}$")
    name: str = Field(min_length=1, max_length=200)
    steps: list[WorkflowStep] = Field(min_length=5, max_length=5)


class Version(StrictRequest):
    expected_version: Identity


class WorkflowReview(Version):
    state: Literal["reviewed", "withdrawn"]
    note: str = Field(min_length=1, max_length=2000)


class SourceProposal(StrictRequest):
    url: str = Field(min_length=1, max_length=1000)
    purpose: str = Field(min_length=1, max_length=1000)
    proposed_category: Literal[
        "unknown", "buyer", "demand", "platform", "constraint", "contradiction"
    ] = "unknown"
    origin_brief_id: Identity | None = None
    new_snapshot: Annotated[bool, Field(strict=True)] = False


@router.get("/workflow-templates")
def workflows_list(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=9223372036854775807),
):
    return invoke(list_templates, limit, offset)


@router.get("/workflow-templates/{ident}")
def workflow_get(ident: Annotated[int, Path(ge=1, le=9223372036854775807)]):
    return invoke(get_template, ident)


@router.post("/workflow-templates")
def workflow_create(request: WorkflowCreate):
    return invoke(
        create_template,
        request.key,
        request.name,
        [s.model_dump(exclude_none=True) for s in request.steps],
    )


@router.post("/workflow-templates/{ident}/review")
def workflow_review(
    ident: Annotated[int, Path(ge=1, le=9223372036854775807)], request: WorkflowReview
):
    return invoke(review_template, ident, **request.model_dump())


@router.get("/research-queue")
def queue_list(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=9223372036854775807),
):
    return invoke(list_proposals, limit, offset)


@router.post("/research-queue")
def queue_propose(request: SourceProposal):
    return invoke(propose_source, **request.model_dump())


@router.post("/research-queue/{ident}/read")
def queue_read(
    ident: Annotated[int, Path(ge=1, le=9223372036854775807)], request: Version
):
    return invoke(read_proposal, ident, request.expected_version)
