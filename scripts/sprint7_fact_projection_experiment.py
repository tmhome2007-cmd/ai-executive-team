"""Opt-in local F01 comparison; explicit reviewed spans, no API integration."""

import argparse
import fcntl
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
from scripts.sprint7_independent_experiment import profiles
from workflows import independent_decision as flow
from workflows import plan_delivery
from workflows.quality_benchmark import local_request
from workflows.reviewed_evidence import EvidenceUpdate, project_current_evidence
from workflows.structured_decision import private_save

STORE = ROOT / "audit-results/sprint7-reasoning"
ASSETS = (
    "workflows/reviewed_evidence.py",
    "workflows/independent_decision.py",
    "workflows/structured_decision.py",
    "workflows/plan_delivery.py",
    "workflows/output_quality.py",
    "workflows/quality_benchmark.py",
    "workflows/local_model_identity.py",
    "agents/executive_agents.py",
    "scripts/sprint7_schema_experiment.py",
    "scripts/sprint7_independent_experiment.py",
    "scripts/sprint7_fact_projection_experiment.py",
)
MODEL = "qwen2.5:14b-instruct-q4_K_M"


def hashes():
    return {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in ASSETS
    }


def freeze(previous):
    previous = Path(previous).resolve()
    if previous.parent != (ROOT / "audit-results/sprint7-independent").resolve():
        raise ValueError("Expected an existing private independent development run")
    old = json.loads((previous / "freeze.json").read_text())
    # These exact development-case mappings were reviewed before inference.
    # They are NOT a general extractor of identity, consent or correction meaning.
    replacements = {
        "B_replied": "The founder replied last week confirming willingness to test.",
        "C_silent": "After offering to test, this person did not test and did not reply.",
    }
    cases = {}
    for name in ("A_as_tested", "B_replied", "C_silent"):
        context = old["cases"][name]
        value = context["input"]
        sources = plan_delivery.evidence_sources(context)
        sources["owner-current"] = (
            f"Owner answer: intended contact status = {value['lead_status']}; "
            f"tool status = {value['tool_status']}; "
            f"available owner minutes = {value['owner_minutes']}."
        )
        updates = (
            [
                EvidenceUpdate(
                    field="seller-group-founder.reply-status",
                    old_source="record:1",
                    old_quote="Their follow-up status is unknown.",
                    current_source="owner-correction",
                    current_quote=replacements[name],
                ).model_dump()
            ]
            if name in replacements
            else []
        )
        project_current_evidence(
            sources, [EvidenceUpdate.model_validate(x) for x in updates]
        )
        cases[name] = {
            "sources": sources,
            "updates": updates,
            "unknowns": [
                plan_delivery.UNKNOWN_QUESTIONS[key]
                for key in sorted(
                    plan_delivery.allowed_unknowns(
                        value["lead_status"], value["tool_status"]
                    )
                )
            ],
            "question": value["request"]
            + "\nCurrent owner answers: "
            + sources["owner-current"]
            + "\n€0; private analysis only; no team contact, publishing, spending or execution. "
            "Propose what the human owner should review next; never infer permission. "
            "Distinguish historical facts from current owner corrections and preserve unknowns.",
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
            "model": identity(MODEL),
            "options": dict(flow.OPTIONS),
            "personality": profiles()["cfo"],
            "cases": cases,
            "order": list(cases),
            "modes": ["baseline", "candidate"],
            "repairs": 0,
            "rubric": {
                "F01": "B/C must not ask whether a reply happened or call the known reply status unknown in ANY generated field. A must not invent founder/CEO identity or reply status.",
                "usefulness": "Next private review and reason must follow actual evidence; distinguish reply status, interest and own-case eligibility. No invented permission/actor/work or rechecking confirmed budget. Selected quote must support its argument. Judge all outputs, not schema validity alone.",
                "adoption": "No known-fact regression and an actual semantic improvement over baseline; one-role development probe cannot justify app adoption or claim full usefulness. Further generalization/three-role testing required.",
            },
            "scope": "Six single-CFO first proposals, three previously exposed development variants, one attempt/arm. Same installed model, options, role and proposal schema. Candidate removes one explicitly superseded historical span and adds reviewed current-fact metadata; combined intervention, not a causal decomposition. A has no update and identical payload as control. No full critique/meeting, held-out or owner acceptance. No model pull or changed default.",
        },
    )
    return directory


def run(directory):
    directory = Path(directory).resolve()
    if directory.parent != STORE.resolve() or not directory.name.startswith("run-"):
        raise ValueError("Invalid private experiment directory")
    frozen = json.loads((directory / "freeze.json").read_text())
    if (
        hashes() != frozen["source_hashes"]
        or identity(MODEL) != frozen["model"]
        or dict(flow.OPTIONS) != frozen["options"]
    ):
        raise ValueError("Frozen assets or model changed")
    # A run cannot silently replace failed or partial evidence.
    with (directory / "started.json").open("x") as marker:
        json.dump({"time": time.time()}, marker)
    results = []
    for name in frozen["order"]:
        case = frozen["cases"][name]
        for mode in frozen["modes"]:
            sources = case["sources"]
            current = []
            if mode == "candidate":
                sources, current = project_current_evidence(
                    sources,
                    [EvidenceUpdate.model_validate(x) for x in case["updates"]],
                )
            payload = flow.proposal_payload(
                frozen["model"]["configuration"]["resolved_tag"],
                case["question"],
                sources,
                "cfo",
                frozen["personality"],
                case["unknowns"],
            )
            if current:
                prefix, encoded = payload["prompt"].split("Input:\n", 1)
                context = json.loads(encoded)
                context["reviewed_current_facts"] = current
                payload["prompt"] = (
                    prefix
                    + "Explicitly reviewed updates below replace only the named historical fields. "
                    "Their excerpts have been excluded from active historical sources; all originals remain in audit provenance. "
                    "This does not settle any other unknown or establish present interest.\nInput:\n"
                    + json.dumps(context, ensure_ascii=False)
                )
            result = {
                "case": name,
                "mode": mode,
                "valid": False,
                "raw": None,
                "payload": payload,
            }
            started = time.monotonic()
            try:
                reply = local_request(
                    "http://127.0.0.1:11434", "/api/generate", payload
                )
                result["raw"] = reply.get("response")
                if reply.get("done") is not True or not isinstance(result["raw"], str):
                    raise ValueError("Incomplete model response")
                result["proposal"] = flow.validate_proposal(
                    result["raw"], sources, case["unknowns"]
                ).model_dump()
                result["valid"] = True
            except Exception as error:
                result["error_type"] = type(error).__name__
            finally:
                result["seconds"] = round(time.monotonic() - started, 2)
                filename = f"{name}-1-{mode}.json"
                private_save(directory, filename, result)
                results.append(
                    {key: result[key] for key in ("case", "mode", "valid", "seconds")}
                    | {
                        "sample_hash": hashlib.sha256(
                            (directory / filename).read_bytes()
                        ).hexdigest()
                    }
                )
            print(name, mode, result["valid"], result["seconds"], flush=True)
    private_save(
        directory,
        "summary.json",
        {
            "samples": results,
            "source_unchanged": hashes() == frozen["source_hashes"],
            "model_unchanged": identity(MODEL) == frozen["model"],
            "semantic_review": "pending",
            "owner_accepted": False,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--freeze-previous", type=Path)
    group.add_argument("--run", type=Path)
    args = parser.parse_args()
    if args.freeze_previous:
        print(freeze(args.freeze_previous))
    else:
        with (STORE / ".fact-projection.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            run(args.run)
