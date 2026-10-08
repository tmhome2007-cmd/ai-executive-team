"""
main.py

Hoofdbestand voor de FastAPI applicatie van het AI Executive Team.
Beheert de API-endpoints en de geautomatiseerde (catch-up) achtergrondtaken.
"""

from logging_config import setup_logging, get_logger
setup_logging()  # Moet als EERSTE gebeuren, vóór andere imports die loggen
logger = get_logger(__name__)

import asyncio
import datetime
from contextlib import asynccontextmanager
from typing import Optional, Literal
from fastapi import FastAPI, HTTPException, Query, Depends, Header, Request
import hmac
import time
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
import os
import re
import json
import ast
from pydantic import BaseModel, Field
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from memory.database import (
    init_db,
    get_recent_decisions,
    log_decision,
    get_pending_actions,
    get_action_history,
    update_action_status,
    transition_action_status,
    get_action_by_id,
    get_system_stats,
    backup_database,
    has_daily_research_attempt_on,
    get_decision_by_id,
    transition_decision_approval,
    claim_decision_for_preparation,
    finish_decision_preparation,
    recover_interrupted_actions,
    get_action_outcome,
    update_action_outcome,
    get_decision_lineage,
    get_resource_request_by_id,
    get_resource_requests,
    transition_resource_request_status,
    propose_resource_request,
    action_provenance_scope,
    add_treasury_entry,
    get_treasury_summary,
    get_treasury_history,
    get_treasury_reservation_for_action,
    approve_action_with_treasury,
    reject_action_with_treasury,
    update_action_outcome_with_treasury,
    create_company_goal,
    get_company_goal,
    get_company_goals,
    update_company_goal,
    transition_company_goal_status,
    get_company_goal_lineage,
    get_followup_event,
    get_followup_events,
    transition_followup_event_status,
    get_executive_memories,
    set_executive_memory_active,
    create_decision_memories,
    create_action_outcome_memories,
)
from workflows.daily_research import run_daily_research
from workflows.autonomous_followup import run_autonomous_followup
from workflows.meeting import run_executive_meeting
from workflows.meeting_types import MEETING_TYPES, VALID_MEETING_TYPES, resolve_meeting_agents
from agents.executive_agents import EXECUTIVE_AGENTS, EXECUTIVE_AGENTS_NO_TOOLS
from workflows.action_executor import execute_action
from workflows.action_control import (
    ActionControlError,
    approve_action_control,
    reject_action_control,
    execute_action_control,
)
from notifications.telegram_bot import send_notification, escape_html
from notifications.telegram_interactive import start_telegram_listener, stop_telegram_listener, is_telegram_listener_alive
from config import config, set_sandbox_mode, validate_config, ConfigValidationError
from system_checks import check_ollama_reachable, check_database_writable, check_telegram_configured, check_playwright_browser_installed, run_startup_checks, get_uptime_seconds


# 1. Globale status dictionary voor het monitoren van de laatste run
LAST_RUN_STATUS = {
    "last_run_time": None,
    "success": None,
    "database_id": None,
    "message": "No run yet.",
}

LAST_FOLLOWUP_STATUS = {
    "last_run_time": None,
    "success": None,
    "scanned_goal_count": 0,
    "created_event_ids": [],
    "generated_decision_ids": [],
    "resolved_event_ids": [],
    "errors": [],
    "message": "No autonomous follow-up run yet.",
}


# 2. Hulpfunctie om te controleren of de taak vandaag al gedraaid heeft
def has_run_today() -> bool:
    """Controleert in de database of er vandaag al een daily research poging is vastgelegd."""
    return has_daily_research_attempt_on(datetime.date.today())


# 3. Asynchrone Achtergrondtaak met Catch-up Logica
async def scheduled_research_job():
    """Achtergrondtaak die elke 15 min controleert of de dagelijkse research moet inhalen."""
    global LAST_RUN_STATUS
    now = datetime.datetime.now()
    now_iso = now.isoformat()

    try:
        # Sla over als het voor 09:00 uur is OF als er vandaag al een run is geweest
        if now.hour < 9 or has_run_today():
            print("Skipping — already ran today or before scheduled time (09:00).")
            return

        # Asynchrone aanroep naar run_daily_research
        result = await run_daily_research()
        is_success = result.get("success", False)
        db_id = result.get("database_id")

        if is_success:
            msg = "Daily research executed successfully (scheduled or catch-up)."
        else:
            msg = result.get("error", "Research verification failed after 3 attempts.")

        LAST_RUN_STATUS = {
            "last_run_time": now_iso,
            "success": is_success,
            "database_id": db_id,
            "message": msg,
        }

    except Exception as e:
        LAST_RUN_STATUS = {
            "last_run_time": now_iso,
            "success": False,
            "database_id": None,
            "message": f"Scheduled job crashed with error: {str(e)}",
        }


async def scheduled_autonomous_followup_job():
    """
    Hourly autonomous follow-up. The deterministic watcher may create
    owner-facing follow-up items and TOOL-FREE pending decisions only.
    It cannot approve, prepare, fulfill, reserve, execute, or measure anything.
    """
    global LAST_FOLLOWUP_STATUS
    now_iso = datetime.datetime.now().isoformat()
    try:
        result = await run_autonomous_followup()
        LAST_FOLLOWUP_STATUS = {
            "last_run_time": now_iso,
            "success": result.get("success", False),
            "scanned_goal_count": result.get("scanned_goal_count", 0),
            "created_event_ids": result.get("created_event_ids", []),
            "generated_decision_ids": result.get("generated_decision_ids", []),
            "resolved_event_ids": result.get("resolved_event_ids", []),
            "errors": result.get("errors", []),
            "message": (
                "Autonomous follow-up scan completed."
                if result.get("success", False)
                else "Autonomous follow-up scan completed with errors."
            ),
        }
    except Exception as exc:
        LAST_FOLLOWUP_STATUS = {
            "last_run_time": now_iso,
            "success": False,
            "scanned_goal_count": 0,
            "created_event_ids": [],
            "generated_decision_ids": [],
            "resolved_event_ids": [],
            "errors": [str(exc)],
            "message": f"Autonomous follow-up job crashed: {exc}",
        }


# 4. Lifespan Handler (Opstarten en Afsluiten)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Valideer de configuratie EERST — fail fast met een duidelijke foutmelding
    # in plaats van een verwarrende crash minuten later midden in een crew-run.
    try:
        config_warnings = validate_config()
        for w in config_warnings:
            logger.warning(f"Config warning: {w}")
    except ConfigValidationError as e:
        logger.error(f"FATAL: {e}")
        raise

    # Initialiseer de database
    init_db()

    # Als een vorige procesrun tijdens een echte actie crashte, is het
    # real-world resultaat per definitie onzeker. Nooit automatisch retryen:
    # markeer zulke 'executing' acties als failed voor menselijke review.
    recovered_actions = recover_interrupted_actions()
    if recovered_actions:
        logger.warning(
            f"Recovered {recovered_actions} interrupted action(s) as execution_failed; "
            "manual review required because real-world outcome is unknown."
        )

    # Controleer Ollama/database/Telegram bereikbaarheid — logt duidelijke
    # waarschuwingen in plaats van dat het probleem pas bij de eerste
    # crew-aanroep, verwarrend, aan het licht komt.
    # run_startup_checks() bevat o.a. Playwright's synchrone API. Lifespan draait
    # op de asyncio event-loop; voer de blokkerende checks daarom in een worker
    # thread uit zodat Playwright niet crasht met "Sync API inside the asyncio loop".
    await asyncio.to_thread(run_startup_checks)

    # Start de interactieve Telegram-listener (Approve/Reject/Execute knoppen)
    # in zijn eigen achtergrond-thread met een eigen event loop.
    start_telegram_listener()

    # Gebruik AsyncIOScheduler voor asynchrone achtergrondtaken
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        scheduled_research_job,
        trigger=IntervalTrigger(minutes=15),
        id="daily_research_interval_job",
        replace_existing=True,
        # Run the catch-up check as soon as the scheduler starts, but do it as
        # a scheduler job instead of awaiting the full research pipeline inside
        # FastAPI lifespan. This keeps API startup fast even when research +
        # meetings take several minutes.
        next_run_time=datetime.datetime.now(),
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        scheduled_autonomous_followup_job,
        trigger=IntervalTrigger(hours=1),
        id="autonomous_followup_interval_job",
        replace_existing=True,
        next_run_time=datetime.datetime.now() + datetime.timedelta(minutes=2),
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        lambda: backup_database(keep_last=7),
        trigger=IntervalTrigger(hours=24),
        id="daily_database_backup_job",
        replace_existing=True,
    )
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info(
        "Scheduler started: daily-research catch-up every 15 min, autonomous "
        "follow-up every 1h (first scan after 2 min), daily DB backup every 24h."
    )

    # Eén backup bij het opstarten, zodat je niet 24 uur moet wachten op de
    # eerste veiligheidskopie na een verse installatie.
    try:
        backup_path = backup_database(keep_last=7)
        logger.info(f"Startup database backup created: {backup_path}")
    except Exception as e:
        logger.warning(f"Startup database backup failed: {e}")

    logger.info("Application startup complete.")

    yield

    logger.info("Application shutting down...")

    # Sluit de scheduler netjes af bij het stoppen van de app
    app.state.scheduler.shutdown()
    logger.info("Scheduler stopped.")

    # Stop de Telegram-listener netjes (wacht tot de achtergrond-thread eindigt)
    stop_telegram_listener()
    logger.info("Telegram listener stopped. Shutdown complete.")


# 5. FastAPI App Instantie
app = FastAPI(
    title="AI Executive Team API",
    description="API voor het aansturen van autonome AI-bestuursworkflows.",
    version="1.0.0",
    lifespan=lifespan,
)

# 5.1 CORS Middleware configuratie voor Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 5.2 Request-logging middleware: elke HTTP-aanroep (methode, pad, status,
# duur) wordt gelogd — geeft achteraf zichtbaarheid in API-gebruik zonder
# dat je op het moment zelf de terminal moet volgen.
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start_time) * 1000, 1)
    logger.info(f'{request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)')
    return response


# 6. Pydantic Respons en Request Modellen
class DailyResearchResponse(BaseModel):
    success: bool
    database_id: Optional[int] = None
    research_summary: Optional[str] = None
    final_decision: Optional[str] = None
    message: Optional[str] = None


class DecisionRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    task_description: str = Field(min_length=1, max_length=12000)
    meeting_type: Literal[
        "strategy", "operating_review", "incident",
        "capital_allocation", "retrospective", "planning"
    ] = "strategy"
    agent_keys: Optional[list[str]] = Field(default=None, min_length=1, max_length=11)
    goal_id: Optional[int] = Field(default=None, ge=1)


class DecisionResponse(BaseModel):
    database_id: int
    topic: str
    meeting_type: str
    goal_id: Optional[int] = None
    final_decision: str
    participants: list[str]
    individual_outputs: dict[str, str]
    quality_warnings: dict = Field(default_factory=dict)


class GoalCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    success_criteria: str = Field(min_length=1, max_length=4000)
    priority: Literal["critical", "high", "medium", "low"] = "medium"
    target_date: Optional[str] = Field(default=None, max_length=10)
    status: Literal["draft", "active"] = "draft"


class GoalUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, min_length=1, max_length=4000)
    success_criteria: Optional[str] = Field(default=None, min_length=1, max_length=4000)
    priority: Optional[Literal["critical", "high", "medium", "low"]] = None
    target_date: Optional[str] = Field(default=None, max_length=10)


class GoalStatusRequest(BaseModel):
    status: Literal["active", "paused", "completed", "abandoned"]
    completion_note: Optional[str] = Field(default=None, max_length=2000)


class ExecutiveMemoryStatusRequest(BaseModel):
    active: bool


class PreparationRequest(BaseModel):
    agent_keys: list[str] = Field(
        default_factory=lambda: ["coo", "cto", "ceo"],
        min_length=1,
        max_length=11,
    )


class ResourceFulfillmentRequest(BaseModel):
    fulfillment_note: str = Field(
        min_length=1,
        max_length=500,
        description=(
            "Describe where/how the resource was provided, e.g. 'Gmail plugin connected'. "
            "Never include passwords, API keys, tokens, or other secret values."
        ),
    )


class TreasuryFundingRequest(BaseModel):
    amount: float = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    note: Optional[str] = Field(default=None, max_length=500)


class PreparationResponse(BaseModel):
    source_decision_id: int
    final_plan: str
    participants: list[str]
    individual_outputs: dict[str, str]
    quality_warnings: dict = Field(default_factory=dict)


# --- API Key Beveiliging ---

# Bijhouden van gefaalde pogingen per client-IP, puur in-memory (dit draait
# als één lokaal proces, geen gedeelde/verspreide store nodig). Zonder dit
# kon iemand onbeperkt X-API-Key waarden proberen — vooral relevant nu de
# server ook bereikbaar kan zijn vanaf hetzelfde netwerk (zie BIND_HOST).
_failed_auth_attempts: dict[str, list[float]] = {}
_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_WINDOW_SECONDS = 300  # 5 minuten


def verify_api_key(request: Request, x_api_key: str = Header(None)) -> bool:
    """
    Controleert of de ontvangen X-API-Key header overeenkomt met de geconfigureerde API_SECRET_KEY.
    Faalt standaard als er geen sleutel op de server is ingesteld (fail closed).

    Twee aanvullende beveiligingen t.o.v. de oorspronkelijke versie:
    - hmac.compare_digest() in plaats van != voor een CONSTANT-TIME vergelijking
      (een simpele stringvergelijking stopt vroeg zodra het eerste verschil
      wordt gevonden, wat in theorie de sleutel karakter-voor-karakter zou
      kunnen lekken via timing).
    - Een simpele lockout: na 5 mislukte pogingen vanaf hetzelfde IP binnen
      5 minuten wordt verder proberen geblokkeerd (429), ongeacht of de
      daaropvolgende poging toevallig wél de juiste sleutel zou zijn.
    """
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    attempts = [
        t for t in _failed_auth_attempts.get(client_ip, [])
        if now - t < _LOCKOUT_WINDOW_SECONDS
    ]

    server_key = config.API_SECRET_KEY
    is_valid = (
        bool(server_key)
        and x_api_key is not None
        and hmac.compare_digest(x_api_key, server_key)
    )

    # A valid owner credential must never be denied because an attacker (or a
    # broken local client) intentionally filled this IP's invalid-attempt
    # bucket. Rate limiting applies only to invalid guesses.
    if is_valid:
        _failed_auth_attempts.pop(client_ip, None)
        return True

    if len(attempts) >= _MAX_FAILED_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Too many failed authentication attempts. Try again later.",
        )

    attempts.append(now)
    _failed_auth_attempts[client_ip] = attempts
    raise HTTPException(
        status_code=401,
        detail="Missing or invalid API key",
    )


def _require_linked_goal_active(
    record: dict,
    *,
    goal_id_key: str,
    operation: str,
) -> None:
    """
    Fail closed when a decision/action/resource belongs to a goal that is no
    longer active. Rejection/audit endpoints intentionally do not call this.
    """
    goal_id = record.get(goal_id_key)
    if goal_id is None:
        return
    goal = get_company_goal(goal_id)
    if goal is None:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot {operation}: linked company goal no longer exists.",
        )
    if goal["status"] != "active":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot {operation}: linked company goal #{goal_id} is "
                f"'{goal['status']}', not active."
            ),
        )


# 7. Endpoints
@app.get("/")
def read_root():
    return {"status": "online", "system": "AI Executive Team API"}


@app.get(
    "/workflows/daily-research/status",
    summary="Get Status of Last Daily Research Run",
    dependencies=[Depends(verify_api_key)],
)
def get_daily_research_status():
    """Geeft de status en uitkomst van de laatst uitgevoerde onderzoeks-workflow terug."""
    return LAST_RUN_STATUS


@app.post(
    "/workflows/daily-research/trigger",
    response_model=DailyResearchResponse,
    summary="Trigger Daily Research Workflow",
    dependencies=[Depends(verify_api_key)],
)
async def trigger_daily_research():
    """Handmatige trigger voor de Daily Research workflow."""
    global LAST_RUN_STATUS
    now_iso = datetime.datetime.now().isoformat()

    try:
        # Asynchrone aanroep van de workflow
        result = await run_daily_research()
    except Exception as e:
        LAST_RUN_STATUS = {
            "last_run_time": now_iso,
            "success": False,
            "database_id": None,
            "message": f"Manual trigger crashed: {str(e)}",
        }
        raise HTTPException(
            status_code=502,
            detail=f"Daily research workflow crashed: {e}",
        )

    is_success = result.get("success", False)
    db_id = result.get("database_id")

    if not is_success:
        msg = "Research verification failed after 3 attempts — no meeting was held. Check Telegram/logs for details."
        LAST_RUN_STATUS = {
            "last_run_time": now_iso,
            "success": False,
            "database_id": db_id,
            "message": msg,
        }
        return DailyResearchResponse(
            success=False,
            database_id=db_id,
            message=msg,
        )

    msg = "Manual trigger executed successfully."
    LAST_RUN_STATUS = {
        "last_run_time": now_iso,
        "success": True,
        "database_id": db_id,
        "message": msg,
    }

    return DailyResearchResponse(
        success=True,
        database_id=db_id,
        research_summary=result.get("research_summary"),
        final_decision=result.get("meeting_result", {}).get("final_decision"),
        message=msg,
    )


# ===================================================================
# AUTONOMOUS FOLLOW-UP
# ===================================================================

@app.get(
    "/workflows/autonomous-followup/status",
    summary="Get Autonomous Follow-Up Status",
    dependencies=[Depends(verify_api_key)],
)
def get_autonomous_followup_status():
    return LAST_FOLLOWUP_STATUS


@app.post(
    "/workflows/autonomous-followup/trigger",
    summary="Run Autonomous Follow-Up Scan Now",
    dependencies=[Depends(verify_api_key)],
)
async def trigger_autonomous_followup():
    global LAST_FOLLOWUP_STATUS
    now_iso = datetime.datetime.now().isoformat()
    try:
        result = await run_autonomous_followup()
    except Exception as exc:
        LAST_FOLLOWUP_STATUS = {
            "last_run_time": now_iso,
            "success": False,
            "scanned_goal_count": 0,
            "created_event_ids": [],
            "generated_decision_ids": [],
            "resolved_event_ids": [],
            "errors": [str(exc)],
            "message": f"Manual autonomous follow-up scan crashed: {exc}",
        }
        raise HTTPException(status_code=502, detail=str(exc))

    LAST_FOLLOWUP_STATUS = {
        "last_run_time": now_iso,
        "success": result.get("success", False),
        "scanned_goal_count": result.get("scanned_goal_count", 0),
        "created_event_ids": result.get("created_event_ids", []),
        "generated_decision_ids": result.get("generated_decision_ids", []),
        "resolved_event_ids": result.get("resolved_event_ids", []),
        "errors": result.get("errors", []),
        "message": "Manual autonomous follow-up scan completed.",
    }
    return result


@app.get(
    "/followups/open",
    summary="List Open Follow-Up Items",
    dependencies=[Depends(verify_api_key)],
)
def list_open_followups(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return get_followup_events(statuses=("open",), limit=limit, offset=offset)


@app.get(
    "/followups/history",
    summary="List Follow-Up History",
    dependencies=[Depends(verify_api_key)],
)
def list_followup_history(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return get_followup_events(limit=limit, offset=offset)


@app.post(
    "/followups/{event_id}/resolve",
    summary="Resolve Follow-Up Item",
    dependencies=[Depends(verify_api_key)],
)
def resolve_followup(event_id: int):
    current = get_followup_event(event_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Follow-up event not found.")
    if not transition_followup_event_status(event_id, "resolved", ("open",)):
        raise HTTPException(status_code=409, detail="Follow-up event is not open.")
    return {"event_id": event_id, "status": "resolved"}


@app.post(
    "/followups/{event_id}/dismiss",
    summary="Dismiss Follow-Up Item",
    dependencies=[Depends(verify_api_key)],
)
def dismiss_followup(event_id: int):
    current = get_followup_event(event_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Follow-up event not found.")
    if not transition_followup_event_status(event_id, "dismissed", ("open",)):
        raise HTTPException(status_code=409, detail="Follow-up event is not open.")
    return {"event_id": event_id, "status": "dismissed"}


# ===================================================================
# COMPANY GOALS / MISSIONS
# ===================================================================

@app.post(
    "/goals",
    summary="Create Company Goal",
    dependencies=[Depends(verify_api_key)],
)
def create_goal(request: GoalCreateRequest):
    try:
        goal_id = create_company_goal(
            title=request.title,
            description=request.description,
            success_criteria=request.success_criteria,
            priority=request.priority,
            target_date=request.target_date,
            status=request.status,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return get_company_goal(goal_id)


@app.get(
    "/goals",
    summary="List Company Goals",
    dependencies=[Depends(verify_api_key)],
)
def list_goals(
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    statuses = (status,) if status else None
    try:
        return get_company_goals(statuses=statuses, limit=limit, offset=offset)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get(
    "/goals/{goal_id}",
    summary="Get Company Goal",
    dependencies=[Depends(verify_api_key)],
)
def read_goal(goal_id: int):
    goal = get_company_goal(goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found.")
    return goal


@app.patch(
    "/goals/{goal_id}",
    summary="Edit Company Goal",
    dependencies=[Depends(verify_api_key)],
)
def patch_goal(goal_id: int, request: GoalUpdateRequest):
    payload = request.model_dump(exclude_none=True)
    try:
        updated = update_company_goal(goal_id, **payload)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if updated is None:
        raise HTTPException(status_code=404, detail="Goal not found.")
    return updated


@app.post(
    "/goals/{goal_id}/status",
    summary="Transition Company Goal Status",
    dependencies=[Depends(verify_api_key)],
)
def change_goal_status(goal_id: int, request: GoalStatusRequest):
    try:
        updated = transition_company_goal_status(
            goal_id,
            request.status,
            request.completion_note,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if updated is None:
        raise HTTPException(status_code=404, detail="Goal not found.")
    return updated


@app.get(
    "/goals/{goal_id}/lineage",
    summary="Get Goal-to-Outcome Lineage",
    dependencies=[Depends(verify_api_key)],
)
def read_goal_lineage(goal_id: int):
    lineage = get_company_goal_lineage(goal_id)
    if lineage is None:
        raise HTTPException(status_code=404, detail="Goal not found.")
    return lineage


@app.get(
    "/meeting-types",
    summary="List Executive Meeting Types",
    dependencies=[Depends(verify_api_key)],
)
def list_meeting_types():
    return {
        key: {
            "label": value["label"],
            "default_agents": value["default_agents"],
            "required_agents": value["required_agents"],
            "evidence_focus": value["evidence_focus"],
            "output_contract": value["output_contract"],
            "approval_posture": value["approval_posture"],
        }
        for key, value in MEETING_TYPES.items()
    }


@app.post(
    "/decisions/trigger",
    response_model=DecisionResponse,
    summary="Trigger Ad-Hoc Executive Decision",
    dependencies=[Depends(verify_api_key)],
)
def trigger_ad_hoc_decision(request: DecisionRequest):
    """Start een ad-hoc overleg tussen geselecteerde agenten en slaat het besluit op."""
    goal = None
    meeting_task = request.task_description
    try:
        resolved_agent_keys = resolve_meeting_agents(
            request.meeting_type,
            request.agent_keys,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if request.goal_id is not None:
        goal = get_company_goal(request.goal_id)
        if goal is None:
            raise HTTPException(status_code=404, detail="Goal not found.")
        if goal["status"] != "active":
            raise HTTPException(
                status_code=409,
                detail=f"Goal must be active before decisions can be linked to it (currently '{goal['status']}').",
            )
        meeting_task = (
            f"COMPANY GOAL #{goal['id']}: {goal['title']}\n"
            f"Mission: {goal['description']}\n"
            f"Success criteria: {goal['success_criteria']}\n"
            f"Priority: {goal['priority']}\n"
            f"Target date: {goal.get('target_date') or 'none'}\n\n"
            f"DECISION TASK:\n{request.task_description}\n\n"
            "Keep the recommendation explicitly aligned to the company goal. "
            "Do not claim the goal is complete; goal completion remains an owner decision."
        )

    try:
        meeting_result = run_executive_meeting(
            topic=request.topic,
            task_description=meeting_task,
            agent_keys=resolved_agent_keys,
            # Decision meetings are reasoning-only. Tool-capable agents belong
            # in the separate preparation/execution phase after human approval.
            agents_source=EXECUTIVE_AGENTS_NO_TOOLS,
            memory_context={
                "enabled": True,
                "goal_id": request.goal_id,
                "limit": 5,
            },
            meeting_type=request.meeting_type,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid meeting request: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Meeting execution failed: {e}",
        )

    final_decision = meeting_result.get("final_decision", "")
    participants = meeting_result.get("participants", [])

    db_id = log_decision(
        topic=request.topic,
        agents_involved=participants,
        task_description=request.task_description,
        decision_outcome=final_decision,
        sandbox_mode=config.SANDBOX_MODE,
        goal_id=request.goal_id,
        meeting_type=request.meeting_type,
    )

    try:
        snippet = final_decision[:200]
        message = f"📌 <b>Ad-Hoc Decision Triggered</b>\n\n<b>Topic:</b> {escape_html(request.topic)}\n\n<b>Decision Snippet:</b>\n{escape_html(snippet)}..."
        send_notification(message)
    except Exception as notify_err:
        print(f"Waarschuwing: Telegram notificatie kon niet worden verzonden: {notify_err}")

    return DecisionResponse(
        database_id=db_id,
        topic=request.topic,
        meeting_type=request.meeting_type,
        goal_id=request.goal_id,
        final_decision=final_decision,
        participants=participants,
        individual_outputs=meeting_result.get("individual_outputs", {}),
        quality_warnings=meeting_result.get("quality_warnings", {}),
    )


@app.post(
    "/decisions/{decision_id}/approve",
    summary="Approve Executive Decision Direction",
    dependencies=[Depends(verify_api_key)],
)
def approve_decision(decision_id: int):
    """Human approval gate voor de strategische richting van een beslissing."""
    decision = get_decision_by_id(decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="Decision not found.")

    _require_linked_goal_active(
        decision,
        goal_id_key="goal_id",
        operation="approve decision direction",
    )

    if not transition_decision_approval(decision_id, "approved", ("pending",)):
        current = get_decision_by_id(decision_id)
        raise HTTPException(
            status_code=409,
            detail=(
                "Decision cannot be approved from its current state "
                f"(approval={current.get('approval_status') if current else 'unknown'}, "
                f"preparation={current.get('preparation_status') if current else 'unknown'})."
            ),
        )

    try:
        send_notification(
            f"✅ <b>DECISION APPROVED</b>\n\n"
            f"<b>Decision ID:</b> #{decision_id}\n"
            f"<b>Topic:</b> {escape_html(decision['topic'])}\n\n"
            "The decision is now eligible for the separate preparation phase."
        )
    except Exception as notify_err:
        logger.warning(f"Decision approval notification failed: {notify_err}")

    try:
        create_decision_memories(decision_id, "approved")
    except Exception as memory_err:
        logger.warning(f"Decision approval memory creation failed: {memory_err}")

    return {
        "decision_id": decision_id,
        "approval_status": "approved",
        "preparation_status": "not_started",
    }


@app.post(
    "/decisions/{decision_id}/reject",
    summary="Reject Executive Decision Direction",
    dependencies=[Depends(verify_api_key)],
)
def reject_decision(decision_id: int):
    """Reject een beslissing voordat preparation is gestart/voltooid."""
    decision = get_decision_by_id(decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="Decision not found.")

    if not transition_decision_approval(decision_id, "rejected", ("pending", "approved")):
        current = get_decision_by_id(decision_id)
        raise HTTPException(
            status_code=409,
            detail=(
                "Decision cannot be rejected from its current state "
                f"(approval={current.get('approval_status') if current else 'unknown'}, "
                f"preparation={current.get('preparation_status') if current else 'unknown'})."
            ),
        )

    try:
        send_notification(
            f"❌ <b>DECISION REJECTED</b>\n\n"
            f"<b>Decision ID:</b> #{decision_id}\n"
            f"<b>Topic:</b> {escape_html(decision['topic'])}"
        )
    except Exception as notify_err:
        logger.warning(f"Decision rejection notification failed: {notify_err}")

    try:
        create_decision_memories(decision_id, "rejected")
    except Exception as memory_err:
        logger.warning(f"Decision rejection memory creation failed: {memory_err}")

    return {"decision_id": decision_id, "approval_status": "rejected"}


@app.post(
    "/decisions/{decision_id}/prepare",
    response_model=PreparationResponse,
    summary="Prepare an Approved Decision for Execution",
    dependencies=[Depends(verify_api_key)],
)
def prepare_approved_decision(decision_id: int, request: PreparationRequest):
    """
    Phase 2: laat tool-capable executives een GOEDGEKEURDE strategische
    beslissing vertalen naar concrete voorbereiding/action proposals en
    structured resource requests. Niets wordt direct uitgevoerd of verleend.
    """
    decision = get_decision_by_id(decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="Decision not found.")
    if decision["approval_status"] != "approved":
        raise HTTPException(
            status_code=409,
            detail=f"Decision must be approved before preparation (currently '{decision['approval_status']}').",
        )

    if decision.get("goal_id") is not None:
        goal = get_company_goal(decision["goal_id"])
        if goal is None:
            raise HTTPException(
                status_code=409,
                detail="Decision references a goal that no longer exists.",
            )
        if goal["status"] != "active":
            raise HTTPException(
                status_code=409,
                detail=(
                    "Linked company goal must remain active before preparation "
                    f"(currently '{goal['status']}')."
                ),
            )
    else:
        goal = None

    if not claim_decision_for_preparation(decision_id):
        current = get_decision_by_id(decision_id)
        raise HTTPException(
            status_code=409,
            detail=(
                "Decision preparation could not be claimed "
                f"(current preparation status: '{current.get('preparation_status') if current else 'unknown'}')."
            ),
        )

    trusted_browser_context = "\n".join(
        part
        for part in (
            decision.get("task_description"),
            decision.get("decision_outcome"),
            goal.get("description") if goal else None,
            goal.get("success_criteria") if goal else None,
        )
        if part
    )
    allowed_browser_urls = set(
        re.findall(r'https?://[^\s<>"\')\]}]+', trusted_browser_context)
    )

    preparation_prompt = (
        f"PHASE 2 — PREPARATION FOR APPROVED DECISION #{decision_id}\n\n"
        f"Original topic: {decision['topic']}\n\n"
        f"Original evidence/task:\n{decision['task_description']}\n\n"
        f"Human-approved strategic direction:\n{decision['decision_outcome']}\n\n"
        + (
            f"Linked company goal: {goal['title']}\n"
            f"Goal success criteria: {goal['success_criteria']}\n"
            f"Goal priority: {goal['priority']}\n"
            f"Goal target date: {goal.get('target_date') or 'none'}\n\n"
            if goal else ""
        )
        + "Your job is NOT to re-decide whether the direction should happen. "
        "Translate the approved direction into a concrete, safe preparation plan. "
        "Identify required resources, access, credentials, plugins, data, files, "
        "browser steps, or commands. If a concrete action is genuinely needed and "
        "your role has an appropriate propose_* tool, you MAY propose it for human "
        "review. IMPORTANT: if you decide a proposal is needed, CALL the actual tool. "
        "Do not print, imitate, or describe a JSON/function-call payload in your answer. "
        "A textual pseudo-call is invalid and will fail preparation verification. "
        "Never claim a proposed action has executed. For every action you actually "
        "propose, include an expected_outcome and expected_impact so we can measure "
        "whether it worked later. Include expected_cost_amount + currency ONLY when "
        "the supplied evidence supports a real cost; otherwise leave cost unknown. "
        "Never invent access or credentials we do not have. Never invent a domain or URL. "
        "A browser action may only target an exact URL already present in the trusted "
        "task/evidence, approved decision, or linked goal context; otherwise request the "
        "missing exact URL/resource from the owner. For every missing resource "
        "or capability that genuinely blocks the approved plan, CALL "
        "propose_resource_request so the owner receives a structured request. For a "
        "non-budget request, OMIT amount and currency. For a budget request whose amount "
        "is unknown, OMIT amount and currency — NEVER send strings such as 'Unknown — "
        "evidence required' into numeric/currency fields. Do not put passwords, API keys, "
        "tokens, or secret values in any tool field. Merely listing a missing capability "
        "in prose or printing a JSON object is not a structured request. Minimize actions: "
        "do not propose anything that is not necessary to prepare the approved direction."
    )

    def _run_preparation_meeting(task_text: str):
        return run_executive_meeting(
            topic=f"Preparation for Decision #{decision_id}",
            task_description=task_text,
            agent_keys=request.agent_keys,
            agents_source=EXECUTIVE_AGENTS,
            # Only the ORIGINAL task/evidence is evidence for quantitative
            # validation. The approved recommendation is direction, not proof.
            evidence_text=decision["task_description"],
            provenance_context={
                "decision_id": decision_id,
                "decision_sync_uuid": decision["sync_uuid"],
                "phase": "preparation",
                "allowed_browser_urls": sorted(allowed_browser_urls),
            },
            memory_context={
                "enabled": True,
                "goal_id": decision.get("goal_id"),
                "limit": 5,
            },
            meeting_type="planning",
        )

    def _load_created_items(meeting_result: dict):
        action_ids = meeting_result.get("proposed_action_ids", [])
        resource_ids = meeting_result.get("proposed_resource_request_ids", [])
        actions = [
            action
            for action_id in action_ids
            if (action := get_action_by_id(action_id)) is not None
        ]
        resources = [
            resource
            for request_id in resource_ids
            if (resource := get_resource_request_by_id(request_id)) is not None
        ]
        return action_ids, resource_ids, actions, resources

    def _provenance_mismatches(action_ids, resource_ids, actions, resources):
        provenance_mismatches = [
            action for action in actions
            if (
                action.get("source_decision_id") != decision_id
                or action.get("source_decision_sync_uuid") != decision["sync_uuid"]
                or action.get("source_phase") != "preparation"
            )
        ]
        if len(actions) != len(action_ids):
            provenance_mismatches.append(
                {"error": "Created action ID missing from database"}
            )

        resource_provenance_mismatches = [
            resource for resource in resources
            if (
                resource.get("source_decision_id") != decision_id
                or resource.get("source_decision_sync_uuid") != decision["sync_uuid"]
                or resource.get("source_phase") != "preparation"
            )
        ]
        if len(resources) != len(resource_ids):
            resource_provenance_mismatches.append(
                {"error": "Created resource request ID missing from database"}
            )

        return provenance_mismatches, resource_provenance_mismatches

    def _extract_resource_request_payloads(text: str) -> list[dict]:
        """
        Strictly extracts ONLY printed propose_resource_request dictionaries.
        This fallback exists for models that expose valid tools but print a
        function payload instead of invoking it. Executable action tools are
        deliberately unsupported here.
        """
        allowed_top = {"name", "parameters"}
        allowed_params = {
            "resource_type", "resource_name", "reason", "required_for",
            "amount", "currency",
        }
        parsed_payloads: list[dict] = []
        seen: set[tuple] = set()

        for start_index, char in enumerate(text):
            if char != "{":
                continue

            depth = 0
            in_string = False
            escaped = False
            end_index = None

            for idx in range(start_index, len(text)):
                current = text[idx]
                if in_string:
                    if escaped:
                        escaped = False
                    elif current == "\\":
                        escaped = True
                    elif current == '"':
                        in_string = False
                    continue

                if current == '"':
                    in_string = True
                elif current == "{":
                    depth += 1
                elif current == "}":
                    depth -= 1
                    if depth == 0:
                        end_index = idx + 1
                        break

            if end_index is None:
                continue

            candidate = text[start_index:end_index]
            try:
                value = json.loads(candidate)
            except Exception:
                try:
                    value = ast.literal_eval(candidate)
                except Exception:
                    continue

            if (
                not isinstance(value, dict)
                or value.get("name") != "propose_resource_request"
                or set(value.keys()) - allowed_top
            ):
                continue

            params = value.get("parameters")
            if not isinstance(params, dict) or set(params.keys()) - allowed_params:
                continue
            if not {"resource_type", "resource_name", "reason"}.issubset(params):
                continue

            resource_type = params.get("resource_type")
            resource_name = params.get("resource_name")
            reason = params.get("reason")
            required_for = params.get("required_for")
            amount = params.get("amount")
            currency = params.get("currency")

            if not all(isinstance(v, str) and v.strip() for v in (
                resource_type, resource_name, reason
            )):
                continue
            if required_for is not None and not isinstance(required_for, str):
                continue
            if amount is not None and not isinstance(amount, (int, float)):
                continue
            if currency is not None and not isinstance(currency, str):
                continue

            normalized = {
                "resource_type": resource_type.strip(),
                "resource_name": resource_name.strip(),
                "reason": reason.strip(),
                "required_for": required_for.strip() if isinstance(required_for, str) else None,
                "amount": amount,
                "currency": currency.strip() if isinstance(currency, str) else None,
            }
            dedupe_key = (
                normalized["resource_type"],
                normalized["resource_name"].lower(),
                normalized["reason"].lower(),
                normalized["required_for"],
                normalized["amount"],
                normalized["currency"],
            )
            if dedupe_key not in seen:
                seen.add(dedupe_key)
                parsed_payloads.append(normalized)

        return parsed_payloads


    def _materialize_resource_requests_from_text(text: str) -> list[int]:
        payloads = _extract_resource_request_payloads(text)
        if not payloads:
            return []

        created_ids: list[int] = []
        requested_by = (
            request.agent_keys[0].upper()
            if len(request.agent_keys) == 1
            else "PREPARATION"
        )

        # Re-enter the same trusted provenance scope only while writing these
        # NON-EXECUTING, owner-gated requests. Existing DB validation still
        # rejects secret-like values, invalid resource types, and malformed money.
        with action_provenance_scope(
            decision_id,
            decision["sync_uuid"],
            "preparation",
        ):
            for payload in payloads:
                created_ids.append(
                    propose_resource_request(
                        requested_by=requested_by,
                        resource_type=payload["resource_type"],
                        resource_name=payload["resource_name"],
                        reason=payload["reason"],
                        required_for=payload["required_for"],
                        amount=payload["amount"],
                        currency=payload["currency"],
                    )
                )

        return created_ids


    try:
        meeting_result = _run_preparation_meeting(preparation_prompt)
        participants = meeting_result.get("participants", [])
        final_plan = meeting_result.get("final_decision", "")
        proposed_action_ids, proposed_resource_request_ids, new_actions, new_resource_requests = (
            _load_created_items(meeting_result)
        )

        provenance_mismatches, resource_provenance_mismatches = _provenance_mismatches(
            proposed_action_ids,
            proposed_resource_request_ids,
            new_actions,
            new_resource_requests,
        )
        if provenance_mismatches:
            finish_decision_preparation(
                decision_id,
                False,
                "Preparation failed provenance verification; orphan/mismatched action detected.",
            )
            raise HTTPException(
                status_code=502,
                detail=(
                    "Preparation created an action without the expected decision provenance. "
                    "Preparation was marked failed; do not approve the orphan action."
                ),
            )
        if resource_provenance_mismatches:
            finish_decision_preparation(
                decision_id,
                False,
                "Preparation failed provenance verification; orphan/mismatched resource request detected.",
            )
            raise HTTPException(
                status_code=502,
                detail=(
                    "Preparation created a resource request without the expected decision provenance. "
                    "Preparation was marked failed; do not fulfill the orphan request."
                ),
            )

        pseudo_resource_call = bool(
            re.search(
                r'(?is)(?:"name"\s*:\s*"propose_resource_request"|'
                r'\bpropose_resource_request\s*\()',
                final_plan,
            )
        )
        pseudo_action_call = bool(
            re.search(
                r'(?is)(?:"name"\s*:\s*"propose_(?:action|file_operation|browser_action)"|'
                r'\bpropose_(?:action|file_operation|browser_action)\s*\()',
                final_plan,
            )
        )
        # Compatibility alias retained for the original Phase 2 regression guard.
        pseudo_tool_call = bool(pseudo_action_call or pseudo_resource_call)

        # One narrow compatibility retry for NON-EXECUTING resource requests.
        # Printed JSON is never parsed into a request; a real tool invocation is required.
        if pseudo_resource_call and not (new_actions or new_resource_requests):
            retry_prompt = (
                preparation_prompt
                + "\n\nCOMPATIBILITY RETRY — YOUR PREVIOUS RESPONSE WAS INVALID. "
                "You printed propose_resource_request JSON instead of invoking the tool. "
                "Do not print any function-call JSON. Invoke propose_resource_request NOW "
                "for each genuinely blocking resource. For access/credential/plugin/data/"
                "service/hardware/other requests, omit amount and currency entirely. "
                "For an unknown budget amount, also omit amount and currency. After the "
                "real tool call succeeds, summarize the created request IDs in prose."
            )
            meeting_result = _run_preparation_meeting(retry_prompt)
            participants = meeting_result.get("participants", [])
            final_plan = meeting_result.get("final_decision", "")
            proposed_action_ids, proposed_resource_request_ids, new_actions, new_resource_requests = (
                _load_created_items(meeting_result)
            )

            retry_action_mismatch, retry_resource_mismatch = _provenance_mismatches(
                proposed_action_ids,
                proposed_resource_request_ids,
                new_actions,
                new_resource_requests,
            )
            if retry_action_mismatch or retry_resource_mismatch:
                finish_decision_preparation(
                    decision_id,
                    False,
                    "Resource compatibility retry failed provenance verification.",
                )
                raise HTTPException(
                    status_code=502,
                    detail="Resource compatibility retry created mismatched provenance.",
                )

            pseudo_resource_call = bool(
                re.search(
                    r'(?is)(?:"name"\s*:\s*"propose_resource_request"|'
                    r'\bpropose_resource_request\s*\()',
                    final_plan,
                )
            )
            pseudo_action_call = bool(
                re.search(
                    r'(?is)(?:"name"\s*:\s*"propose_(?:action|file_operation|browser_action)"|'
                    r'\bpropose_(?:action|file_operation|browser_action)\s*\()',
                    final_plan,
                )
            )
            pseudo_tool_call = bool(pseudo_action_call or pseudo_resource_call)

        if pseudo_resource_call and not new_resource_requests:
            materialized_resource_ids = _materialize_resource_requests_from_text(final_plan)
            if materialized_resource_ids:
                proposed_resource_request_ids = materialized_resource_ids
                new_resource_requests = [
                    resource_request
                    for request_id in materialized_resource_ids
                    if (
                        resource_request := get_resource_request_by_id(request_id)
                    ) is not None
                ]
                _, resource_provenance_mismatches = _provenance_mismatches(
                    [],
                    proposed_resource_request_ids,
                    [],
                    new_resource_requests,
                )
                if resource_provenance_mismatches:
                    finish_decision_preparation(
                        decision_id,
                        False,
                        "Materialized resource request failed provenance verification.",
                    )
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            "Materialized resource request had invalid decision provenance. "
                            "Preparation was marked failed."
                        ),
                    )
                pseudo_resource_call = False

        if (
            (pseudo_action_call and not new_actions)
            or (pseudo_resource_call and not new_resource_requests)
        ):
            finish_decision_preparation(
                decision_id,
                False,
                (
                    "Preparation failed verification: an executive printed a "
                    "tool-call imitation but no matching real proposal/request was created."
                ),
            )
            raise HTTPException(
                status_code=502,
                detail=(
                    "Preparation agent described/printed a propose_* tool call without "
                    "actually invoking the tool. No matching proposal/request was created, "
                    "so preparation was marked failed and is safe to retry."
                ),
            )

        finish_decision_preparation(decision_id, True, final_plan)
    except HTTPException:
        raise
    except ValueError as e:
        finish_decision_preparation(decision_id, False, None)
        raise HTTPException(status_code=400, detail=f"Invalid preparation request: {e}")
    except Exception as e:
        finish_decision_preparation(decision_id, False, None)
        raise HTTPException(status_code=502, detail=f"Preparation meeting failed: {e}")

    try:
        send_notification(
            f"🧭 <b>PREPARATION COMPLETE</b>\n\n"
            f"<b>Source decision:</b> #{decision_id}\n\n"
            "Any concrete actions and resource requests proposed by executives are "
            "still waiting for separate owner review."
        )
    except Exception as notify_err:
        logger.warning(f"Preparation completion notification failed: {notify_err}")

    return PreparationResponse(
        source_decision_id=decision_id,
        final_plan=final_plan,
        participants=participants,
        individual_outputs=meeting_result.get("individual_outputs", {}),
        quality_warnings=meeting_result.get("quality_warnings", {}),
    )


@app.get(
    "/resources/pending",
    summary="Get Pending Resource Requests",
    dependencies=[Depends(verify_api_key)],
)
def read_pending_resource_requests():
    return get_resource_requests(statuses=("pending", "approved"), limit=100)


@app.get(
    "/resources/history",
    summary="Get Resource Request History",
    dependencies=[Depends(verify_api_key)],
)
def read_resource_request_history(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return get_resource_requests(limit=limit, offset=offset)


@app.post(
    "/resources/{request_id}/approve",
    summary="Approve Resource Request",
    dependencies=[Depends(verify_api_key)],
)
def approve_resource_request(request_id: int):
    current = get_resource_request_by_id(request_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Resource request not found.")
    _require_linked_goal_active(
        current,
        goal_id_key="source_goal_id",
        operation="approve resource request",
    )
    if not transition_resource_request_status(request_id, "approved", ("pending",)):
        refreshed = get_resource_request_by_id(request_id)
        raise HTTPException(
            status_code=409,
            detail=f"Resource request cannot be approved from status '{refreshed.get('status') if refreshed else 'unknown'}'.",
        )
    return get_resource_request_by_id(request_id)


@app.post(
    "/resources/{request_id}/reject",
    summary="Reject Resource Request",
    dependencies=[Depends(verify_api_key)],
)
def reject_resource_request(request_id: int):
    current = get_resource_request_by_id(request_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Resource request not found.")
    if not transition_resource_request_status(request_id, "rejected", ("pending", "approved")):
        refreshed = get_resource_request_by_id(request_id)
        raise HTTPException(
            status_code=409,
            detail=f"Resource request cannot be rejected from status '{refreshed.get('status') if refreshed else 'unknown'}'.",
        )
    return get_resource_request_by_id(request_id)


@app.post(
    "/resources/{request_id}/fulfill",
    summary="Mark Resource Request Fulfilled",
    dependencies=[Depends(verify_api_key)],
)
def fulfill_resource_request(request_id: int, request: ResourceFulfillmentRequest):
    current = get_resource_request_by_id(request_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Resource request not found.")
    _require_linked_goal_active(
        current,
        goal_id_key="source_goal_id",
        operation="fulfill resource request",
    )
    try:
        fulfilled = transition_resource_request_status(
            request_id,
            "fulfilled",
            ("approved",),
            fulfillment_note=request.fulfillment_note,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not fulfilled:
        refreshed = get_resource_request_by_id(request_id)
        raise HTTPException(
            status_code=409,
            detail=(
                "Resource must be approved before it can be marked fulfilled "
                f"(current status '{refreshed.get('status') if refreshed else 'unknown'}')."
            ),
        )
    return get_resource_request_by_id(request_id)


@app.get(
    "/decisions/{decision_id}/lineage",
    summary="Get Decision-to-Outcome Lineage",
    description=(
        "Returns the full auditable chain for one decision: approval/preparation, "
        "all linked action proposals, execution state, and measured outcomes."
    ),
    dependencies=[Depends(verify_api_key)],
)
def read_decision_lineage(decision_id: int):
    lineage = get_decision_lineage(decision_id)
    if lineage is None:
        raise HTTPException(status_code=404, detail="Decision not found.")
    return lineage


# ===================================================================
# EXECUTIVE MEMORY
# ===================================================================

@app.get(
    "/memory/{executive_key}",
    summary="Get Structured Executive Memory",
    dependencies=[Depends(verify_api_key)],
)
def read_executive_memory(
    executive_key: str,
    active_only: bool = True,
    limit: int = Query(default=20, ge=1, le=100),
    goal_id: Optional[int] = None,
):
    if executive_key not in EXECUTIVE_AGENTS:
        raise HTTPException(status_code=404, detail="Executive role not found.")
    return get_executive_memories(
        executive_key,
        active_only=active_only,
        limit=limit,
        goal_id=goal_id,
    )


@app.post(
    "/memory/{memory_id}/status",
    summary="Activate or Deactivate Executive Memory",
    dependencies=[Depends(verify_api_key)],
)
def change_executive_memory_status(memory_id: int, request: ExecutiveMemoryStatusRequest):
    if not set_executive_memory_active(memory_id, request.active):
        raise HTTPException(status_code=404, detail="Executive memory not found.")
    return {"memory_id": memory_id, "active": request.active}


@app.get(
    "/decisions/history",
    summary="Get Decision History",
    description="Haalt de meest recente besluiten op uit de database met een instelbare limiet (maximaal 100).",
    dependencies=[Depends(verify_api_key)],
)
def get_decision_history(
    limit: int = Query(default=20, ge=1, le=100, description="Aantal op te halen besluiten (1-100)"),
    offset: int = Query(default=0, ge=0, description="Aantal over te slaan besluiten (voor paginering)"),
):
    """Retourneert een lijst van recent opgeslagen besluiten."""
    try:
        decisions = get_recent_decisions(limit=limit, offset=offset)
        return decisions
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Fout bij het ophalen van de besluthistorie: {str(e)}"
        )


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Vangt favicon-verzoeken op om 404-fouten in de serverlogs te voorkomen."""
    return Response(status_code=204)

# ===================================================================
# COMPANY TREASURY ENDPOINTS
# ===================================================================

@app.get(
    "/treasury/summary",
    summary="Get Company Treasury Summary",
    dependencies=[Depends(verify_api_key)],
)
def read_treasury_summary(currency: Optional[str] = None):
    try:
        return get_treasury_summary(currency)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get(
    "/treasury/history",
    summary="Get Treasury Ledger History",
    dependencies=[Depends(verify_api_key)],
)
def read_treasury_history(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return get_treasury_history(limit=limit, offset=offset)


@app.post(
    "/treasury/fund",
    summary="Add Owner Funding to Treasury",
    description=(
        "Records owner-provided capital. This is an accounting entry only and "
        "does not move money or connect a bank account."
    ),
    dependencies=[Depends(verify_api_key)],
)
def fund_treasury(request: TreasuryFundingRequest):
    try:
        entry_id = add_treasury_entry(
            "funding",
            request.amount,
            request.currency,
            request.note or "Owner funding",
        )
        return {
            "entry_id": entry_id,
            "entry_type": "funding",
            "amount": request.amount,
            "currency": request.currency.strip().upper(),
            "treasury": get_treasury_summary(request.currency),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get(
    "/treasury/actions/{action_id}/reservation",
    summary="Get Action Treasury Reservation",
    dependencies=[Depends(verify_api_key)],
)
def read_action_treasury_reservation(action_id: int):
    action = get_action_by_id(action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found.")
    return {
        "action_id": action_id,
        "reservation": get_treasury_reservation_for_action(action_id),
    }


# ===================================================================
# SYSTEM ENDPOINTS
# ===================================================================

@app.get(
    "/system/sandbox-status",
    summary="Get Sandbox Mode Status",
    description="Retourneert de huidige sandbox-modus status van het systeem.",
    dependencies=[Depends(verify_api_key)],
)
def get_sandbox_status():
    """Geeft aan of het systeem in Sandbox Mode of Live Mode draait."""
    return {"sandbox_mode": config.SANDBOX_MODE}


@app.get(
    "/system/health",
    summary="Comprehensive Health Check",
    description="Verifieert daadwerkelijk of Ollama, de database en Telegram bereikbaar/geconfigureerd zijn — in tegenstelling tot de root '/', die alleen zegt dat de server zelf draait.",
    dependencies=[Depends(verify_api_key)],
)
def get_system_health():
    """Retourneert per-component gezondheidsstatus, plus algehele status en uptime."""
    ollama_ok, ollama_msg = check_ollama_reachable()
    db_ok, db_msg = check_database_writable()
    tg_ok, tg_msg = check_telegram_configured()
    pw_ok, pw_msg = check_playwright_browser_installed()
    tg_listener_ok, tg_listener_error = is_telegram_listener_alive()

    overall_ok = ollama_ok and db_ok  # Telegram/Playwright zijn optioneel, blokkeren 'healthy' niet

    return {
        "status": "healthy" if overall_ok else "degraded",
        "uptime_seconds": round(get_uptime_seconds(), 1),
        "sandbox_mode": config.SANDBOX_MODE,
        "components": {
            "ollama": {"ok": ollama_ok, "message": ollama_msg},
            "database": {"ok": db_ok, "message": db_msg},
            "telegram_configured": {"ok": tg_ok, "message": tg_msg},
            "telegram_listener_running": {"ok": tg_listener_ok, "message": tg_listener_error or "ok"},
            "playwright_browser": {"ok": pw_ok, "message": pw_msg},
        },
    }


@app.get(
    "/system/stats",
    summary="System Statistics",
    description="Aantallen beslissingen/acties, uitsplitsing per actiestatus, en het slaagpercentage van dagelijkse research.",
    dependencies=[Depends(verify_api_key)],
)
def get_stats():
    """Retourneert de systeemstatistieken uit de database, plus uptime."""
    stats = get_system_stats()
    stats["uptime_seconds"] = round(get_uptime_seconds(), 1)
    return stats


class OutcomeUpdateRequest(BaseModel):
    expected_outcome: Optional[str] = None
    expected_impact: Optional[str] = None
    expected_cost_amount: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    outcome_status: Optional[
        Literal["succeeded", "failed", "partial", "inconclusive"]
    ] = None
    actual_outcome: Optional[str] = None
    actual_impact: Optional[str] = None
    actual_cost_amount: Optional[float] = Field(default=None, ge=0)
    next_recommendation: Optional[str] = None
    notes: Optional[str] = None


class SandboxModeRequest(BaseModel):
    enabled: bool


@app.post(
    "/system/sandbox-mode",
    summary="Toggle Sandbox/Live Execution Mode",
    description=(
        "Zet SANDBOX_MODE aan of uit. Werkt onmiddellijk (geen herstart nodig) "
        "en schrijft de wijziging ook weg naar .env, zodat een herstart de "
        "instelling niet stilzwijgend terugdraait. Vervangt het handmatig "
        "openen van .env in een editor."
    ),
    dependencies=[Depends(verify_api_key)],
)
def toggle_sandbox_mode(request: SandboxModeRequest):
    """Schakelt tussen Sandbox en Live modus, en meldt de wijziging via Telegram."""
    set_sandbox_mode(request.enabled)

    mode_label = "SANDBOX" if request.enabled else "LIVE"
    try:
        if request.enabled:
            body = "Executions will now be simulated only — nothing real will run."
        else:
            body = "⚠️ Approved actions will now run for REAL on this machine."
        send_notification(f"🔧 <b>Execution mode changed to {mode_label}</b>\n\n{body}")
    except Exception as e:
        print(f"Warning: failed to send mode-change notification: {e}")

    return {"sandbox_mode": config.SANDBOX_MODE}


# Strikte whitelist: browser-actie-screenshots worden ALTIJD exact zo
# genoemd door workflows/action_executor.py (_execute_browser_action). Door
# de bestandsnaam tegen dit patroon te valideren voordat we hem in een pad
# gebruiken, is padtraversal (../../etc/passwd) door constructie onmogelijk —
# dit is geen algemene file-server, alleen deze ene, voorspelbare vorm mag door.
_SCREENSHOT_FILENAME_PATTERN = re.compile(r"^action_\d+\.png$")


@app.get(
    "/screenshots/{filename}",
    summary="Get Browser Action Screenshot",
    description="Serveert een screenshot die is opgeslagen door een uitgevoerde browser_action. Bestandsnaam moet exact het patroon action_<id>.png volgen.",
    dependencies=[Depends(verify_api_key)],
)
def get_screenshot(filename: str):
    """Retourneert de PNG-screenshot van een uitgevoerde browser-actie, indien aanwezig."""
    if not _SCREENSHOT_FILENAME_PATTERN.match(filename):
        raise HTTPException(status_code=400, detail="Invalid screenshot filename format.")

    workspace_root = os.path.realpath(os.path.expanduser(config.WORKSPACE_ROOT or "./workspace"))
    screenshots_root = os.path.realpath(os.path.join(workspace_root, "screenshots"))
    screenshot_path = os.path.realpath(os.path.join(screenshots_root, filename))

    try:
        if os.path.commonpath([screenshots_root, screenshot_path]) != screenshots_root:
            raise HTTPException(status_code=404, detail="Screenshot not found.")
    except ValueError:
        raise HTTPException(status_code=404, detail="Screenshot not found.")

    # Refuse symlinked screenshot files/directories. FileResponse would follow
    # symlinks, which could otherwise turn this endpoint into a local file read.
    if (
        not os.path.isdir(screenshots_root)
        or os.path.islink(os.path.join(workspace_root, "screenshots"))
        or os.path.islink(os.path.join(screenshots_root, filename))
        or not os.path.isfile(screenshot_path)
    ):
        raise HTTPException(status_code=404, detail="Screenshot not found.")

    return FileResponse(screenshot_path, media_type="image/png")


# ===================================================================
# ACTION APPROVAL QUEUE ENDPOINTS
# ===================================================================

@app.get(
    "/actions/pending",
    summary="Get Pending Action Proposals",
    description="Haalt alle voorgestelde acties op die wachten op menselijke goedkeuring.",
    dependencies=[Depends(verify_api_key)],
)
def read_pending_actions():
    """Retourneert een lijst van alle acties met status 'pending'."""
    return get_pending_actions()


@app.get(
    "/actions/history",
    summary="Get Full Action History",
    description="Haalt de meest recente acties op UIT ALLE statussen (inclusief afgehandelde/geblokkeerde), voor een volledig audit-overzicht — in tegenstelling tot /actions/pending, dat alleen nog-actiegevende items toont.",
    dependencies=[Depends(verify_api_key)],
)
def read_action_history(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = None,
):
    """Retourneert een lijst van de meest recente acties, ongeacht status (tenzij gefilterd)."""
    if status is not None:
        from memory.database import VALID_ACTION_STATUSES
        if status not in VALID_ACTION_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action status filter '{status}'.",
            )
    return get_action_history(limit, offset, status)


@app.get(
    "/actions/{action_id}/outcome",
    summary="Get Action Business Outcome",
    dependencies=[Depends(verify_api_key)],
)
def read_action_outcome(action_id: int):
    """Return the expected/actual business outcome separately from execution logs."""
    action = get_action_by_id(action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found.")
    outcome = get_action_outcome(action_id)
    if outcome is None:
        raise HTTPException(status_code=404, detail="Outcome record not found.")
    return outcome


@app.patch(
    "/actions/{action_id}/outcome",
    summary="Update Action Business Outcome",
    dependencies=[Depends(verify_api_key)],
)
def patch_action_outcome(action_id: int, request: OutcomeUpdateRequest):
    """
    Record expected or actual business results. Terminal outcome judgments are
    allowed only after a LIVE action reached a terminal execution state.
    """
    action = get_action_by_id(action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found.")

    payload = request.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(status_code=400, detail="No outcome fields supplied.")

    if "expected_cost_amount" in payload and action["status"] != "pending":
        raise HTTPException(
            status_code=409,
            detail=(
                "Expected cost can only be changed while an action is pending. "
                "Once approved, the treasury reservation is authoritative."
            ),
        )

    # currency serves two purposes in this endpoint:
    # - before approval it may set/change the expected-cost currency;
    # - after execution it may accompany actual_cost_amount, but it must match
    #   the already-approved/reserved currency and may not silently re-denominate it.
    if "currency" in payload and action["status"] != "pending":
        if "actual_cost_amount" not in payload:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Currency can only be changed while an action is pending. "
                    "After approval it may only accompany actual_cost_amount."
                ),
            )
        existing_currency = (action.get("currency") or "").strip().upper()
        supplied_currency = payload["currency"].strip().upper()
        if existing_currency and supplied_currency != existing_currency:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Actual cost currency must match the approved treasury currency "
                    f"({existing_currency})."
                ),
            )

    monetary_fields = {"expected_cost_amount", "actual_cost_amount"}
    if monetary_fields.intersection(payload) and not (
        payload.get("currency") or action.get("currency")
    ):
        raise HTTPException(
            status_code=400,
            detail="currency is required when recording a monetary amount.",
        )

    terminal_result_fields = {
        "outcome_status",
        "actual_outcome",
        "actual_impact",
        "actual_cost_amount",
        "next_recommendation",
    }
    if terminal_result_fields.intersection(payload):
        if action["status"] not in {"executed", "execution_failed", "blocked_dangerous"}:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Actual business outcomes can only be recorded after a live "
                    f"action reaches a terminal execution state; current status is '{action['status']}'."
                ),
            )
        if payload.get("outcome_status") and not (
            payload.get("actual_outcome") or action.get("actual_outcome")
        ):
            raise HTTPException(
                status_code=400,
                detail="actual_outcome is required when setting a terminal outcome status.",
            )

    try:
        updated = update_action_outcome_with_treasury(action_id, **payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if updated is None:
        raise HTTPException(status_code=404, detail="Outcome record not found.")

    if updated.get("outcome_status") in {"succeeded", "failed", "partial", "inconclusive"}:
        try:
            create_action_outcome_memories(action_id)
        except Exception as memory_err:
            logger.warning(f"Action outcome memory creation failed: {memory_err}")

    return updated


@app.post(
    "/actions/{action_id}/approve",
    summary="Approve Action Proposal",
    description="Keurt een voorgestelde actie goed op basis van het ID.",
    dependencies=[Depends(verify_api_key)],
)
def approve_action(action_id: int):
    """Markeert een voorgestelde actie als 'approved'."""
    action = get_action_by_id(action_id)
    if action is None:
        raise HTTPException(status_code=404, detail=f"Action proposal with ID {action_id} not found.")

    try:
        return approve_action_control(action_id)
    except ActionControlError as e:
        current = get_action_by_id(action_id)
        if current is None:
            raise HTTPException(status_code=404, detail=str(e))
        detail = str(e)
        status_code = 409 if (
            "cannot be approved" in detail.lower()
            or "insufficient available treasury funds" in detail.lower()
            or "race" in detail.lower()
            or "linked company goal" in detail.lower()
        ) else 400
        raise HTTPException(status_code=status_code, detail=detail)


@app.post(
    "/actions/{action_id}/reject",
    summary="Reject Action Proposal",
    description="Wijst een voorgestelde actie af op basis van het ID.",
    dependencies=[Depends(verify_api_key)],
)
def reject_action(action_id: int):
    """Markeert een voorgestelde actie als 'rejected'."""
    action = get_action_by_id(action_id)
    if action is None:
        raise HTTPException(status_code=404, detail=f"Action proposal with ID {action_id} not found.")

    try:
        return reject_action_control(action_id)
    except ActionControlError as e:
        current = get_action_by_id(action_id)
        if current is None:
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=409, detail=str(e))
@app.post(
    "/actions/{action_id}/execute",
    summary="Execute Approved Action",
    dependencies=[Depends(verify_api_key)],
)
def execute_approved_action(action_id: int):
    """Voert een reeds goedgekeurde actie uit via het action_id."""
    action = get_action_by_id(action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")
    try:
        result = execute_action_control(action_id)
    except ActionControlError as e:
        detail = str(e)
        status_code = 409 if "linked company goal" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail)
    
    if not result.get("success", False):
        error_msg = result.get("error", "Execution failed")
        if error_msg == "Action not found":
            raise HTTPException(status_code=404, detail=error_msg)
        if "must be 'approved'" in error_msg or "could not be claimed for execution" in error_msg:
            raise HTTPException(status_code=409, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
        
    return result

if __name__ == "__main__":
    import uvicorn

    # BELANGRIJK: standaard 127.0.0.1 (alleen deze machine), NIET 0.0.0.0.
    # 0.0.0.0 maakt deze API bereikbaar voor ELK ander apparaat op hetzelfde
    # netwerk (bijv. een schoolnetwerk) — inclusief pogingen om de API-key
    # te brute-forcen vanaf een ander toestel. Alleen bewust overschrijven
    # via BIND_HOST in .env als je écht vanaf een ander apparaat op hetzelfde
    # netwerk bij het dashboard moet kunnen (en dan met extra voorzichtigheid).
    bind_host = config.BIND_HOST
    # Stable single-process default. For active development, run
    # "uvicorn main:app --reload" explicitly instead. Auto-reload can briefly
    # overlap workers, which is unsafe for the single Telegram poller.
    uvicorn.run("main:app", host=bind_host, port=8000, reload=False)