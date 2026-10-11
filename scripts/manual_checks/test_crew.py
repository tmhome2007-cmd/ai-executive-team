"""Run a local CEO/CFO demo against disposable records, with notifications disabled. Importing this manual check never initializes the app."""

import argparse
from pathlib import Path
import sys


def run_check():
    import privacy_bootstrap
    from crewai import Crew, Process, Task

    from agents.executive_agents import EXECUTIVE_AGENTS
    from config import config
    from memory.database import init_db, log_decision

    ceo_agent = EXECUTIVE_AGENTS.get("ceo")
    cfo_agent = EXECUTIVE_AGENTS.get("cfo")
    if not ceo_agent or not cfo_agent:
        raise ValueError(
            "CEO of CFO agent kon niet worden gevonden in EXECUTIVE_AGENTS."
        )
    topic_title = "Q4 Marketing Budget Request"
    task_prompt = "The marketing team has requested a $50,000 increase to the Q4 marketing budget to run a new paid acquisition campaign. Evaluate this request and provide a joint recommendation: approve, reject, or approve with conditions. Justify the decision."
    budget_request_task = Task(
        description=task_prompt,
        expected_output="A clear decision (approve/reject/approve with conditions) with 2-3 sentences of justification from both a strategic and financial perspective.",
        agent=ceo_agent,
    )
    executive_crew = Crew(
        agents=[ceo_agent, cfo_agent],
        tasks=[budget_request_task],
        process=Process.sequential,
        verbose=True,
    )
    print("\n" + "=" * 60)
    print("STARTING FICTIONAL LOCAL DEMO — DISPOSABLE RECORDS")
    print("=" * 60 + "\n")
    init_db()
    try:
        print("🤖 [1/3] AI Executive Team is aan het overleggen via Ollama...")
        result = executive_crew.kickoff()
        result_str = str(result)
        print("\n" + "=" * 60)
        print("EXECUTIVE TEAM DECISION RESULT:")
        print("=" * 60)
        print(result_str)
        print("=" * 60 + "\n")
        print("💾 [2/3] Beslissing opslaan in SQLite database...")
        record_id = log_decision(
            topic=topic_title,
            agents_involved=["CEO", "CFO"],
            task_description=task_prompt,
            decision_outcome=result_str,
            sandbox_mode=config.SANDBOX_MODE,
        )
        print(f"✅ Opgeslagen onder Database ID: {record_id}\n")
        print("[3/3] Telegram disabled; demo records are temporary.")
        print("✅ Workflow succesvol afgerond!")
        print("=" * 60 + "\n")
    except Exception:
        print("\n" + "!" * 60)
        print("FOUT TIJDENS HET UITVOEREN VAN DE WORKFLOW!")
        print("!" * 60 + "\n")
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-local",
        action="store_true",
        help="Opt in to this manual demo; never part of automated discovery.",
    )
    args = parser.parse_args(argv)
    if not args.run_local:
        parser.error("This demo requires --run-local; no application was initialized.")
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    from scripts.run_tests import disposable_environment

    with disposable_environment():
        run_check()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
