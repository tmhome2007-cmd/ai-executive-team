"""Opt-in single-CFO comparison of free recommendations and bound unknown checks."""

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
from workflows import bound_review, independent_decision, plan_delivery
from workflows.quality_benchmark import local_request
from workflows.structured_decision import private_save

STORE = ROOT / "audit-results/sprint7-reasoning"
MODEL = "qwen2.5:14b-instruct-q4_K_M"
ASSETS = (
    "workflows/bound_review.py",
    "workflows/independent_decision.py",
    "workflows/structured_decision.py",
    "workflows/plan_delivery.py",
    "workflows/output_quality.py",
    "workflows/quality_benchmark.py",
    "workflows/local_model_identity.py",
    "scripts/sprint7_schema_experiment.py",
    "scripts/sprint7_bound_review_experiment.py",
)
CHECKS = {
    "tool_availability": "Owner: check the tool privately with safe fictional input compatible with its documented format. Record errors; a failure blocks invitations.",
    "tool_recovery": "Owner: privately review whether the known outage has been resolved. Keep invitations paused until working status is confirmed.",
    "contact_status": "Owner: privately review existing messages for the intended contact's identity, date and reply status. Keep unmatched people separate.",
    "eligible_live_case": "Owner: privately review whether existing records establish that the responsive contact has their own current live case. Record missing evidence; do not contact anyone in this step.",
    "alternative_route": "Owner: privately review existing messages for another permitted conversation with a potentially eligible tester. Record a blocker if none is established; do not send a message.",
}


def catalog():
    return {
        key: bound_review.ReviewTarget(
            question=plan_delivery.UNKNOWN_QUESTIONS[key], owner_check=value
        )
        for key, value in CHECKS.items()
    }


def hashes():
    return {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in ASSETS
    }


def freeze(previous):
    previous = Path(previous).resolve()
    if previous.parent != STORE.resolve() or not previous.name.startswith("run-"):
        raise ValueError("Expected a retained private development run")
    old = json.loads((previous / "freeze.json").read_text())
    if old.get("model") != identity(MODEL):
        raise ValueError("Installed model differs from prior comparison")
    cases = old["cases"]
    targets = catalog()
    reverse = {value.question: key for key, value in targets.items()}
    for case in cases.values():
        case["unresolved_ids"] = [reverse[question] for question in case["unknowns"]]
        bound_review.unresolved_targets(targets, case["unresolved_ids"])
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
            "options": dict(independent_decision.OPTIONS),
            "personality": old["personality"],
            "catalog": {key: value.model_dump() for key, value in targets.items()},
            "cases": cases,
            "order": ["A_as_tested", "B_replied", "C_silent"],
            "modes": ["baseline", "candidate"],
            "prior_run": str(previous),
            "repairs": 0,
            "rubric": {
                "F01": "Check and ALL generated explanation/assumption fields must preserve known reply status, known time and unresolved identity. Known silence is not proof of lack of interest.",
                "linkage": "Candidate target ID must be unresolved and its exact paired workflow question/check must be shown. Do not count this code-enforced pairing as independent model reasoning.",
                "usefulness": "Read every answer: target selection, reason and citation must be relevant and coherent; no made-up facts, actor authority, inference from group size or reopening settled questions. Single-step probe, not complete owner delivery.",
                "adoption": "No factual regression and useful semantic improvement; a six-sample single-role development probe alone does not authorize app adoption or claim team/held-out usefulness.",
            },
            "scope": "Six single-CFO first proposals; same exposed cases, original unprojected source bytes, installed Qwen, canonical profile and options. Candidate changes schema/prompt and supplies workflow-authored checks bound to the selected unresolved ID. Model supplies choice, reason, citation and assumption, not the step wording. Zero retries. No API, default-model change, cloud, downloads, contact or company data.",
        },
    )
    return directory


def run(directory):
    directory = Path(directory).resolve()
    if directory.parent != STORE.resolve() or not directory.name.startswith("run-"):
        raise ValueError("Invalid private experiment directory")
    frozen = json.loads((directory / "freeze.json").read_text())
    if hashes() != frozen["source_hashes"] or identity(MODEL) != frozen["model"]:
        raise ValueError("Frozen code or model changed")
    if frozen["options"] != independent_decision.OPTIONS:
        raise ValueError("Inference options changed")
    targets = {
        key: bound_review.ReviewTarget.model_validate(value)
        for key, value in frozen["catalog"].items()
    }
    private_save(directory, "started.json", {"time": time.time()})
    samples = []
    for name in frozen["order"]:
        case = frozen["cases"][name]
        for mode in frozen["modes"]:
            args = (
                frozen["model"]["configuration"]["resolved_tag"],
                case["question"],
                case["sources"],
                "cfo",
                frozen["personality"],
            )
            payload = (
                independent_decision.proposal_payload(*args, case["unknowns"])
                if mode == "baseline"
                else bound_review.request_payload(
                    *args, targets, case["unresolved_ids"]
                )
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
                if len(payload["prompt"]) > 12000:
                    raise ValueError("Bounded input exceeded")
                reply = local_request(
                    "http://127.0.0.1:11434", "/api/generate", payload
                )
                result["raw"] = reply.get("response")
                if reply.get("done") is not True or not isinstance(result["raw"], str):
                    raise ValueError("Incomplete model response")
                if mode == "baseline":
                    result["proposal"] = independent_decision.validate_proposal(
                        result["raw"], case["sources"], case["unknowns"]
                    ).model_dump()
                else:
                    value = bound_review.validate(
                        result["raw"], case["sources"], targets, case["unresolved_ids"]
                    )
                    result["proposal"] = value.model_dump()
                    result["rendered"] = bound_review.render(
                        value, case["sources"], targets, case["unresolved_ids"]
                    )
                result["valid"] = True
            except Exception as error:
                result["error_type"] = type(error).__name__
            finally:
                result["seconds"] = round(time.monotonic() - started, 2)
                filename = f"{name}-1-{mode}.json"
                private_save(directory, filename, result)
                samples.append(
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
            "samples": samples,
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
