"""
workflows/meeting.py

Module voor het uitvoeren van een sequentieel overleg tussen meerdere CrewAI executive agents.
Agents bouwen voort op elkaars antwoorden en leveren zowel een individuele als gezamenlijke uitkomst.
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import Any, Dict, List

from crewai import Crew, Process, Task

# Zorg ervoor dat de hoofdmap van het project bereikbaar is voor imports
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from agents.executive_agents import EXECUTIVE_AGENTS
from workflows.execution_lock import EXECUTION_LOCK


def run_executive_meeting(
    topic: str,
    task_description: str,
    agent_keys: List[str],
    agents_source: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Voert een sequentieel overleg uit tussen de gespecificeerde agents.

    Args:
        topic (str): Het onderwerp van het overleg.
        task_description (str): De specifieke vraag of beschrijving van de taak.
        agent_keys (List[str]): Lijst van rollen (bijv. ["cfo", "coo", "ceo"]) die deelnemen.
        agents_source (dict, optioneel): Welke agent-dictionary te gebruiken om
            de keys op te zoeken. Standaard EXECUTIVE_AGENTS (volledig getoold).
            Geef bijv. EXECUTIVE_AGENTS_NO_TOOLS mee voor een meeting waar
            GEEN enkele deelnemer real-world tools mag kunnen aanroepen —
            zoals de geautomatiseerde dagelijkse research-meeting.

    Returns:
        Dict[str, Any]: Een dictionary met 'final_decision', 'participants' en 'individual_outputs'.
    """
    # --- Bestand: workflows/meeting.py ---

    if agents_source is None:
        agents_source = EXECUTIVE_AGENTS

    # 1. Validatie van de input
    if len(agent_keys) < 1:
        raise ValueError(
            f"Er moet minimaal 1 agent worden opgegeven. Ontvangen: {len(agent_keys)}"
        )

    missing_keys = [key for key in agent_keys if key not in agents_source]
    if missing_keys:
        raise ValueError(
            f"De volgende agent_keys bestaan niet in agents_source: {missing_keys}"
        )

    # === NIEUWE LOGICA: Zorg dat de CEO altijd als laatste synthetiseert ===
    if "ceo" in agent_keys and agent_keys[-1] != "ceo":
        agent_keys.remove("ceo")
        agent_keys.append("ceo")
        print(f"Reordered agent_keys so CEO synthesizes last: {agent_keys}")
    # ======================================================================

    tasks: List[Task] = []
    agent_instances = []

    # 2. Taken opbouwen in sequentiële volgorde
    for index, key in enumerate(agent_keys):
        agent_obj = agents_source[key]
        agent_instances.append(agent_obj)

        if index == 0:
            # De eerste agent start de discussie
            description = task_description
            expected_output = (
                "Your professional assessment of this topic from your role's perspective."
            )
            current_task = Task(
                description=description,
                expected_output=expected_output,
                agent=agent_obj
            )
        else:
            # Vervolgentaken ontvangen de historie van vorige taken als context
            description = (
                f"{task_description}\n\n"
                "Instruction: Consider the perspectives already shared by your fellow executives above, "
                "then add your own professional assessment from your role's perspective. "
                "Do NOT repeat any point, recommendation, or concern already raised by a previous executive above — "
                "only contribute analysis that comes specifically from your own role's unique lens, as described in your backstory. "
                "If, after reviewing what's already been said, you genuinely have nothing new to add from your specific perspective, "
                "say so explicitly in one sentence rather than restating prior points in different words."
            )
            expected_output = (
                "Your professional assessment building upon or contrasting with prior executive inputs."
            )
            current_task = Task(
                description=description,
                expected_output=expected_output,
                agent=agent_obj,
                context=list(tasks)  # Geef alle voorgaande taken mee als context
            )

        tasks.append(current_task)

    # 3. Stel de Crew samen en voer deze uit
    crew = Crew(
        agents=agent_instances,
        tasks=tasks,
        process=Process.sequential,
        verbose=True
    )

    # De daadwerkelijke kickoff is de zware, CPU/GPU-intensieve stap — deze
    # loopt altijd binnen EXECUTION_LOCK, zodat hij nooit gelijktijdig draait
    # met bijvoorbeeld de geplande dagelijkse research (die anders de
    # belasting simpelweg zou optellen in plaats van serialiseren).
    # Timeout rond de blokkerende kickoff-aanroep: als Ollama vastloopt of
    # extreem traag reageert, mag dit de aanroeper (en daarmee EXECUTION_LOCK)
    # niet voor onbepaalde tijd blokkeren. EERLIJKE beperking: Python kan een
    # lopende thread niet écht geforceerd stoppen — bij een timeout krijgt de
    # aanroeper direct een duidelijke fout terug, maar de onderliggende
    # crew-aanroep kan op de achtergrond nog even doorlopen tot hij zelf
    # afrondt. Dat is nog altijd veel beter dan een verzoek dat voor altijd
    # blijft hangen.
    MEETING_TIMEOUT_SECONDS = 600  # 10 minuten

    with EXECUTION_LOCK:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(crew.kickoff)
            try:
                crew_result = future.result(timeout=MEETING_TIMEOUT_SECONDS)
            except FutureTimeoutError:
                raise TimeoutError(
                    f"Meeting execution exceeded the {MEETING_TIMEOUT_SECONDS}s timeout — "
                    f"Ollama may be unresponsive or the model is taking unusually long."
                )

    # 4. Verzamel de individuele output per taak/agent
    individual_outputs: Dict[str, str] = {}
    for key, task in zip(agent_keys, tasks):
        # Gebruik task.output.raw om de specifieke output van die stap op te halen
        if hasattr(task, "output") and task.output is not None:
            individual_outputs[key] = task.output.raw
        else:
            individual_outputs[key] = "Geen individuele output beschikbaar."

    return {
        "final_decision": str(crew_result),
        "participants": agent_keys,
        "individual_outputs": individual_outputs
    }


if __name__ == "__main__":
    print("=" * 60)
    print("STARTING TEST MEETING WORKFLOW")
    print("=" * 60)

    try:
        meeting_result = run_executive_meeting(
            topic="Test Meeting",
            task_description="Should we open a new office in Austin, Texas next year?",
            agent_keys=["cfo", "coo", "ceo"]
        )

        print("\n" + "=" * 60)
        print("MEETING RESULTS (JSON):")
        print("=" * 60)
        print(json.dumps(meeting_result, indent=2))

    except Exception as error:
        print(f"\nFout tijdens uitvoeren van test meeting: {error}")