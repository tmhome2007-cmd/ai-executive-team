"""Owner-facing organizational APIs; included under the main owner-auth dependency."""
from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from memory.evidence import create_source, get_source, list_sources, review_source, add_evidence_link, entity_evidence

router = APIRouter()


def invoke(callback, *args, **kwargs):
    try:
        return callback(*args, **kwargs)
    except LookupError as error:
        raise HTTPException(404, str(error)) from None
    except RuntimeError as error:
        raise HTTPException(409, str(error)) from None
    except ValueError as error:
        raise HTTPException(400, str(error)) from None


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class SourceRequest(StrictRequest):
    source_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    reference: str = Field(min_length=1, max_length=1000)
    summary: str = Field(min_length=1, max_length=12000)
    observed_at: str = Field(max_length=40)
    expires_at: str | None = Field(default=None, max_length=40)
    source_kind: Literal['owner_record', 'owner_context', 'observation', 'document', 'external_reference'] = 'owner_record'


class SourceReview(StrictRequest):
    expected_version: int = Field(ge=1)
    verification: Literal['unverified', 'owner_confirmed', 'disputed']


class EvidenceLink(StrictRequest):
    source_id: int = Field(ge=1)
    entity_kind: Literal['decision', 'observation', 'discussion']
    entity_id: int = Field(ge=1)
    relation: Literal['context', 'supports', 'contradicts'] = 'context'
    claim: str = Field(default='', max_length=2000)


@router.get('/evidence')
def sources(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return list_sources(limit, offset)


@router.post('/evidence')
def source_create(request: SourceRequest):
    return invoke(create_source, **request.model_dump())


@router.get('/evidence/{source_id}')
def source_get(source_id: int):
    source = get_source(source_id)
    if source is None:
        raise HTTPException(404, 'Source not found')
    return source


@router.patch('/evidence/{source_id}')
def source_review(source_id: int, request: SourceReview):
    return invoke(review_source, source_id, **request.model_dump())


@router.post('/evidence-links')
def evidence_link(request: EvidenceLink):
    return invoke(add_evidence_link, **request.model_dump())


@router.get('/evidence-for/{entity_kind}/{entity_id}')
def evidence_for(entity_kind: str, entity_id: int):
    return invoke(entity_evidence, entity_kind, entity_id)


from memory.planning import create_plan, list_plans, get_plan, review_plan, review_work, workload
from workflows.executive_planning import generate_plan, dispatch_planned_work


class ProposedTask(StrictRequest):
    key: str = Field(pattern=r'^[A-Za-z0-9_-]{1,40}$')
    title: str = Field(min_length=1, max_length=200)
    acceptance_criteria: str = Field(min_length=1, max_length=10000)
    assignee: str = Field(max_length=40)
    depends_on: list[str] = Field(default_factory=list, max_length=20)
    expected_cost: float = Field(ge=0, le=1e15, strict=True)
    currency: str = Field(pattern=r'^[A-Z]{3}$')


class PlanGeneration(StrictRequest):
    run_key: str = Field(min_length=1, max_length=80, pattern=r'^[A-Za-z0-9:_-]+$')
    goal_id: int = Field(ge=1)
    board_id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    proposer: str = Field(default='coo', max_length=40)


class PlanRequest(PlanGeneration):
    tasks: list[ProposedTask] = Field(min_length=1, max_length=20)


class OwnerReview(StrictRequest):
    approved: bool = Field(strict=True)
    note: str = Field(min_length=1, max_length=4000)


class PlanReview(OwnerReview):
    expected_version: int = Field(ge=1)


@router.get('/plans')
def plans(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return list_plans(limit, offset)


@router.post('/plans')
def plan_create(request: PlanRequest):
    return invoke(create_plan, **request.model_dump())


@router.post('/plans/generate')
def plan_generate(request: PlanGeneration):
    return invoke(generate_plan, **request.model_dump())


@router.get('/plans/{plan_id}')
def plan_get(plan_id: int):
    plan = get_plan(plan_id)
    if plan is None:
        raise HTTPException(404, 'Plan not found')
    return plan


@router.post('/plans/{plan_id}/review')
def plan_review(plan_id: int, request: PlanReview):
    return invoke(review_plan, plan_id, **request.model_dump())


@router.post('/planned-work/{work_id}/review')
def work_review(work_id: int, request: OwnerReview):
    return invoke(review_work, work_id, **request.model_dump())


@router.get('/executive-workload')
def executive_workload():
    return workload()


@router.post('/planned-work/dispatch')
async def work_dispatch(max_items: int = Query(2, ge=1, le=5)):
    return await dispatch_planned_work(max_items)


from memory.discussions import get_discussion
from workflows.discussion_rounds import run_discussion


class DiscussionRequest(StrictRequest):
    run_key: str = Field(min_length=1, max_length=80, pattern=r'^[A-Za-z0-9:_-]+$')
    topic: str = Field(min_length=1, max_length=200)
    task_description: str = Field(min_length=1, max_length=12000)
    agent_keys: list[str] = Field(min_length=1, max_length=11)
    source_ids: list[int] = Field(default_factory=list, max_length=20)
    goal_id: int | None = Field(default=None, ge=1)


@router.post('/discussions')
def discussion_create(request: DiscussionRequest):
    return invoke(run_discussion, **request.model_dump())


@router.get('/decisions/{decision_id}/discussion')
def discussion_get(decision_id: int):
    return {'messages': invoke(get_discussion, decision_id), 'scope': 'Published proposal/critique/revision/synthesis; not hidden reasoning or verbatim speech'}

from memory.capabilities import provide_capability, list_capabilities, revoke_capability, bind_capabilities
from workflows.capability_inventory import verify_capability


class CapabilityRequest(StrictRequest):
    resource_request_id: int = Field(ge=1, strict=True)
    provider: Literal['github', 'browser', 'manual']
    scopes: list[str] = Field(min_length=1, max_length=10)
    roles: list[str] = Field(min_length=1, max_length=11)
    target: str = Field(min_length=1, max_length=200)
    secret_ref: Literal['GITHUB_TOKEN'] | None = None


class VersionRequest(StrictRequest):
    expected_version: int = Field(ge=1, strict=True)


class CapabilityRequirement(StrictRequest):
    grant_id: int = Field(ge=1, strict=True)
    scope: str = Field(min_length=1, max_length=60)


class CapabilityBinding(StrictRequest):
    requirements: list[CapabilityRequirement] = Field(min_length=1, max_length=10)


@router.get('/capabilities')
def capabilities(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return list_capabilities(limit, offset)


@router.post('/capabilities')
def capability_provide(request: CapabilityRequest):
    return invoke(provide_capability, **request.model_dump())


@router.post('/capabilities/{capability_id}/verify')
def capability_verify(capability_id: int):
    return invoke(verify_capability, capability_id)


@router.post('/capabilities/{capability_id}/revoke')
def capability_revoke(capability_id: int, request: VersionRequest):
    return invoke(revoke_capability, capability_id, request.expected_version)


@router.post('/actions/{action_id}/capabilities')
def capability_bind(action_id: int, request: CapabilityBinding):
    result = invoke(bind_capabilities, action_id, request.model_dump()['requirements'])
    # Authority seal fields are internal; never expose credential fingerprints.
    return {'action_id': result['action_id'], 'requirements': [{k: v for k, v in row.items() if k != 'credential_fingerprint'} for row in result['requirements']]}
