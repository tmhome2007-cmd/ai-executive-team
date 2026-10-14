"""Freeze a two-stage delivery candidate against the retained intake variants."""

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
from workflows import plan_delivery as delivery
from workflows.quality_benchmark import local_request
from workflows.structured_decision import private_save

STORE = ROOT / "audit-results/sprint7-reasoning"
ASSETS = (
    "workflows/plan_delivery.py",
    "workflows/actionable_plan.py",
    "workflows/output_quality.py",
    "workflows/structured_decision.py",
    "scripts/sprint7_delivery_experiment.py",
    "scripts/sprint7_schema_experiment.py",
)


def hashes():
    return {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in ASSETS
    }


def freeze(previous, model_tag=None):
    previous = Path(previous).resolve()
    old = json.loads((previous / "freeze.json").read_text())
    old_tag = old["model"]["configuration"]["tag"]
    selected = identity(model_tag or old_tag)
    if model_tag is None and old["model"] != selected:
        raise ValueError("Installed model differs from the prior comparison")
    if any(c["input"]["tool_status"] != "unknown" for c in old["cases"].values()):
        raise ValueError(
            "This development comparison requires unknown tool availability"
        )
    directory = STORE / ("run-" + uuid.uuid4().hex)
    private_save(
        directory,
        "freeze.json",
        {
            "source_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "source_hashes": hashes(),
            "model": selected,
            "baseline_model": old["model"],
            "comparison_kind": (
                "different-installed-model"
                if selected != old["model"]
                else "same-installed-model"
            ),
            "options": old["options"],
            "persona": old["persona"],
            "cases": old["cases"],
            "repetitions": 3,
            "repairs": 0,
            "rubric": old["rubric"],
            "prior_run": str(previous),
            "scope": "Role-neutral explanation helper, not CEO speech: canonical persona is metadata only. Same reviewed records/corrections and typed answers. Application supplies operational checks, success, pivot branches, stop anchors, full correction snapshot, distinct alternative labels/conditional comparison/pivotal explanations and complete standard invitation/privacy/feedback text. Model supplies evidence, step explanation, alternative/pivotal-key selection and exact source-link selection. This measures combined workflow, not independent drafting/planning, full team or held-out performance.",
            "extra_gate": "All 9 complete plans valid without repair; no outbound instruction disguised as private check; B has a usable safe-input/feedback draft; A/C may honestly end with a blocker and require no draft. Apply original usefulness axes and gate; no automatic merge or owner acceptance.",
        },
    )
    return directory


def run(directory):
    directory = Path(directory).resolve()
    if directory.parent != STORE.resolve() or not directory.name.startswith("run-"):
        raise ValueError("Invalid experiment directory")
    frozen = json.loads((directory / "freeze.json").read_text())
    if (
        hashes() != frozen["source_hashes"]
        or identity(frozen["model"].get("configuration", {}).get("tag", "llama3.1"))
        != frozen["model"]
    ):
        raise ValueError("Frozen source or model identity changed")
    private_save(directory, "started.json", {"time": time.time()})
    slots = []
    for case, context in frozen["cases"].items():
        value = context["input"]
        question = context["intake"]["brief"]
        sources = delivery.evidence_sources(context)
        for repetition in range(1, 4):
            slot = {
                "case": case,
                "repetition": repetition,
                "validated": False,
                "raw_stages": [],
                "status": "incomplete",
                "application_composition": {
                    "version": delivery.VERSION,
                    "standard_invitation": delivery.outreach_required(
                        value["lead_status"],
                        value["owner_minutes"],
                        value["tool_status"],
                    ),
                    "distinct_alternative_labels": True,
                    "conditional_comparison_and_pivotal_explanation": "application rules",
                },
            }
            start = time.monotonic()
            try:
                model = frozen["model"]["configuration"]["resolved_tag"]
                payload = delivery.preparation_payload(
                    model,
                    value["request"],
                    frozen["persona"],
                    value["lead_status"],
                    value["owner_minutes"],
                    sources,
                    tool_status=value["tool_status"],
                )
                reply = local_request(
                    "http://127.0.0.1:11434", "/api/generate", payload
                )
                slot["raw_stages"].append(
                    {
                        "stage": "preparation",
                        "raw": reply.get("response"),
                        "done": reply.get("done"),
                    }
                )
                if reply.get("done") is not True or not isinstance(
                    reply.get("response"), str
                ):
                    raise ValueError("Incomplete preparation")
                preparation = delivery.validate_preparation(
                    reply["response"],
                    question,
                    value["lead_status"],
                    value["owner_minutes"],
                    sources,
                    tool_status=value["tool_status"],
                )
                draft_raw = None
                if delivery.outreach_required(
                    value["lead_status"], value["owner_minutes"], value["tool_status"]
                ):
                    reply = local_request(
                        "http://127.0.0.1:11434",
                        "/api/generate",
                        delivery.invitation_payload(
                            model, value["request"], preparation, sources
                        ),
                    )
                    slot["raw_stages"].append(
                        {
                            "stage": "invitation",
                            "raw": reply.get("response"),
                            "done": reply.get("done"),
                        }
                    )
                    if reply.get("done") is not True or not isinstance(
                        reply.get("response"), str
                    ):
                        raise ValueError("Incomplete invitation")
                    draft_raw = reply["response"]
                result = delivery.assemble(
                    preparation,
                    draft_raw,
                    question,
                    value["lead_status"],
                    value["owner_minutes"],
                    sources,
                    tool_status=value["tool_status"],
                )
                slot.update(validated=True, status="valid", plan=result.model_dump())
            except Exception as error:
                slot.update(status="error", error_type=type(error).__name__)
            slot["seconds"] = round(time.monotonic() - start, 2)
            private_save(directory, f"{case}-{repetition}.json", slot)
            slots.append(slot)
            print(case, repetition, slot["status"], slot["seconds"], flush=True)
    summary = {
        "scheduled": 9,
        "completed": len(slots),
        "validated": sum(s["validated"] for s in slots),
        "stage_responses": sum(len(s["raw_stages"]) for s in slots),
        "errors": sum(s["status"] == "error" for s in slots),
        "identity_unchanged": identity(frozen["model"]["configuration"]["tag"])
        == frozen["model"],
        "source_unchanged": hashes() == frozen["source_hashes"],
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
    parser.add_argument(
        "--model",
        choices=["llama3", "llama3.1", "qwen2.5:14b-instruct-q4_K_M"],
        help="Freeze an already installed alternative; no pull or remote fallback.",
    )
    args = parser.parse_args()
    if args.model and not args.freeze_previous:
        parser.error("Select the model at freeze time, never while running")
    (
        print(freeze(args.freeze_previous, args.model))
        if args.freeze_previous
        else run(args.run)
    )


if __name__ == "__main__":
    main()
