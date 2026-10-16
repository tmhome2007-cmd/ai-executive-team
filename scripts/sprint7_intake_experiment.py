"""Freeze and assess the same contact variants after deterministic owner intake."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.sprint7_schema_experiment import identity
from workflows import actionable_plan as plan
from workflows.decision_intake import IntakeInput, build_intake
from workflows.quality_benchmark import local_request
from workflows.structured_decision import private_save

STORE = ROOT / "audit-results/sprint7-intake"
ASSETS = (
    "workflows/decision_intake.py",
    "workflows/actionable_plan.py",
    "workflows/output_quality.py",
    "scripts/sprint7_intake_experiment.py",
    "api/decision_intake.py",
)


def hashes():
    return {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in ASSETS
    }


def freeze(previous):
    """Use the prior private development fixture, never overwrite its results."""
    previous = Path(previous).resolve()
    old = json.loads((previous / "freeze.json").read_text())
    if old["model"] != identity():
        raise ValueError("Installed model differs from the prior comparison")
    # Historical records, not a second copy of the previous instructions/prompt.
    historical = old["cases"]["A_as_tested"].split("CLARIFICATION\n")[0]
    historical = historical.split("HISTORICAL FACTS\n", 1)[1]
    contexts = {}
    for case, lead in (
        ("A_as_tested", "unknown"),
        ("B_replied", "recent_reply"),
        ("C_silent", "silent"),
    ):
        source = {
            "id": 1,
            "version": 1,
            "title": "Owner-supplied historical product record",
            "summary": historical,
            "verification": "owner_confirmed",
            "observed_at": "Recorded in the prior owner test; business-fact date unconfirmed",
            "freshness": "unknown",
        }
        if case == "A_as_tested":
            correction = (
                old["cases"][case]
                .split("CLARIFICATION\n", 1)[1]
                .split("CONSTRAINTS\n", 1)[0]
            )
        else:
            correction = (
                old["cases"][case]
                .split("VARIANT CLARIFICATION", 1)[1]
                .split("CONSTRAINTS\n", 1)[0]
            )
        value = IntakeInput(
            request="Help me get the first real user for Reinstatly",
            source_ids=[1],
            correction=correction,
            lead_status=lead,
            tool_status="unknown",
            owner_minutes=60,
        )
        contexts[case] = {
            "input": value.model_dump(),
            "intake": build_intake(value, lambda _: source),
        }
    directory = STORE / ("run-" + uuid.uuid4().hex)
    private_save(
        directory,
        "freeze.json",
        {
            "source_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "source_hashes": hashes(),
            "model": old["model"],
            "options": old["options"],
            "persona": old["persona"],
            "cases": contexts,
            "repetitions": 3,
            "repairs": 0,
            "rubric": old["rubric"],
            "prior_run": str(previous),
            "scope": "Same isolated CEO plan schema; changed intake brief and trusted route policy. Not a full three-role test or independent proof of model reasoning.",
            "source_metadata_limit": "Historical fixture is an explicitly selected synthetic record wrapping supplied owner facts, not a live database registration. Its date remains unconfirmed.",
        },
    )
    return directory


def run(directory):
    directory = Path(directory).resolve()
    if directory.parent != STORE.resolve():
        raise ValueError("Invalid experiment directory")
    frozen = json.loads((directory / "freeze.json").read_text())
    if hashes() != frozen["source_hashes"] or identity() != frozen["model"]:
        raise ValueError("Frozen source or identity changed")
    private_save(directory, "started.json", {"time": time.time()})
    slots = []
    for case, context in frozen["cases"].items():
        question = context["intake"]["brief"]
        for repetition in range(1, 4):
            slot = {
                "case": case,
                "repetition": repetition,
                "schema_valid": False,
                "validated": False,
                "raw": None,
                "status": "incomplete",
            }
            start = time.monotonic()
            try:
                reply = local_request(
                    "http://127.0.0.1:11434",
                    "/api/generate",
                    plan.payload(
                        frozen["model"]["configuration"]["resolved_tag"],
                        question,
                        frozen["persona"],
                        60,
                    ),
                )
                slot["raw"] = reply.get("response")
                if reply.get("done") is not True or not isinstance(slot["raw"], str):
                    raise ValueError("Incomplete generation")
                plan.OwnerPlan.model_validate_json(
                    slot["raw"], context={"owner_minutes": 60}
                )
                slot["schema_valid"] = True
                plan.validate_plan(slot["raw"], question, 60)
                slot.update(validated=True, status="valid")
            except Exception as error:
                slot.update(status="error", error_type=type(error).__name__)
            slot["seconds"] = round(time.monotonic() - start, 2)
            private_save(directory, f"{case}-{repetition}.json", slot)
            slots.append(slot)
            print(case, repetition, slot["status"], slot["seconds"], flush=True)
    summary = {
        "scheduled": 9,
        "completed": len(slots),
        "schema_valid": sum(s["schema_valid"] for s in slots),
        "validated": sum(s["validated"] for s in slots),
        "errors": sum(s["status"] == "error" for s in slots),
        "identity_unchanged": identity() == frozen["model"],
        "semantic_review": "pending",
        "merged": False,
        "owner_accepted": False,
    }
    private_save(directory, "summary.json", summary)
    print(json.dumps(summary), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--freeze-previous")
    group.add_argument("--run")
    args = parser.parse_args()
    print(freeze(args.freeze_previous)) if args.freeze_previous else run(args.run)


if __name__ == "__main__":
    main()
