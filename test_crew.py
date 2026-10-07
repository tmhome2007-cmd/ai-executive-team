"""
test_crew.py

Integreert het AI Executive Team met de SQLite database en Telegram notificaties.
"""

import sys
from pathlib import Path
from crewai import Crew, Process, Task

# Zorg dat Python de hoofdmap en alle submappen kan vinden
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from agents.executive_agents import EXECUTIVE_AGENTS
from config import config
from memory.database import init_db, log_decision
from notifications.telegram_bot import send_notification, escape_html

# 1. Haal de CEO en CFO agenten op uit de geladen dictionary
ceo_agent = EXECUTIVE_AGENTS.get("ceo")
cfo_agent = EXECUTIVE_AGENTS.get("cfo")

if not ceo_agent or not cfo_agent:
    raise ValueError("CEO of CFO agent kon niet worden gevonden in EXECUTIVE_AGENTS.")

# 2. Definieer het onderwerp en de taakomschrijving
topic_title = "Q4 Marketing Budget Request"
task_prompt = (
    "The marketing team has requested a $50,000 increase to the Q4 marketing budget "
    "to run a new paid acquisition campaign. Evaluate this request and provide a joint "
    "recommendation: approve, reject, or approve with conditions. Justify the decision."
)

budget_request_task = Task(
    description=task_prompt,
    expected_output=(
        "A clear decision (approve/reject/approve with conditions) with 2-3 sentences of "
        "justification from both a strategic and financial perspective."
    ),
    agent=ceo_agent,
)

# 3. Stel de Crew samen
executive_crew = Crew(
    agents=[ceo_agent, cfo_agent],
    tasks=[budget_request_task],
    process=Process.sequential,
    verbose=True
)

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("STARTING FULL END-TO-END WORKFLOW TEST")
    print("=" * 60 + "\n")
    
    # Stap 1: Initialiseer de SQLite-database
    init_db()

    try:
        # Stap 2: Voer de CrewAI-discussie uit
        print("🤖 [1/3] AI Executive Team is aan het overleggen via Ollama...")
        result = executive_crew.kickoff()
        result_str = str(result)
        
        print("\n" + "=" * 60)
        print("EXECUTIVE TEAM DECISION RESULT:")
        print("=" * 60)
        print(result_str)
        print("=" * 60 + "\n")

        # Stap 3: Sla het resultaat op in de database
        print("💾 [2/3] Beslissing opslaan in SQLite database...")
        record_id = log_decision(
            topic=topic_title,
            agents_involved=["CEO", "CFO"],
            task_description=task_prompt,
            decision_outcome=result_str,
            sandbox_mode=config.SANDBOX_MODE
        )
        print(f"✅ Opgeslagen onder Database ID: {record_id}\n")

        # Stap 4: Stuur een Telegram-notificatie
        print("📱 [3/3] Telegram notificatie versturen...")
        telegram_message = (
            f"🏛 <b>AI Executive Team Decision</b>\n\n"
            f"<b>Topic:</b> {escape_html(topic_title)}\n"
            f"<b>Record ID:</b> #{record_id}\n"
            f"<b>Agents Involved:</b> CEO, CFO\n\n"
            f"<b>Outcome:</b>\n{escape_html(result_str)}"
        )
        send_notification(telegram_message)
        print("✅ Workflow succesvol afgerond!")
        print("=" * 60 + "\n")

    except Exception as e:
        print("\n" + "!" * 60)
        print("FOUT TIJDENS HET UITVOEREN VAN DE WORKFLOW!")
        print("!" * 60 + "\n")
        raise e
