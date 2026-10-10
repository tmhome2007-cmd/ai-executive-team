"""Character presentation, workforce and fictional simulation API routes."""

from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Path, Query, Response
from pydantic import Field
from api.common import StrictRequest, invoke, private_response

router = APIRouter(dependencies=[Depends(private_response)])

from memory.character_profiles import get_character, save_character, character_history
from memory.organization import (
    departments,
    save_department,
    update_department,
    employees,
    create_employee,
    update_employee,
    assignments,
    assign_work,
    review_assignment,
)
from memory.personal_simulation import (
    settings,
    set_enabled,
    relationship,
    record_personal_event,
    events as personal_events,
)


class AppearanceRequest(StrictRequest):
    portrait_style: Literal["masculine", "feminine", "androgynous"] = "androgynous"
    description: str = Field(min_length=1, max_length=1000)
    skin_tone: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    hair_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    eye_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    eye_tint: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    hair_style: Literal["dreadlocks", "short", "bob", "long", "curly", "bun"]
    beard: bool = Field(strict=True)


class BodyRequest(StrictRequest):
    height_cm: float = Field(ge=140, le=220, strict=True)
    build: Literal["slender", "average", "athletic", "well_built"]
    outfit_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    asset_ref: Literal["builtin:character-v1"]


class VoiceRequest(StrictRequest):
    provider: Literal["browser_local", "kokoro_local"]
    language: str = Field(pattern=r"^[a-z]{2,3}-[A-Z]{2}$")
    voice_name: str = Field(max_length=120)
    pitch: float = Field(ge=0.5, le=1.5, strict=True)
    rate: float = Field(ge=0.5, le=1.5, strict=True)
    style: str = Field(min_length=1, max_length=400)


class CharacterRequest(StrictRequest):
    expected_version: int = Field(ge=1, le=9223372036854775807, strict=True)
    appearance: AppearanceRequest
    body: BodyRequest
    voice: VoiceRequest


@router.get("/characters/voice-samples")
def neural_sample_catalog():
    from workflows.local_voice_samples import sample_catalog

    return sample_catalog()


@router.get("/characters/voice-samples/{voice}")
def neural_sample(voice: str):
    from fastapi.responses import Response
    from workflows.local_voice_samples import sample_audio

    return Response(
        content=invoke(sample_audio, voice),
        media_type="audio/wav",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/characters/{key}")
def read_character(key: str):
    return invoke(get_character, key)


@router.put("/characters/{key}")
def write_character(key: str, request: CharacterRequest):
    return invoke(save_character, key, **request.model_dump())


@router.get("/characters/{key}/history")
def read_character_history(
    key: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=9223372036854775807),
):
    return invoke(character_history, key, limit, offset)


class DepartmentRequest(StrictRequest):
    department_key: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,49}$")
    name: str = Field(min_length=1, max_length=120)
    executive_key: str = Field(max_length=40)
    floor: Literal["01", "02", "03"]


class DepartmentUpdate(StrictRequest):
    expected_version: int = Field(ge=1, le=9223372036854775807, strict=True)
    name: str = Field(min_length=1, max_length=120)
    executive_key: str = Field(max_length=40)
    floor: Literal["01", "02", "03"]
    status: Literal["active", "archived"]


@router.get("/organization/departments")
def read_departments(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=9223372036854775807),
):
    return departments(limit, offset)


@router.post("/organization/departments")
def write_department(request: DepartmentRequest):
    return {"id": invoke(save_department, **request.model_dump())}


@router.put("/organization/departments/{ident}")
def edit_department(
    ident: Annotated[int, Path(ge=1, le=9223372036854775807)], request: DepartmentUpdate
):
    return {"id": invoke(update_department, ident, **request.model_dump())}


class EmployeeRequest(StrictRequest):
    creation_key: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    job_title: str = Field(min_length=1, max_length=120)
    department_id: int = Field(ge=1, le=9223372036854775807, strict=True)
    capacity_hours: float = Field(ge=0, le=168, strict=True)


class EmployeeUpdate(StrictRequest):
    expected_version: int = Field(ge=1, le=9223372036854775807, strict=True)
    department_id: int = Field(ge=1, le=9223372036854775807, strict=True)
    capacity_hours: float = Field(ge=0, le=168, strict=True)
    status: Literal["onboarding", "active", "suspended", "retired"]


@router.get("/organization/employees")
def read_employees(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=9223372036854775807),
):
    return employees(limit, offset)


@router.post("/organization/employees")
def write_employee(request: EmployeeRequest):
    return {"id": invoke(create_employee, **request.model_dump())}


@router.put("/organization/employees/{ident}")
def edit_employee(
    ident: Annotated[int, Path(ge=1, le=9223372036854775807)], request: EmployeeUpdate
):
    return {"id": invoke(update_employee, ident, **request.model_dump())}


class AssignmentRequest(StrictRequest):
    employee_id: int = Field(ge=1, le=9223372036854775807, strict=True)
    task_id: int = Field(ge=1, le=9223372036854775807, strict=True)
    hours: float = Field(gt=0, le=168, strict=True)


class AssignmentReview(StrictRequest):
    expected_version: int = Field(ge=1, le=9223372036854775807, strict=True)
    status: Literal["in_progress", "completed", "cancelled"]
    note: str = Field(min_length=1, max_length=2000)


@router.get("/organization/assignments")
def read_assignments(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=9223372036854775807),
):
    return assignments(limit, offset)


@router.post("/organization/assignments")
def write_assignment(request: AssignmentRequest):
    return {"id": invoke(assign_work, **request.model_dump())}


@router.post("/organization/assignments/{ident}/review")
def edit_assignment(
    ident: Annotated[int, Path(ge=1, le=9223372036854775807)], request: AssignmentReview
):
    return {"id": invoke(review_assignment, ident, **request.model_dump())}


class SimulationSettings(StrictRequest):
    expected_version: int = Field(ge=1, le=9223372036854775807, strict=True)
    enabled: bool = Field(strict=True)
    note: str = Field(min_length=1, max_length=2000)


class PersonalEventRequest(StrictRequest):
    event_key: str = Field(min_length=1, max_length=80)
    kind: Literal[
        "friendship",
        "dating",
        "marriage",
        "separation",
        "divorce",
        "hobby",
        "milestone",
    ]
    character_key: str = Field(max_length=60)
    partner_key: str | None = Field(default=None, max_length=60)
    narrative: str = Field(min_length=1, max_length=2000)
    simulated_at: str = Field(max_length=40)
    expected_relationship_version: int = Field(default=0, ge=0, strict=True)


@router.get("/simulation/settings")
def read_simulation_settings():
    return settings()


@router.put("/simulation/settings")
def write_simulation_settings(request: SimulationSettings):
    return invoke(set_enabled, **request.model_dump())


@router.get("/simulation/relationship")
def read_relationship(
    left: str = Query(max_length=60), right: str = Query(max_length=60)
):
    return invoke(relationship, left, right)


@router.get("/simulation/events")
def read_personal_events(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=9223372036854775807),
):
    return personal_events(limit, offset)


@router.post("/simulation/events")
def write_personal_event(request: PersonalEventRequest):
    return invoke(record_personal_event, **request.model_dump())


@router.get("/organization/office-roster")
def read_office_roster(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=9223372036854775807),
    floor: Literal["01", "02", "03"] | None = None,
):
    from memory.organization import office_roster

    return office_roster(limit, offset, floor)


# Business discovery is owner-authenticated by the router dependency in main.
