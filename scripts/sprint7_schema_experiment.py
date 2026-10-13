"""Freeze and run one explicit local-only three-variant schema comparison."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.sprint6_evaluation import persona
from workflows import actionable_plan as candidate
from workflows import structured_decision as baseline
from workflows.local_model_identity import resolve_model
from workflows.quality_benchmark import local_request

STORE = ROOT / "audit-results/sprint7-schema"
ASSETS = (
    "workflows/actionable_plan.py",
    "workflows/structured_decision.py",
    "workflows/output_quality.py",
    "agents/executive_agents.py",
    "scripts/sprint7_schema_experiment.py",
)


def identity(model_tag="llama3.1"):
    """Resolve the installed local model without pull or cloud fallback."""
    return resolve_model(
        SimpleNamespace(
            model="ollama/" + model_tag,
            provider="ollama",
            base_url="http://127.0.0.1:11434",
            temperature=0,
            max_tokens=1200,
            timeout=120,
        )
    )


def hashes():
    return {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in ASSETS
    }


def freeze(source):
    """Freeze supplied owner input, synthetic variants and rubric before inference."""
    value = json.loads(Path(source).read_text())
    original = value["question"]
    warm = """VARIANT CLARIFICATION (replaces founder status and prior clarification):
The seller-group founder and the external CEO are different people.
The founder replied last week confirming willingness to test.
Whether the founder has their own current live suspension case is unknown.
The external CEO remains silent and is not the proposed contact.
"""
    silent = """VARIANT CLARIFICATION (replaces founder status and prior clarification):
The seller-group founder is the same person as the external CEO from the call.
After offering to test, this person did not test and did not reply.
The last unanswered exchange was seven days ago.
There is no confirmed willing live-case tester.
"""
    # Preserve all other facts and constraints; replace only contact clarification.
    before, rest = original.split("CLARIFICATION\n", 1)
    _, constraints = rest.split("CONSTRAINTS\n", 1)
    directory = STORE / ("run-" + uuid.uuid4().hex)
    baseline.private_save(
        directory,
        "freeze.json",
        {
            "source_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "source_hashes": hashes(),
            "model": identity(),
            "options": baseline.OPTIONS,
            "persona": persona(),
            "owner_minutes": 60,
            "cases": {
                "A_as_tested": original,
                "B_replied": before + warm + "\nCONSTRAINTS\n" + constraints,
                "C_silent": before + silent + "\nCONSTRAINTS\n" + constraints,
            },
            "repetitions": 3,
            "repairs": 0,
            "comparison_scope": "isolated canonical CEO; no prior speeches; not full three-role meetings",
            "determinism_limit": "Same seed/temperature; repetitions are not independent variance estimates",
            "rubric": {
                "axes": [
                    "concrete steps and effort breakdown",
                    "usable unsent outreach draft when appropriate",
                    "current tool check before inviting use",
                    "correct owner responsibility and no invented facts",
                    "bounded stopping window without repeated-pressure plan",
                    "live-case eligibility and structured feedback",
                    "contact clarification affects route or conditions",
                ],
                "merge_gate": "All 9 candidate samples valid without repairs; no critical authority/fact failure; at least 6/9 satisfy all seven semantic axes, at least two per case; B/C route or conditions differ in all three pairs; candidate improves completeness over matched baseline. Analyst assessment, owner acceptance separate. Reserved transfer cases not assessed by this experiment.",
            },
        },
    )
    return directory


def run(directory):
    """Keep every scheduled slot, incomplete/error samples and timing."""
    directory = Path(directory).resolve()
    if directory.parent != STORE.resolve() or not directory.name.startswith("run-"):
        raise ValueError("Run directory outside the private experiment store")
    frozen = json.loads((directory / "freeze.json").read_text())
    if frozen["source_hashes"] != hashes() or frozen["model"] != identity():
        raise ValueError("Frozen source or model identity changed")
    baseline.private_save(directory, "started.json", {"started_at": time.time()})
    results = []
    for case, question in frozen["cases"].items():
        for repetition in range(1, 4):
            order = (
                ("baseline", "candidate")
                if repetition % 2
                else ("candidate", "baseline")
            )
            for variant in order:
                slot = {
                    "case": case,
                    "repetition": repetition,
                    "variant": variant,
                    "status": "incomplete",
                    "schema_valid": False,
                    "validated": False,
                    "semantic_axes": None,
                    "raw": None,
                }
                started = time.monotonic()
                try:
                    model = frozen["model"]["configuration"]["resolved_tag"]
                    request = (
                        baseline.request_payload(
                            model,
                            question,
                            {"owner-task": question},
                            "ceo",
                            frozen["persona"],
                        )
                        if variant == "baseline"
                        else candidate.payload(
                            model, question, frozen["persona"], frozen["owner_minutes"]
                        )
                    )
                    reply = local_request(
                        "http://127.0.0.1:11434", "/api/generate", request
                    )
                    slot["raw"] = reply.get("response")
                    slot["provider_done"] = reply.get("done")
                    if reply.get("done") is not True or not isinstance(
                        slot["raw"], str
                    ):
                        raise ValueError("Incomplete provider response")
                    if variant == "baseline":
                        baseline.Contribution.model_validate_json(slot["raw"])
                        slot["schema_valid"] = True
                        baseline.validate_contribution(
                            slot["raw"], {"owner-task": question}
                        )
                    else:
                        candidate.OwnerPlan.model_validate_json(
                            slot["raw"],
                            context={"owner_minutes": frozen["owner_minutes"]},
                        )
                        slot["schema_valid"] = True
                        candidate.validate_plan(
                            slot["raw"], question, frozen["owner_minutes"]
                        )
                    slot.update(status="valid", validated=True)
                except Exception as error:
                    slot.update(status="error", error_type=type(error).__name__)
                slot["seconds"] = round(time.monotonic() - started, 2)
                baseline.private_save(
                    directory, f"{case}-{repetition}-{variant}.json", slot
                )
                results.append(slot)
                print(
                    case,
                    repetition,
                    variant,
                    slot["status"],
                    slot["seconds"],
                    flush=True,
                )
    if frozen["model"] != identity():
        baseline.private_save(
            directory, "identity-drift.json", {"valid_comparison": False}
        )
        raise ValueError("Model identity changed; comparison invalid")
    summary = {
        "completed_slots": len(results),
        "denominator_per_variant": 9,
        "counts": {
            variant: {
                "schema_valid": sum(
                    r["schema_valid"] for r in results if r["variant"] == variant
                ),
                "validated": sum(
                    r["validated"] for r in results if r["variant"] == variant
                ),
                "errors": sum(
                    r["status"] == "error" for r in results if r["variant"] == variant
                ),
            }
            for variant in ("baseline", "candidate")
        },
        "semantic_assessment": "pending",
        "owner_acceptance": False,
        "merge_eligible": False,
    }
    baseline.private_save(directory, "summary.json", summary)
    print(json.dumps(summary), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--freeze-input")
    group.add_argument("--run")
    args = parser.parse_args()
    print(freeze(args.freeze_input)) if args.freeze_input else run(args.run)


if __name__ == "__main__":
    main()
