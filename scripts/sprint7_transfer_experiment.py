"""Freeze untouched transfer inputs after the guided development gate, no repair."""

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

STORE = ROOT / "audit-results/sprint7-transfer"
ASSETS = (
    "workflows/plan_delivery.py",
    "workflows/actionable_plan.py",
    "workflows/output_quality.py",
    "workflows/structured_decision.py",
    "scripts/sprint7_schema_experiment.py",
    "scripts/sprint7_transfer_experiment.py",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def hashes():
    return {name: sha(ROOT / name) for name in ASSETS}


def freeze(reserved, development):
    reserved, development = Path(reserved).resolve(), Path(development).resolve()
    assessment = json.loads((development / "semantic-assessment.json").read_text())
    if assessment.get("development_gate_passed") is not True:
        raise ValueError("A completed development gate is required before transfer")
    development_freeze = json.loads((development / "freeze.json").read_text())
    summary = json.loads((development / "summary.json").read_text())
    shared_assets = set(ASSETS) - {"scripts/sprint7_transfer_experiment.py"}
    if (
        any(
            development_freeze.get("source_hashes", {}).get(name) != sha(ROOT / name)
            for name in shared_assets
        )
        or summary.get("completed") != 9
        or summary.get("validated") != 9
        or summary.get("identity_unchanged") is not True
        or summary.get("source_unchanged") is not True
    ):
        raise ValueError("Current-code completed development evidence is required")
    manifest = json.loads((reserved / "manifest.json").read_text())
    if (
        sha(reserved / "cases.json") != manifest["cases_sha256"]
        or sha(reserved / "protocol.json") != manifest["protocol_sha256"]
    ):
        raise ValueError("Reserved input or protocol drift")
    models = {
        name: identity(tag)
        for name, tag in (
            ("baseline", "llama3.1"),
            ("candidate", "qwen2.5:14b-instruct-q4_K_M"),
        )
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
            "models": models,
            "options": dict(delivery.OPTIONS),
            "cases": json.loads((reserved / "cases.json").read_text()),
            "protocol": json.loads((reserved / "protocol.json").read_text()),
            "development_run": str(development),
            "reserved_input": str(reserved),
            "reserved_cases_sha256": manifest["cases_sha256"],
            "scope": "Same final guided workflow on two installed local models, six samples/model. Application supplies operational/comparison/pivotal/draft/link text; not independent model planning or author-blind evaluation. No transfer output used for tuning.",
            "scorer": "Reserved seven-axis protocol, analyst grades after inference; owner acceptance separate",
            "repairs": 0,
        },
    )
    return directory


def run(directory):
    directory = Path(directory).resolve()
    if directory.parent != STORE.resolve() or not directory.name.startswith("run-"):
        raise ValueError("Invalid transfer directory")
    frozen = json.loads((directory / "freeze.json").read_text())

    def stable():
        return (
            hashes() == frozen["source_hashes"]
            and frozen["options"] == delivery.OPTIONS
            and all(
                identity(model["configuration"]["tag"]) == model
                for model in frozen["models"].values()
            )
        )

    if not stable():
        raise ValueError("Frozen model, source or options drift")
    private_save(directory, "started.json", {"time": time.time()})
    summaries = []
    for case, context in frozen["cases"].items():
        value = context["input"]
        question = context["intake"]["brief"]
        sources = delivery.evidence_sources(context)
        for mode, model in frozen["models"].items():
            for repetition in range(1, 4):
                start = time.monotonic()
                slot = {
                    "case": case,
                    "mode": mode,
                    "repetition": repetition,
                    "validated": False,
                    "status": "incomplete",
                    "raw_stages": [],
                    "application_version": delivery.VERSION,
                }
                try:
                    payload = delivery.preparation_payload(
                        model["configuration"]["resolved_tag"],
                        value["request"],
                        "Role-neutral helper",
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
                        raise ValueError("Incomplete generation")
                    preparation = delivery.validate_preparation(
                        reply["response"],
                        question,
                        value["lead_status"],
                        value["owner_minutes"],
                        sources,
                        tool_status=value["tool_status"],
                    )
                    draft = (
                        delivery.recorded_invitation(sources).model_dump_json()
                        if delivery.outreach_required(
                            value["lead_status"],
                            value["owner_minutes"],
                            value["tool_status"],
                        )
                        else None
                    )
                    result = delivery.assemble(
                        preparation,
                        draft,
                        question,
                        value["lead_status"],
                        value["owner_minutes"],
                        sources,
                        tool_status=value["tool_status"],
                    )
                    slot.update(
                        validated=True, status="valid", plan=result.model_dump()
                    )
                except Exception as error:
                    slot.update(status="error", error_type=type(error).__name__)
                slot["seconds"] = round(time.monotonic() - start, 2)
                name = f"{case}-{repetition}-{mode}.json"
                private_save(directory, name, slot)
                summaries.append(
                    {
                        "case": case,
                        "mode": mode,
                        "repetition": repetition,
                        "validated": slot["validated"],
                        "seconds": slot["seconds"],
                        "sample_sha256": sha(directory / name),
                    }
                )
                print(
                    case, mode, repetition, slot["status"], slot["seconds"], flush=True
                )
    private_save(
        directory,
        "summary.json",
        {
            "samples": summaries,
            "source_and_models_unchanged": stable(),
            "semantic_review": "pending",
            "owner_accepted": False,
            "merged": False,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reserved")
    parser.add_argument("--development")
    parser.add_argument("--run")
    args = parser.parse_args()
    if args.run and (args.reserved or args.development):
        parser.error("Use run alone")
    if args.run:
        run(args.run)
    elif args.reserved and args.development:
        print(freeze(args.reserved, args.development))
    else:
        parser.error("Choose run or both reserved/development paths")
