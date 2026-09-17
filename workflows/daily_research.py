"""
workflows/daily_research.py

Asynchrone workflow voor het uitvoeren van dagelijks onderzoek door de CSO,
gevolgd door een executive meeting, database-logging en een Telegram-notificatie.

BELANGRIJK — async ontwerp:
- CrewAI's kickoff_async() wordt gebruikt voor het research-gedeelte, zodat dit
  veilig werkt binnen de AsyncIOScheduler / FastAPI event loop.
- run_executive_meeting() (in workflows/meeting.py) is bewust SYNC gebleven,
  omdat die functie ook wordt gebruikt door de sync /decisions/trigger endpoint.
  Om "asyncio.run() cannot be called from a running event loop" te voorkomen
  wanneer we die sync functie vanuit deze async functie aanroepen, draaien we
  hem via asyncio.to_thread() in een aparte thread.
- send_notification_async() wordt rechtstreeks ge-awaited (niet de sync
  send_notification() wrapper), om dezelfde reden: de sync wrapper roept zelf
  asyncio.run() aan, wat crasht binnen een reeds actieve event loop.
"""

import asyncio

from crewai import Crew, Process, Task

from agents.executive_agents import EXECUTIVE_AGENTS
from tools.research_tool import PageReaderTool, reset_call_count, get_call_count
from workflows.meeting import run_executive_meeting
from memory.database import log_decision
from notifications.telegram_bot import send_notification_async, escape_html
from config import config

RESEARCH_SOURCES = [
    "https://en.wikipedia.org/wiki/Artificial_intelligence",
    "https://en.wikipedia.org/wiki/Technology_news",
    "https://en.wikipedia.org/wiki/Generative_artificial_intelligence",
]

MAX_RESEARCH_ATTEMPTS = 3
MEETING_AGENT_KEYS = ["cfo", "general_counsel", "coo", "ceo"]


async def _run_research_crew_once() -> str:
    """Runs the CSO research crew once (async) and returns the raw result text."""
    cso_agent = EXECUTIVE_AGENTS["cso"]
    tool_instance = PageReaderTool()

    task_description = (
        "You MUST call the 'read_web_page' tool individually for EACH of the "
        "following URLs, one at a time, before writing any summary. Do not "
        "answer from memory or prior knowledge under any circumstances.\n\n"
        + "\n".join([f"- {url}" for url in RESEARCH_SOURCES])
        + "\n\nAfter reading all pages, write a synthesis covering one notable "
        "point from each source and any common theme across them."
    )

    task = Task(
        description=task_description,
        expected_output=(
            "A synthesis with one notable point per source plus common themes, "
            "based strictly on the tool's returned content."
        ),
        agent=cso_agent,
        tools=[tool_instance],
    )

    crew = Crew(
        agents=[cso_agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )

    result = await crew.kickoff_async()
    return str(result)


async def run_daily_research() -> dict:
    """
    Voert de volledige dagelijkse workflow uit:
    research (met verificatie + retry) -> executive meeting -> logging -> notificatie.

    Retourneert altijd een dict met minimaal "success" en "database_id",
    en raist NOOIT een exception (wordt intern afgevangen), omdat dit ook
    vanuit een achtergrond-scheduler wordt aangeroepen.
    """
    try:
        research_summary = None

        for attempt in range(1, MAX_RESEARCH_ATTEMPTS + 1):
            reset_call_count()
            research_summary = await _run_research_crew_once()
            calls_made = get_call_count()

            if calls_made == len(RESEARCH_SOURCES):
                print(f"Attempt {attempt}/{MAX_RESEARCH_ATTEMPTS}: CSO made {calls_made}/{len(RESEARCH_SOURCES)} real tool calls — proceeding.")
                break
            else:
                print(f"Attempt {attempt}/{MAX_RESEARCH_ATTEMPTS}: CSO made {calls_made}/{len(RESEARCH_SOURCES)} real tool calls — retrying...")
                research_summary = None

        if research_summary is None:
            # All attempts failed verification — do NOT proceed to a meeting.
            db_id = log_decision(
                topic="Daily Research FAILED — Tool Verification",
                agents_involved=["CSO"],
                task_description="CSO failed to genuinely invoke the research tool after 3 attempts.",
                decision_outcome="No meeting was held. Manual review needed.",
                sandbox_mode=config.SANDBOX_MODE,
            )
            try:
                await send_notification_async(
                    "⚠️ <b>Daily Research FAILED</b>\n\nCSO could not verifiably complete "
                    "the research tool calls after 3 attempts. No meeting was held."
                )
            except Exception as notify_err:
                print(f"Warning: failed to send failure notification: {notify_err}")

            return {
                "success": False,
                "database_id": db_id,
                "error": "CSO failed to genuinely invoke the research tool after 3 attempts. No meeting was held.",
            }

        # Research succeeded — run the executive meeting.
        # run_executive_meeting is sync, so it runs in a worker thread to avoid
        # nested-event-loop conflicts.
        meeting_result = await asyncio.to_thread(
            run_executive_meeting,
            topic="Daily Research Findings",
            task_description=(
                f"Our CSO just completed daily market research and found the "
                f"following: {research_summary}. Discuss what — if anything — "
                f"we should act on based on these findings."
            ),
            agent_keys=MEETING_AGENT_KEYS,
        )

        db_id = log_decision(
            topic="Daily Research Findings",
            agents_involved=["CSO"] + [k.upper() for k in MEETING_AGENT_KEYS],
            task_description=research_summary,
            decision_outcome=meeting_result["final_decision"],
            sandbox_mode=config.SANDBOX_MODE,
        )

        try:
            snippet = meeting_result["final_decision"][:300]
            await send_notification_async(
                f"📊 <b>Daily Research Findings</b>\n\n{escape_html(snippet)}..."
            )
        except Exception as notify_err:
            print(f"Warning: failed to send success notification: {notify_err}")

        return {
            "success": True,
            "database_id": db_id,
            "research_summary": research_summary,
            "meeting_result": meeting_result,
        }

    except Exception as e:
        print(f"Daily research workflow crashed unexpectedly: {e}")
        return {
            "success": False,
            "database_id": None,
            "error": f"Unexpected crash: {e}",
        }


if __name__ == "__main__":
    import json

    result = asyncio.run(run_daily_research())
    print(json.dumps(result, indent=2, default=str))