"""Owner-facing planning and operating routes; assembles isolated feature routers."""

from typing import Literal
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import Field
from memory.evidence import (
    create_source,
    get_source,
    list_sources,
    review_source,
    add_evidence_link,
    entity_evidence,
)

from api.common import StrictRequest, invoke, private_response

router = APIRouter(dependencies=[Depends(private_response)])


class SourceRequest(StrictRequest):
    source_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    reference: str = Field(min_length=1, max_length=1000)
    summary: str = Field(min_length=1, max_length=12000)
    observed_at: str = Field(max_length=40)
    expires_at: str | None = Field(default=None, max_length=40)
    source_kind: Literal[
        "owner_record", "owner_context", "observation", "document", "external_reference"
    ] = "owner_record"


class SourceReview(StrictRequest):
    expected_version: int = Field(ge=1)
    verification: Literal["unverified", "owner_confirmed", "disputed"]


class EvidenceLink(StrictRequest):
    source_id: int = Field(ge=1)
    entity_kind: Literal["decision", "observation", "discussion"]
    entity_id: int = Field(ge=1)
    relation: Literal["context", "supports", "contradicts"] = "context"
    claim: str = Field(default="", max_length=2000)


@router.get("/evidence")
def sources(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return list_sources(limit, offset)


@router.post("/evidence")
def source_create(request: SourceRequest):
    return invoke(create_source, **request.model_dump())


@router.get("/evidence/{source_id}")
def source_get(source_id: int):
    source = get_source(source_id)
    if source is None:
        raise HTTPException(404, "Source not found")
    return source


@router.patch("/evidence/{source_id}")
def source_review(source_id: int, request: SourceReview):
    return invoke(review_source, source_id, **request.model_dump())


@router.post("/evidence-links")
def evidence_link(request: EvidenceLink):
    return invoke(add_evidence_link, **request.model_dump())


@router.get("/evidence-for/{entity_kind}/{entity_id}")
def evidence_for(entity_kind: str, entity_id: int):
    return invoke(entity_evidence, entity_kind, entity_id)


from memory.planning import (
    create_plan,
    list_plans,
    get_plan,
    review_plan,
    review_work,
    workload,
)
from workflows.executive_planning import generate_plan, dispatch_planned_work


class ProposedTask(StrictRequest):
    key: str = Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")
    title: str = Field(min_length=1, max_length=200)
    acceptance_criteria: str = Field(min_length=1, max_length=10000)
    assignee: str = Field(max_length=40)
    depends_on: list[str] = Field(default_factory=list, max_length=20)
    expected_cost: float = Field(ge=0, le=1e15, strict=True)
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class PlanGeneration(StrictRequest):
    run_key: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9:_-]+$")
    goal_id: int = Field(ge=1)
    board_id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    proposer: str = Field(default="coo", max_length=40)


class PlanRequest(PlanGeneration):
    tasks: list[ProposedTask] = Field(min_length=1, max_length=20)


class OwnerReview(StrictRequest):
    approved: bool = Field(strict=True)
    note: str = Field(min_length=1, max_length=4000)


class PlanReview(OwnerReview):
    expected_version: int = Field(ge=1)


@router.get("/plans")
def plans(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return list_plans(limit, offset)


@router.post("/plans")
def plan_create(request: PlanRequest):
    return invoke(create_plan, **request.model_dump())


@router.post("/plans/generate")
def plan_generate(request: PlanGeneration):
    return invoke(generate_plan, **request.model_dump())


@router.get("/plans/{plan_id}")
def plan_get(plan_id: int):
    plan = get_plan(plan_id)
    if plan is None:
        raise HTTPException(404, "Plan not found")
    return plan


@router.post("/plans/{plan_id}/review")
def plan_review(plan_id: int, request: PlanReview):
    return invoke(review_plan, plan_id, **request.model_dump())


@router.post("/planned-work/{work_id}/review")
def work_review(work_id: int, request: OwnerReview):
    return invoke(review_work, work_id, **request.model_dump())


@router.get("/executive-workload")
def executive_workload():
    return workload()


@router.post("/planned-work/dispatch")
async def work_dispatch(max_items: int = Query(2, ge=1, le=5)):
    return await dispatch_planned_work(max_items)


from memory.discussions import get_discussion
from workflows.discussion_rounds import run_discussion


class DiscussionRequest(StrictRequest):
    run_key: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9:_-]+$")
    topic: str = Field(min_length=1, max_length=200)
    task_description: str = Field(min_length=1, max_length=12000)
    agent_keys: list[str] = Field(min_length=1, max_length=11)
    source_ids: list[int] = Field(default_factory=list, max_length=20)
    goal_id: int | None = Field(default=None, ge=1)


@router.post("/discussions")
def discussion_create(request: DiscussionRequest):
    return invoke(run_discussion, **request.model_dump())


@router.get("/decisions/{decision_id}/discussion")
def discussion_get(decision_id: int):
    return {
        "messages": invoke(get_discussion, decision_id),
        "scope": "Published proposal/critique/revision/synthesis; not hidden reasoning or verbatim speech",
    }


from memory.capabilities import (
    provide_capability,
    list_capabilities,
    revoke_capability,
    bind_capabilities,
)
from workflows.capability_inventory import verify_capability


class CapabilityRequest(StrictRequest):
    resource_request_id: int = Field(ge=1, strict=True)
    provider: Literal["github", "browser", "manual"]
    scopes: list[str] = Field(min_length=1, max_length=10)
    roles: list[str] = Field(min_length=1, max_length=11)
    target: str = Field(min_length=1, max_length=200)
    secret_ref: Literal["GITHUB_TOKEN"] | None = None


class VersionRequest(StrictRequest):
    expected_version: int = Field(ge=1, strict=True)


class CapabilityRequirement(StrictRequest):
    grant_id: int = Field(ge=1, strict=True)
    scope: str = Field(min_length=1, max_length=60)


class CapabilityBinding(StrictRequest):
    requirements: list[CapabilityRequirement] = Field(min_length=1, max_length=10)


@router.get("/capabilities")
def capabilities(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return list_capabilities(limit, offset)


@router.post("/capabilities")
def capability_provide(request: CapabilityRequest):
    return invoke(provide_capability, **request.model_dump())


@router.post("/capabilities/{capability_id}/verify")
def capability_verify(capability_id: int):
    return invoke(verify_capability, capability_id)


@router.post("/capabilities/{capability_id}/revoke")
def capability_revoke(capability_id: int, request: VersionRequest):
    return invoke(revoke_capability, capability_id, request.expected_version)


@router.post("/actions/{action_id}/capabilities")
def capability_bind(action_id: int, request: CapabilityBinding):
    result = invoke(bind_capabilities, action_id, request.model_dump()["requirements"])
    # Authority seal fields are internal; never expose credential fingerprints.
    return {
        "action_id": result["action_id"],
        "requirements": [
            {k: v for k, v in row.items() if k != "credential_fingerprint"}
            for row in result["requirements"]
        ],
    }


# BE-08–11 share the main router's existing owner-auth dependency.
from memory.operating_policies import get_policy, save_policy
from memory.memory_reconciliation import curated_memories, reconcile_memory
from memory.observation_jobs import schedule_observation, list_jobs, review_job
from memory.agent_activity_stream import stream_page, executive_states


class OperatingPolicyRequest(StrictRequest):
    expected_version: int = Field(ge=1)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    max_action_cost: float | None = Field(default=None, ge=0, le=1e15)
    max_daily_cost: float | None = Field(default=None, ge=0, le=1e15)
    max_experiment_risk: float | None = Field(default=None, ge=0, le=1e15)
    require_known_cost: bool = False
    prohibited_types: list[Literal["shell", "file_operation", "browser_action"]] = (
        Field(default_factory=list, max_length=3)
    )
    note: str = Field(min_length=1, max_length=2000)


@router.get("/operating-policy")
def read_operating_policy():
    return get_policy()


@router.put("/operating-policy")
def write_operating_policy(request: OperatingPolicyRequest):
    return invoke(save_policy, **request.model_dump())


class MemoryReconcileRequest(StrictRequest):
    expected_version: int = Field(ge=1)
    operation: Literal["annotate", "correct", "expire", "conflict"]
    source_ids: list[int] = Field(min_length=1, max_length=20)
    note: str = Field(min_length=1, max_length=2000)
    lesson: str | None = Field(default=None, max_length=2000)
    claim_key: str = Field(default="", max_length=120)
    expires_at: str | None = Field(default=None, max_length=40)


@router.get("/memory-review")
def read_memory_review(
    limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)
):
    return curated_memories(limit, offset)


@router.post("/memory-review/{ident}")
def write_memory_review(ident: int, request: MemoryReconcileRequest):
    return invoke(reconcile_memory, ident, **request.model_dump())


@router.get("/memory-review/{ident}/history")
def memory_review_history(
    ident: int, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)
):
    from memory.database import get_connection

    with get_connection() as conn:
        return [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM memory_revisions WHERE memory_id=? ORDER BY version DESC LIMIT ? OFFSET ?",
                (ident, limit, offset),
            )
        ]


class ObservationJobRequest(StrictRequest):
    job_key: str = Field(min_length=1, max_length=80)
    experiment_id: int = Field(ge=1)
    collector: Literal["owner_source", "approved_file_read"]
    due_at: str = Field(max_length=40)
    source_id: int | None = Field(default=None, ge=1)
    collection_action_id: int | None = Field(default=None, ge=1)


class ObservationJobReview(StrictRequest):
    expected_version: int = Field(ge=1)
    operation: Literal["retry", "cancel"]


@router.get("/observation-jobs")
def read_observation_jobs(
    limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)
):
    return list_jobs(limit, offset)


@router.post("/observation-jobs")
def write_observation_job(request: ObservationJobRequest):
    return invoke(schedule_observation, **request.model_dump())


@router.post("/observation-jobs/{ident}/review")
def write_observation_job_review(ident: int, request: ObservationJobReview):
    return invoke(review_job, ident, request.expected_version, request.operation)


@router.get("/activity-stream/page")
def read_stream_page(
    after_id: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)
):
    return {
        **stream_page(after_id, limit),
        "executives": executive_states(),
        "state_scope": "Running is a recent observed task start; idle is observed completion; interrupted/stale/unobserved roles are unknown",
    }


_active_streams = 0
_MAX_STREAMS = 16


@router.get("/activity-stream")
async def stream_activity(after_id: int = Query(0, ge=0)):
    import asyncio
    import json
    from starlette.responses import StreamingResponse

    if _active_streams >= _MAX_STREAMS:
        raise HTTPException(429, "Too many activity streams; retry later")

    async def events():
        global _active_streams
        if _active_streams >= _MAX_STREAMS:
            yield 'event: unavailable\ndata: {"retry": true}\n\n'
            return
        _active_streams += 1
        try:
            async for item in replay_events():
                yield item
        finally:
            _active_streams -= 1

    async def replay_events():
        cursor = after_id
        # Finite session duration and bounded batches; reconnect with the last ID.
        for _ in range(60):
            page = await asyncio.to_thread(stream_page, cursor)
            if page["reset_required"]:
                cursor = page["after_id"]
                yield "event: reset\ndata: " + json.dumps(
                    {"after_id": cursor, "retention_days": 30}
                ) + "\n\n"
            for item in page["items"]:
                cursor = item["id"]
                yield "id: " + str(cursor) + "\nevent: activity\ndata: " + json.dumps(
                    item
                ) + "\n\n"
            states = await asyncio.to_thread(executive_states)
            yield "event: states\ndata: " + json.dumps(states) + "\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


# Presentation and workforce are owner-controlled metadata. Personal simulation
# has its own endpoints and is deliberately excluded from company evidence feeds.

# Feature routers inherit owner authentication when this router is mounted in main.
from api.business import router as business_router
from api.people import router as people_router
from api.conversation_audio import router as conversation_audio_router

# Preserve the existing request-model import surface used by local integrations.
from api.business import BusinessBriefRequest, BusinessReview

router.include_router(people_router)
router.include_router(business_router)
router.include_router(conversation_audio_router)

from api.skills import router as skills_router

router.include_router(skills_router)

from api.practice_artifacts import router as artifacts_router

router.include_router(artifacts_router)

from api.run_inspector import router as run_inspector_router

router.include_router(run_inspector_router)
