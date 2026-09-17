"""
main.py

Hoofdbestand voor de FastAPI applicatie van het AI Executive Team.
Beheert de API-endpoints en de geautomatiseerde (catch-up) achtergrondtaken.
"""

import datetime
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from memory.database import (
    init_db,
    get_recent_decisions,
    log_decision,
    get_pending_actions,
    update_action_status,
)
from workflows.daily_research import run_daily_research
from workflows.meeting import run_executive_meeting
from workflows.action_executor import execute_action
from notifications.telegram_bot import send_notification, escape_html
from config import config


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
    recent_decisions = get_recent_decisions(limit=5)
    today_date = datetime.date.today()

    for decision in recent_decisions:
        topic = decision.get("topic", "")
        timestamp_str = decision.get("timestamp")

        if topic.startswith("Daily Research") and timestamp_str:
            try:
                decision_date = datetime.datetime.fromisoformat(timestamp_str).date()
                if decision_date == today_date:
                    return True
            except (ValueError, TypeError):
                continue

    return False


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
    # Initialiseer de database
    init_db()

    # Gebruik AsyncIOScheduler voor asynchrone achtergrondtaken
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        scheduled_research_job,
        trigger=IntervalTrigger(minutes=15),
        id="daily_research_interval_job",
        replace_existing=True,
    )
    scheduler.start()
    app.state.scheduler = scheduler

    # Voer direct bij het opstarten één check/catch-up uit (asynchroon)
    await scheduled_research_job()

    yield

    # Sluit de scheduler netjes af bij het stoppen van de app
    app.state.scheduler.shutdown()


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
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 6. Pydantic Respons en Request Modellen
class DailyResearchResponse(BaseModel):
    success: bool
    database_id: Optional[int] = None
    research_summary: Optional[str] = None
    final_decision: Optional[str] = None
    message: Optional[str] = None


class DecisionRequest(BaseModel):
    topic: str
    task_description: str
    agent_keys: list[str] = ["cfo", "ceo"]


class DecisionResponse(BaseModel):
    database_id: int
    topic: str
    final_decision: str
    participants: list[str]
    individual_outputs: dict[str, str]


# --- API Key Beveiliging ---
def verify_api_key(x_api_key: str = Header(None)) -> bool:
    """
    Controleert of de ontvangen X-API-Key header overeenkomt met de geconfigureerde API_SECRET_KEY.
    Faalt standaard als er geen sleutel op de server is ingesteld (fail closed).
    """
    server_key = config.API_SECRET_KEY

    if not server_key or x_api_key != server_key:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API key",
        )
    return True


# 7. Endpoints
@app.get("/")
def read_root():
    return {"status": "online", "system": "AI Executive Team API"}


@app.get(
    "/workflows/daily-research/status",
    summary="Get Status of Last Daily Research Run",
    
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
        agents_involved=request.agent_keys,
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
        individual_outputs=meeting_result.get("individual_outputs", {}),  # <-- NIEUWE REGEL
    )


@app.get(
    "/decisions/history",
    summary="Get Decision History",
    description="Haalt de meest recente besluiten op uit de database met een instelbare limiet (maximaal 100).",
    
)
def get_decision_history(
    limit: int = Query(default=20, ge=1, le=100, description="Aantal op te halen besluiten (1-100)")
):
    """Retourneert een lijst van recent opgeslagen besluiten."""
    try:
        decisions = get_recent_decisions(limit=limit)
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
)
def get_sandbox_status():
    """Geeft aan of het systeem in Sandbox Mode of Live Mode draait."""
    return {"sandbox_mode": config.SANDBOX_MODE}

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


@app.post(
    "/actions/{action_id}/approve",
    summary="Approve Action Proposal",
    description="Keurt een voorgestelde actie goed op basis van het ID.",
    dependencies=[Depends(verify_api_key)],
)
def approve_action(action_id: int):
    """Markeert een voorgestelde actie als 'approved'."""
    success = update_action_status(action_id, "approved")
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Action proposal with ID {action_id} not found."
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
    success = update_action_status(action_id, "rejected")
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Action proposal with ID {action_id} not found."
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
            raise HTTPException(
                status_code=404,
                detail=error_msg
            )
        raise HTTPException(
            status_code=400,
            detail=error_msg
        )
        
    return result

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)