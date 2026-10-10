"""Owner-facing organizational APIs; included under the main owner-auth dependency."""
from typing import Literal, Annotated
from fastapi import APIRouter, HTTPException, Query, Path
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

# BE-08–11 share the main router's existing owner-auth dependency.
from memory.operating_policies import get_policy, save_policy
from memory.memory_reconciliation import curated_memories, reconcile_memory
from memory.observation_jobs import schedule_observation, list_jobs, review_job
from memory.agent_activity_stream import stream_page, executive_states


class OperatingPolicyRequest(StrictRequest):
    expected_version: int = Field(ge=1)
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    max_action_cost: float | None = Field(default=None,ge=0,le=1e15)
    max_daily_cost: float | None = Field(default=None,ge=0,le=1e15)
    max_experiment_risk: float | None = Field(default=None,ge=0,le=1e15)
    require_known_cost: bool = False
    prohibited_types: list[Literal['shell','file_operation','browser_action']] = Field(default_factory=list,max_length=3)
    note: str = Field(min_length=1,max_length=2000)


@router.get('/operating-policy')
def read_operating_policy():
    return get_policy()


@router.put('/operating-policy')
def write_operating_policy(request: OperatingPolicyRequest):
    return invoke(save_policy,**request.model_dump())


class MemoryReconcileRequest(StrictRequest):
    expected_version: int = Field(ge=1)
    operation: Literal['annotate','correct','expire','conflict']
    source_ids: list[int] = Field(min_length=1,max_length=20)
    note: str = Field(min_length=1,max_length=2000)
    lesson: str | None = Field(default=None,max_length=2000)
    claim_key: str = Field(default='',max_length=120)
    expires_at: str | None = Field(default=None,max_length=40)


@router.get('/memory-review')
def read_memory_review(limit: int=Query(50,ge=1,le=100),offset: int=Query(0,ge=0)):
    return curated_memories(limit,offset)


@router.post('/memory-review/{ident}')
def write_memory_review(ident: int,request: MemoryReconcileRequest):
    return invoke(reconcile_memory,ident,**request.model_dump())


@router.get('/memory-review/{ident}/history')
def memory_review_history(ident: int, limit: int=Query(50,ge=1,le=100), offset: int=Query(0,ge=0)):
    from memory.database import get_connection
    with get_connection() as conn:
        return [dict(row) for row in conn.execute('SELECT * FROM memory_revisions WHERE memory_id=? ORDER BY version DESC LIMIT ? OFFSET ?',(ident,limit,offset))]


class ObservationJobRequest(StrictRequest):
    job_key: str = Field(min_length=1,max_length=80)
    experiment_id: int = Field(ge=1)
    collector: Literal['owner_source','approved_file_read']
    due_at: str = Field(max_length=40)
    source_id: int | None = Field(default=None,ge=1)
    collection_action_id: int | None = Field(default=None,ge=1)


class ObservationJobReview(StrictRequest):
    expected_version: int = Field(ge=1)
    operation: Literal['retry','cancel']


@router.get('/observation-jobs')
def read_observation_jobs(limit: int=Query(50,ge=1,le=100),offset: int=Query(0,ge=0)):
    return list_jobs(limit,offset)


@router.post('/observation-jobs')
def write_observation_job(request: ObservationJobRequest):
    return invoke(schedule_observation,**request.model_dump())


@router.post('/observation-jobs/{ident}/review')
def write_observation_job_review(ident: int,request: ObservationJobReview):
    return invoke(review_job,ident,request.expected_version,request.operation)


@router.get('/activity-stream/page')
def read_stream_page(after_id: int=Query(0,ge=0),limit: int=Query(100,ge=1,le=100)):
    return {**stream_page(after_id,limit),'executives':executive_states(),'state_scope':'Running is a recent observed task start; idle is observed completion; interrupted/stale/unobserved roles are unknown'}


_active_streams = 0
_MAX_STREAMS = 16


@router.get('/activity-stream')
async def stream_activity(after_id: int=Query(0,ge=0)):
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
        cursor=after_id
        # Finite session duration and bounded batches; reconnect with the last ID.
        for _ in range(60):
            page=await asyncio.to_thread(stream_page,cursor)
            if page['reset_required']:
                cursor=page['after_id']
                yield 'event: reset\ndata: '+json.dumps({'after_id':cursor,'retention_days':30})+'\n\n'
            for item in page['items']:
                cursor=item['id']
                yield 'id: '+str(cursor)+'\nevent: activity\ndata: '+json.dumps(item)+'\n\n'
            states=await asyncio.to_thread(executive_states)
            yield 'event: states\ndata: '+json.dumps(states)+'\n\n'
            await asyncio.sleep(5)
    return StreamingResponse(events(),media_type='text/event-stream',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})

# Presentation and workforce are owner-controlled metadata. Personal simulation
# has its own endpoints and is deliberately excluded from company evidence feeds.
from memory.character_profiles import get_character,save_character,character_history
from memory.organization import departments,save_department,update_department,employees,create_employee,update_employee,assignments,assign_work,review_assignment
from memory.personal_simulation import settings,set_enabled,relationship,record_personal_event,events as personal_events


class AppearanceRequest(StrictRequest):
    portrait_style: Literal['masculine','feminine','androgynous'] = 'androgynous'
    description: str = Field(min_length=1,max_length=1000)
    skin_tone: str = Field(pattern=r'^#[0-9a-fA-F]{6}$')
    hair_color: str = Field(pattern=r'^#[0-9a-fA-F]{6}$')
    eye_color: str = Field(pattern=r'^#[0-9a-fA-F]{6}$')
    eye_tint: str = Field(pattern=r'^#[0-9a-fA-F]{6}$')
    hair_style: Literal['dreadlocks','short','bob','long','curly','bun']
    beard: bool = Field(strict=True)


class BodyRequest(StrictRequest):
    height_cm: float = Field(ge=140,le=220,strict=True)
    build: Literal['slender','average','athletic','well_built']
    outfit_color: str = Field(pattern=r'^#[0-9a-fA-F]{6}$')
    asset_ref: Literal['builtin:character-v1']


class VoiceRequest(StrictRequest):
    provider: Literal['browser_local','kokoro_local']
    language: str = Field(pattern=r'^[a-z]{2,3}-[A-Z]{2}$')
    voice_name: str = Field(max_length=120)
    pitch: float = Field(ge=.5,le=1.5,strict=True)
    rate: float = Field(ge=.5,le=1.5,strict=True)
    style: str = Field(min_length=1,max_length=400)


class CharacterRequest(StrictRequest):
    expected_version: int = Field(ge=1,le=9223372036854775807,strict=True)
    appearance: AppearanceRequest
    body: BodyRequest
    voice: VoiceRequest


@router.get('/characters/voice-samples')
def neural_sample_catalog():
    from workflows.local_voice_samples import sample_catalog
    return sample_catalog()


@router.get('/characters/voice-samples/{voice}')
def neural_sample(voice: str):
    from fastapi.responses import Response
    from workflows.local_voice_samples import sample_audio
    return Response(content=invoke(sample_audio,voice),media_type='audio/wav',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})


@router.get('/characters/{key}')
def read_character(key: str): return invoke(get_character,key)


@router.put('/characters/{key}')
def write_character(key: str,request: CharacterRequest): return invoke(save_character,key,**request.model_dump())


@router.get('/characters/{key}/history')
def read_character_history(key: str,limit: int=Query(50,ge=1,le=100),offset: int=Query(0,ge=0,le=9223372036854775807)): return invoke(character_history,key,limit,offset)


class DepartmentRequest(StrictRequest):
    department_key: str = Field(pattern=r'^[a-z][a-z0-9_-]{0,49}$')
    name: str = Field(min_length=1,max_length=120)
    executive_key: str = Field(max_length=40)
    floor: Literal['01','02','03']


class DepartmentUpdate(StrictRequest):
    expected_version: int = Field(ge=1,le=9223372036854775807,strict=True)
    name: str = Field(min_length=1,max_length=120)
    executive_key: str = Field(max_length=40)
    floor: Literal['01','02','03']
    status: Literal['active','archived']


@router.get('/organization/departments')
def read_departments(limit: int=Query(50,ge=1,le=100),offset: int=Query(0,ge=0,le=9223372036854775807)): return departments(limit,offset)


@router.post('/organization/departments')
def write_department(request: DepartmentRequest): return {'id':invoke(save_department,**request.model_dump())}


@router.put('/organization/departments/{ident}')
def edit_department(ident: Annotated[int, Path(ge=1, le=9223372036854775807)],request: DepartmentUpdate): return {'id':invoke(update_department,ident,**request.model_dump())}


class EmployeeRequest(StrictRequest):
    creation_key: str = Field(min_length=1,max_length=80)
    name: str = Field(min_length=1,max_length=120)
    job_title: str = Field(min_length=1,max_length=120)
    department_id: int = Field(ge=1,le=9223372036854775807,strict=True)
    capacity_hours: float = Field(ge=0,le=168,strict=True)


class EmployeeUpdate(StrictRequest):
    expected_version: int = Field(ge=1,le=9223372036854775807,strict=True)
    department_id: int = Field(ge=1,le=9223372036854775807,strict=True)
    capacity_hours: float = Field(ge=0,le=168,strict=True)
    status: Literal['onboarding','active','suspended','retired']


@router.get('/organization/employees')
def read_employees(limit: int=Query(50,ge=1,le=100),offset: int=Query(0,ge=0,le=9223372036854775807)): return employees(limit,offset)


@router.post('/organization/employees')
def write_employee(request: EmployeeRequest): return {'id':invoke(create_employee,**request.model_dump())}


@router.put('/organization/employees/{ident}')
def edit_employee(ident: Annotated[int, Path(ge=1, le=9223372036854775807)],request: EmployeeUpdate): return {'id':invoke(update_employee,ident,**request.model_dump())}


class AssignmentRequest(StrictRequest):
    employee_id: int = Field(ge=1,le=9223372036854775807,strict=True)
    task_id: int = Field(ge=1,le=9223372036854775807,strict=True)
    hours: float = Field(gt=0,le=168,strict=True)


class AssignmentReview(StrictRequest):
    expected_version: int = Field(ge=1,le=9223372036854775807,strict=True)
    status: Literal['in_progress','completed','cancelled']
    note: str = Field(min_length=1,max_length=2000)


@router.get('/organization/assignments')
def read_assignments(limit: int=Query(50,ge=1,le=100),offset: int=Query(0,ge=0,le=9223372036854775807)): return assignments(limit,offset)


@router.post('/organization/assignments')
def write_assignment(request: AssignmentRequest): return {'id':invoke(assign_work,**request.model_dump())}


@router.post('/organization/assignments/{ident}/review')
def edit_assignment(ident: Annotated[int, Path(ge=1, le=9223372036854775807)],request: AssignmentReview): return {'id':invoke(review_assignment,ident,**request.model_dump())}


class SimulationSettings(StrictRequest):
    expected_version: int = Field(ge=1,le=9223372036854775807,strict=True)
    enabled: bool = Field(strict=True)
    note: str = Field(min_length=1,max_length=2000)


class PersonalEventRequest(StrictRequest):
    event_key: str = Field(min_length=1,max_length=80)
    kind: Literal['friendship','dating','marriage','separation','divorce','hobby','milestone']
    character_key: str = Field(max_length=60)
    partner_key: str | None = Field(default=None,max_length=60)
    narrative: str = Field(min_length=1,max_length=2000)
    simulated_at: str = Field(max_length=40)
    expected_relationship_version: int = Field(default=0,ge=0,strict=True)


@router.get('/simulation/settings')
def read_simulation_settings(): return settings()


@router.put('/simulation/settings')
def write_simulation_settings(request: SimulationSettings): return invoke(set_enabled,**request.model_dump())


@router.get('/simulation/relationship')
def read_relationship(left: str=Query(max_length=60),right: str=Query(max_length=60)): return invoke(relationship,left,right)


@router.get('/simulation/events')
def read_personal_events(limit: int=Query(50,ge=1,le=100),offset: int=Query(0,ge=0,le=9223372036854775807)): return personal_events(limit,offset)


@router.post('/simulation/events')
def write_personal_event(request: PersonalEventRequest): return invoke(record_personal_event,**request.model_dump())


@router.get('/organization/office-roster')
def read_office_roster(limit: int=Query(50,ge=1,le=100),offset: int=Query(0,ge=0,le=9223372036854775807),floor: Literal['01','02','03'] | None=None):
    from memory.organization import office_roster
    return office_roster(limit,offset,floor)

# Business discovery is owner-authenticated by the router dependency in main.
from memory.business_discovery import create_brief, get_brief, list_briefs, select_practice, review_practice
from workflows.business_discovery import run_stage, read_public_source


class BusinessBriefRequest(StrictRequest):
    title: str = Field(min_length=1, max_length=200)
    constraints: str = Field(min_length=1, max_length=4000)
    source_ids: list[Annotated[int, Field(strict=True, ge=1)]] = Field(min_length=3, max_length=20)


class BusinessVersion(StrictRequest):
    expected_version: int = Field(strict=True, ge=1)


class BusinessPractice(BusinessVersion):
    selected_option: str = Field(min_length=1, max_length=1000)
    exercise: str = Field(min_length=1, max_length=4000)
    checks: list[str] = Field(min_length=2, max_length=10)
    observation_due_at: str = Field(max_length=40)


class BusinessReview(BusinessVersion):
    results: list[Annotated[bool, Field(strict=True)]] = Field(min_length=2, max_length=10, strict=True)
    evidence: str = Field(min_length=1, max_length=12000)
    observed_at: str = Field(max_length=40)


class BusinessSource(StrictRequest):
    url: str = Field(min_length=1, max_length=1000)


@router.post('/business-discovery/public-source')
def business_source(request: BusinessSource):
    return invoke(read_public_source, request.url)


@router.get('/business-discovery')
def business_list(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return invoke(list_briefs, limit, offset)


@router.post('/business-discovery')
def business_create(request: BusinessBriefRequest):
    return invoke(create_brief, **request.model_dump())


@router.get('/business-discovery/{ident}')
def business_get(ident: int):
    return invoke(get_brief, ident)


@router.post('/business-discovery/{ident}/research')
def business_research(ident: int, request: BusinessVersion):
    return invoke(run_stage, ident, request.expected_version, 'research')


@router.post('/business-discovery/{ident}/practice-plan')
def business_select(ident: int, request: BusinessPractice):
    return invoke(select_practice, ident, **request.model_dump())


@router.post('/business-discovery/{ident}/practice')
def business_practice(ident: int, request: BusinessVersion):
    return invoke(run_stage, ident, request.expected_version, 'practice')


@router.post('/business-discovery/{ident}/review')
def business_review(ident: int, request: BusinessReview):
    return invoke(review_practice, ident, **request.model_dump())


@router.post('/business-discovery/{ident}/revise')
def business_revise(ident: int, request: BusinessVersion):
    return invoke(run_stage, ident, request.expected_version, 'revision')


@router.post('/business-discovery/{ident}/review-correction')
def business_review_correction(ident: int, request: BusinessReview):
    return invoke(review_practice, ident, **request.model_dump(), correction=True)
