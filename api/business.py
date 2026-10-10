"""Zero-budget business evidence and private practice API routes."""

from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Path, Query
from pydantic import Field
from api.common import StrictRequest, invoke, private_response

router = APIRouter(dependencies=[Depends(private_response)])

from memory.business_discovery import (
    create_brief,
    get_brief,
    list_briefs,
    select_practice,
    review_practice,
)
from workflows.business_discovery import run_stage, read_public_source


class BusinessBriefRequest(StrictRequest):
    workflow_template_id: (
        Annotated[int, Field(strict=True, ge=1, le=9223372036854775807)] | None
    ) = None
    title: str = Field(min_length=1, max_length=200)
    constraints: str = Field(min_length=1, max_length=4000)
    source_ids: list[
        Annotated[int, Field(strict=True, ge=1, le=9223372036854775807)]
    ] = Field(min_length=3, max_length=20)


class BusinessVersion(StrictRequest):
    expected_version: int = Field(strict=True, ge=1, le=9223372036854775807)


class BusinessPractice(BusinessVersion):
    skill_version_id: (
        Annotated[int, Field(strict=True, ge=1, le=9223372036854775807)] | None
    ) = None
    service_key: Literal["documentation", "editing", "support_drafts", "legacy"] = (
        "legacy"
    )
    audience: str = Field(default="", max_length=1000)
    supplied_facts: str = Field(default="", max_length=6000)
    deliverable_kind: str = Field(default="", max_length=200)
    selected_option: str = Field(min_length=1, max_length=1000)
    exercise: str = Field(min_length=1, max_length=4000)
    checks: list[str] = Field(min_length=2, max_length=10)
    observation_due_at: str = Field(max_length=40)


class BusinessReview(BusinessVersion):
    results: list[Annotated[bool, Field(strict=True)]] = Field(
        min_length=2, max_length=10, strict=True
    )
    evidence: str = Field(min_length=1, max_length=12000)
    observed_at: str = Field(max_length=40)


class BusinessSource(StrictRequest):
    url: str = Field(min_length=1, max_length=1000)


@router.post("/business-discovery/public-source")
def business_source(request: BusinessSource):
    return invoke(read_public_source, request.url)


@router.get("/business-discovery")
def business_list(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return invoke(list_briefs, limit, offset)


@router.post("/business-discovery")
def business_create(request: BusinessBriefRequest):
    return invoke(create_brief, **request.model_dump())


class BusinessSourceContext(StrictRequest):
    expected_version: int = Field(strict=True, ge=0, le=9223372036854775806)
    category: Literal[
        "unknown", "demand", "buyer", "platform", "constraint", "contradiction"
    ]
    services: list[Literal["documentation", "editing", "support_drafts"]] = Field(
        max_length=3
    )
    publication_date: str | None = Field(default=None, max_length=10)
    note: str = Field(default="", max_length=1000)


@router.get("/business-discovery/source-context/{source_id}")
def business_source_context(
    source_id: Annotated[int, Path(ge=1, le=9223372036854775807)],
):
    from memory.business_evidence import business_sources

    return invoke(business_sources, [source_id])[0]["business_context"]


@router.post("/business-discovery/source-context/{source_id}")
def business_classify_source(
    source_id: Annotated[int, Path(ge=1, le=9223372036854775807)],
    request: BusinessSourceContext,
):
    from memory.business_evidence import classify_source

    return invoke(classify_source, source_id, **request.model_dump())


@router.get("/business-discovery/practice-templates")
def business_templates():
    from memory.practice_quality import TEMPLATES

    return TEMPLATES


@router.get("/business-discovery/practice-evidence")
def business_practice_evidence():
    from memory.practice_quality import practice_evidence
    from memory.database import get_connection

    with get_connection() as conn:
        conn.execute("BEGIN")
        return practice_evidence(conn.cursor())


@router.get("/business-discovery/{ident}")
def business_get(ident: Annotated[int, Path(ge=1, le=9223372036854775807)]):
    return invoke(get_brief, ident)


@router.post("/business-discovery/{ident}/research")
def business_research(
    ident: Annotated[int, Path(ge=1, le=9223372036854775807)], request: BusinessVersion
):
    return invoke(run_stage, ident, request.expected_version, "research")


@router.post("/business-discovery/{ident}/practice-plan")
def business_select(
    ident: Annotated[int, Path(ge=1, le=9223372036854775807)], request: BusinessPractice
):
    return invoke(select_practice, ident, **request.model_dump())


@router.post("/business-discovery/{ident}/practice")
def business_practice(
    ident: Annotated[int, Path(ge=1, le=9223372036854775807)], request: BusinessVersion
):
    return invoke(run_stage, ident, request.expected_version, "practice")


@router.post("/business-discovery/{ident}/review")
def business_review(
    ident: Annotated[int, Path(ge=1, le=9223372036854775807)], request: BusinessReview
):
    return invoke(review_practice, ident, **request.model_dump())


@router.post("/business-discovery/{ident}/revise")
def business_revise(
    ident: Annotated[int, Path(ge=1, le=9223372036854775807)], request: BusinessVersion
):
    return invoke(run_stage, ident, request.expected_version, "revision")


@router.post("/business-discovery/{ident}/review-correction")
def business_review_correction(
    ident: Annotated[int, Path(ge=1, le=9223372036854775807)], request: BusinessReview
):
    return invoke(review_practice, ident, **request.model_dump(), correction=True)
