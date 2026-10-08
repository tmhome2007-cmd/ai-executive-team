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
    get_latest_action_id,
    get_actions_after_id,
    get_action_outcome,
    update_action_outcome,
)
from workflows.daily_research import run_daily_research
from workflows.meeting import run_executive_meeting
from agents.executive_agents import EXECUTIVE_AGENTS, EXECUTIVE_AGENTS_NO_TOOLS
from workflows.action_executor import execute_action
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
        lambda: backup_database(keep_last=7),
        trigger=IntervalTrigger(hours=24),
        id="daily_database_backup_job",
        replace_existing=True,
    )
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("Scheduler started: immediate daily-research catch-up check + 15 min interval + daily DB backup (24h interval).")

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
    agent_keys: list[str] = Field(default_factory=lambda: ["cfo", "ceo"], min_length=1, max_length=11)


class DecisionResponse(BaseModel):
    database_id: int
    topic: str
    final_decision: str
    participants: list[str]
    individual_outputs: dict[str, str]
    quality_warnings: dict = Field(default_factory=dict)


class PreparationRequest(BaseModel):
    agent_keys: list[str] = Field(
        default_factory=lambda: ["coo", "cto", "ceo"],
        min_length=1,
        max_length=11,
    )


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

    attempts = [t for t in _failed_auth_attempts.get(client_ip, []) if now - t < _LOCKOUT_WINDOW_SECONDS]

    if len(attempts) >= _MAX_FAILED_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Too many failed authentication attempts. Try again later.",
        )

    server_key = config.API_SECRET_KEY
    is_valid = bool(server_key) and x_api_key is not None and hmac.compare_digest(x_api_key, server_key)

    if not is_valid:
        attempts.append(now)
        _failed_auth_attempts[client_ip] = attempts
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API key",
        )

    # Succesvolle poging: reset de teller voor dit IP.
    _failed_auth_attempts.pop(client_ip, None)
    return True


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


@app.post(
    "/decisions/trigger",
    response_model=DecisionResponse,
    summary="Trigger Ad-Hoc Executive Decision",
    dependencies=[Depends(verify_api_key)],
)
def trigger_ad_hoc_decision(request: DecisionRequest):
    """Start een ad-hoc overleg tussen geselecteerde agenten en slaat het besluit op."""
    try:
        meeting_result = run_executive_meeting(
            topic=request.topic,
            task_description=request.task_description,
            agent_keys=request.agent_keys,
            # Decision meetings are reasoning-only. Tool-capable agents belong
            # in the separate preparation/execution phase after human approval.
            agents_source=EXECUTIVE_AGENTS_NO_TOOLS,
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
    beslissing vertalen naar concrete voorbereiding/action proposals.
    De tools voeren niets direct uit: elk voorstel blijft in action_queue en
    vereist daarna nog steeds afzonderlijke menselijke Approve + Execute.
    """
    decision = get_decision_by_id(decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="Decision not found.")
    if decision["approval_status"] != "approved":
        raise HTTPException(
            status_code=409,
            detail=f"Decision must be approved before preparation (currently '{decision['approval_status']}').",
        )

    if not claim_decision_for_preparation(decision_id):
        current = get_decision_by_id(decision_id)
        raise HTTPException(
            status_code=409,
            detail=(
                "Decision preparation could not be claimed "
                f"(current preparation status: '{current.get('preparation_status') if current else 'unknown'}')."
            ),
        )

    preparation_prompt = (
        f"PHASE 2 — PREPARATION FOR APPROVED DECISION #{decision_id}\n\n"
        f"Original topic: {decision['topic']}\n\n"
        f"Original evidence/task:\n{decision['task_description']}\n\n"
        f"Human-approved strategic direction:\n{decision['decision_outcome']}\n\n"
        "Your job is NOT to re-decide whether the direction should happen. "
        "Translate the approved direction into a concrete, safe preparation plan. "
        "Identify required resources, access, credentials, plugins, data, files, "
        "browser steps, or commands. If a concrete action is genuinely needed and "
        "your role has an appropriate propose_* tool, you MAY propose it for human "
        "review. IMPORTANT: if you decide a proposal is needed, CALL the actual tool. "
        "Do not print, imitate, or describe a JSON/function-call payload in your answer. "
        "A textual pseudo-call is invalid and will fail preparation verification. "
        "Never claim a proposed action has executed. Never invent access or "
        "credentials we do not have. Missing capabilities must be listed explicitly "
        "as resource/access requests. Minimize actions: do not propose anything that "
        "is not necessary to prepare the approved direction."
    )

    try:
        action_snapshot_id = get_latest_action_id()

        meeting_result = run_executive_meeting(
            topic=f"Preparation for Decision #{decision_id}",
            task_description=preparation_prompt,
            agent_keys=request.agent_keys,
            agents_source=EXECUTIVE_AGENTS,
            # Only the ORIGINAL task/evidence is evidence for quantitative
            # validation. The approved recommendation is direction, not proof.
            evidence_text=decision["task_description"],
        )

        participants = meeting_result.get("participants", [])
        final_plan = meeting_result.get("final_decision", "")
        new_actions = get_actions_after_id(action_snapshot_id)

        # Some local models occasionally PRINT a function-call-shaped JSON
        # object instead of actually invoking the CrewAI tool. That must never
        # count as a successful preparation run: no DB action means no proposal
        # was really created and therefore no human approval gate exists.
        pseudo_tool_call = bool(
            re.search(
                r'(?is)(?:"name"\s*:\s*"propose_(?:action|file_operation|browser_action)"|'
                r'\bpropose_(?:action|file_operation|browser_action)\s*\()',
                final_plan,
            )
        )
        if pseudo_tool_call and not new_actions:
            finish_decision_preparation(
                decision_id,
                False,
                (
                    "Preparation failed verification: an executive printed a "
                    "tool-call imitation but no action proposal was actually "
                    "created in action_queue. Retry preparation."
                ),
            )
            raise HTTPException(
                status_code=502,
                detail=(
                    "Preparation agent described/printed a propose_* tool call "
                    "without actually invoking the tool. No action proposal was "
                    "created, so preparation was marked failed and is safe to retry."
                ),
            )

        finish_decision_preparation(decision_id, True, final_plan)
    except HTTPException:
        # Deliberate verification/API errors above already persisted the
        # appropriate preparation state and should keep their exact status/detail.
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
            "Any concrete actions proposed by executives are still waiting in "
            "the normal action approval queue."
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
    screenshot_path = os.path.join(workspace_root, "screenshots", filename)

    if not os.path.isfile(screenshot_path):
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
        updated = update_action_outcome(action_id, **payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if updated is None:
        raise HTTPException(status_code=404, detail="Outcome record not found.")
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

    success = transition_action_status(action_id, "approved", ("pending",))
    if not success:
        current = get_action_by_id(action_id)
        current_status = current["status"] if current else "unknown"
        raise HTTPException(
            status_code=409,
            detail=f"Action cannot be approved from status '{current_status}'.",
        )
    return {"action_id": action_id, "status": "approved"}


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

    success = transition_action_status(action_id, "rejected", ("pending", "approved"))
    if not success:
        current = get_action_by_id(action_id)
        current_status = current["status"] if current else "unknown"
        raise HTTPException(
            status_code=409,
            detail=f"Action cannot be rejected from status '{current_status}'.",
        )
    return {"action_id": action_id, "status": "rejected"}
@app.post(
    "/actions/{action_id}/execute",
    summary="Execute Approved Action",
    dependencies=[Depends(verify_api_key)],
)
def execute_approved_action(action_id: int):
    """Voert een reeds goedgekeurde actie uit via het action_id."""
    result = execute_action(action_id)
    
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
    bind_host = os.getenv("BIND_HOST", "127.0.0.1")
    # Stable single-process default. For active development, run
    # "uvicorn main:app --reload" explicitly instead. Auto-reload can briefly
    # overlap workers, which is unsafe for the single Telegram poller.
    uvicorn.run("main:app", host=bind_host, port=8000, reload=False)