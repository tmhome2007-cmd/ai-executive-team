"""Explicit local-only evaluation with immutable freezes and retained failed slots."""

import argparse
import ast
import hashlib
import json
import os
import subprocess
from pathlib import Path
import sys
from types import SimpleNamespace
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluation_protocol import model_input, validate
from workflows.local_model_identity import resolve_model
from workflows.quality_benchmark import local_request
from workflows.structured_decision import (
    Contribution,
    OPTIONS,
    PROMPT,
    private_save,
    request_payload,
    validate_contribution,
)

PROTOCOL = ROOT / "docs/evaluation/sprint6"
STORE = ROOT / "audit-results/sprint6-evaluation"


def sha(path):
    """Hash exact bytes, never ambiguous parsed representations."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def persona():
    """Read the canonical CEO persona without importing agents, keys or databases."""
    tree = ast.parse((ROOT / "agents/executive_agents.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "ceo_agent"
            for target in node.targets
        ):
            return ast.literal_eval(
                next(
                    keyword.value
                    for keyword in node.value.keywords
                    if keyword.arg == "backstory"
                )
            )
    raise ValueError("Canonical CEO persona unavailable")


def identity():
    """Resolve only the explicitly frozen installed loopback model."""
    return resolve_model(
        SimpleNamespace(
            model="ollama/llama3.1",
            provider="ollama",
            base_url="http://localhost:11434",
            temperature=0,
            max_tokens=1200,
            timeout=120,
        )
    )


def freeze():
    """Create a new immutable candidate snapshot before generation."""
    protocol = validate(PROTOCOL)
    model = identity()
    expected = json.loads((PROTOCOL / "freeze.json").read_text())
    if (
        model["digest"] != expected["model"]["digest"]
        or OPTIONS != expected["generation"]["options"]
    ):
        raise ValueError("Model identity or explicit options differ from protocol")
    directory = STORE / ("candidate-" + uuid.uuid4().hex)
    private_save(
        directory,
        "candidate.json",
        {
            "protocol_hash": protocol["freeze_hash"],
            "identity": model,
            "options": OPTIONS,
            "prompt": PROMPT,
            "schema": Contribution.model_json_schema(),
            "persona": persona(),
            "source_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "repair_attempts": 1,
            "source_hashes": {
                name: sha(ROOT / name)
                for name in (
                    "workflows/structured_decision.py",
                    "workflows/output_quality.py",
                    "scripts/sprint6_evaluation.py",
                    "scripts/evaluation_protocol.py",
                )
            },
            "comparison_limit": "Same question and source records, options and model; different prompt, CEO persona context and response schema. Candidate is one contribution, not the multi-role meeting. No competence or causal model-quality claim.",
        },
    )
    return directory / "candidate.json"


def validate_candidate(path):
    """Reject altered candidates, protocol/code drift and unavailable identities."""
    snapshot = json.loads(path.read_text())
    if snapshot["protocol_hash"] != validate(PROTOCOL)["freeze_hash"]:
        raise ValueError("Protocol changed since candidate freeze")
    if any(
        sha(ROOT / name) != expected
        for name, expected in snapshot["source_hashes"].items()
    ):
        raise ValueError("Candidate source changed; create a new disclosed freeze")
    if (
        snapshot["prompt"] != PROMPT
        or snapshot["schema"] != Contribution.model_json_schema()
        or snapshot["options"] != OPTIONS
        or snapshot["persona"] != persona()
        or snapshot["identity"] != identity()
        or snapshot["repair_attempts"] != 1
    ):
        raise ValueError("Candidate configuration or model identity changed")
    return snapshot


def append_ledger(directory, entry):
    """Durably append accesses; a prior held-out run prevents another clean claim."""
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if any(parent.is_symlink() for parent in (directory, *directory.parents)):
        raise ValueError("Evaluation ledger cannot use symlinks")
    fd = os.open(
        directory / "access.jsonl",
        os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW,
        0o600,
    )
    with os.fdopen(fd, "a") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def baseline_valid(raw):
    """Narrow baseline format check, independent of semantic judgement."""
    obj = json.loads(raw)
    if not isinstance(obj, dict) or set(obj) != {"findings", "unknowns", "next_action"}:
        raise ValueError("Invalid baseline schema")
    for key in ("findings", "unknowns"):
        if (
            not isinstance(obj[key], list)
            or not 1 <= len(obj[key]) <= 3
            or any(not isinstance(x, str) or not x.strip() for x in obj[key])
        ):
            raise ValueError("Invalid baseline list")
    if not isinstance(obj["next_action"], str) or not obj["next_action"].strip():
        raise ValueError("Invalid baseline next action")


def run(candidate_path, split):
    """Save every scheduled slot, including errors; never silently replace runs."""
    snapshot = validate_candidate(candidate_path)
    candidate_hash = sha(candidate_path)
    if split == "held_out" and (STORE / "access.jsonl").exists():
        entries = [
            json.loads(line)
            for line in (STORE / "access.jsonl").read_text().splitlines()
        ]
        if any(entry["split"] == "held_out" for entry in entries):
            raise ValueError(
                "Held-out generation already accessed; no repeated untouched claim"
            )
    cases = json.loads(
        (
            PROTOCOL
            / (
                "development-cases.json"
                if split == "development"
                else "held-out-cases.json"
            )
        ).read_text()
    )
    directory = STORE / (split + "-" + uuid.uuid4().hex)
    slots = [
        {
            "case": case["id"],
            "repeat": repeat,
            "variant": variant,
            "status": "incomplete",
            "human_grounding": "unscored",
            "human_unsupported_claims": "unscored",
            "owner_usefulness": "unscored",
        }
        for case in cases
        for repeat in (1, 2, 3)
        for variant in ("baseline", "candidate")
    ]
    private_save(
        directory,
        "manifest.json",
        {
            "candidate_hash": candidate_hash,
            "source_commit": snapshot.get("source_commit", "unknown legacy candidate"),
            "candidate_path": str(candidate_path.relative_to(ROOT)),
            "split": split,
            "slots": slots,
            "identity": snapshot["identity"],
            "protocol_hash": snapshot["protocol_hash"],
        },
    )
    append_ledger(
        STORE,
        {
            "split": split,
            "run": directory.name,
            "candidate_hash": candidate_hash,
            "repair_use": False,
            "case_ids": [case["id"] for case in cases],
        },
    )
    base_prompt = (PROTOCOL / "baseline-prompt.txt").read_text()
    from workflows.execution_lock import EXECUTION_LOCK

    with EXECUTION_LOCK:
        for index, slot in enumerate(slots):
            case = next(case for case in cases if case["id"] == slot["case"])
            sources = {source["id"]: source["text"] for source in case["sources"]}
            if slot["variant"] == "baseline":
                payload = {
                    "model": "llama3.1:latest",
                    "prompt": base_prompt + "\n" + model_input(case),
                    "format": "json",
                    "options": OPTIONS,
                    "stream": False,
                    "keep_alive": 0,
                }
            else:
                payload = request_payload(
                    "llama3.1:latest",
                    case["question"] + "\n" + case["allowed_next_step"],
                    sources,
                    "ceo",
                    snapshot["persona"],
                )
            attempts = []
            for attempt in (1, 2):
                raw = None
                try:
                    reply = local_request(
                        "http://localhost:11434", "/api/generate", payload
                    )
                    raw = reply.get("response")
                    if reply.get("done") is not True or not isinstance(raw, str):
                        raise ValueError("Incomplete generation")
                    (
                        baseline_valid(raw)
                        if slot["variant"] == "baseline"
                        else validate_contribution(raw, sources)
                    )
                except Exception as error:
                    attempts.append(
                        {
                            "attempt": attempt,
                            "raw": raw,
                            "status": "error",
                            "error_type": type(error).__name__,
                        }
                    )
                    payload = {
                        **payload,
                        "prompt": payload["prompt"]
                        + "\nRepair: the previous attempt was invalid. Follow the required JSON shape and quote only supplied records.",
                    }
                else:
                    attempts.append({"attempt": attempt, "raw": raw, "status": "valid"})
                    break
            result = {
                **slot,
                "status": attempts[-1]["status"],
                "first_attempt_status": attempts[0]["status"],
                "attempts": attempts,
            }
            private_save(directory, f"slot-{index:02}.json", result)
            print(
                f"{split} {index+1}/48 {slot['case']} {slot['variant']} {result['status']}",
                flush=True,
            )
        if identity() != snapshot["identity"]:
            private_save(
                directory,
                "identity-change.json",
                {"status": "aborted", "reason": "post-run identity changed"},
            )
            raise ValueError(
                "Post-run model identity changed; results are not comparable"
            )
    results = [
        json.loads(path.read_text()) for path in sorted(directory.glob("slot-*.json"))
    ]
    summary = {
        "split": split,
        "candidate_hash": candidate_hash,
        "scheduled": 48,
        "completed": len(results),
        "semantic_and_owner_scores": "unscored",
        "variants": {
            variant: {
                "denominator": 24,
                "valid_after_repair": sum(
                    result["status"] == "valid"
                    for result in results
                    if result["variant"] == variant
                ),
                "valid_first_attempt": sum(
                    result["first_attempt_status"] == "valid"
                    for result in results
                    if result["variant"] == variant
                ),
                "errors": sum(
                    result["status"] == "error"
                    for result in results
                    if result["variant"] == variant
                ),
            }
            for variant in ("baseline", "candidate")
        },
    }
    private_save(directory, "summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)
    return directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--split", choices=["development", "held_out"])
    args = parser.parse_args()
    if args.freeze and not args.candidate and not args.split:
        print(freeze())
    elif args.candidate and args.split and not args.freeze:
        print(run(args.candidate.resolve(), args.split))
    else:
        parser.error("Use --freeze, or --candidate PATH --split development|held_out")


if __name__ == "__main__":
    main()
