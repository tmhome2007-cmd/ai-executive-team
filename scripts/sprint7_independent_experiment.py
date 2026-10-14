"""Freeze five paired sequential/independent meetings on development inputs."""

import argparse
import ast
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
from workflows import independent_decision as flow
from workflows import plan_delivery
from workflows import structured_decision as sd

STORE = ROOT / "audit-results/sprint7-independent"
ASSETS = (
    "workflows/independent_decision.py",
    "workflows/structured_decision.py",
    "workflows/output_quality.py",
    "workflows/plan_delivery.py",
    "scripts/sprint7_independent_experiment.py",
    "scripts/sprint7_schema_experiment.py",
    "agents/executive_agents.py",
)


def hashes():
    return {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in ASSETS
    }


def profiles():
    """Read canonical backstories without importing agent tools/company config."""
    tree = ast.parse((ROOT / "agents/executive_agents.py").read_text())
    result = {}
    for role in ("cso", "cfo", "ceo"):
        node = next(
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == role + "_agent"
                for target in node.targets
            )
        )
        result[role] = ast.literal_eval(
            next(item.value for item in node.value.keywords if item.arg == "backstory")
        )
    return result


def freeze(previous, model_tag):
    old = json.loads((Path(previous) / "freeze.json").read_text())
    cases = old["cases"]
    order = ("A_as_tested", "B_replied", "C_silent", "A_as_tested", "C_silent")
    directory = STORE / ("run-" + uuid.uuid4().hex)
    model = identity(model_tag)
    sd.private_save(
        directory,
        "freeze.json",
        {
            "source_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "source_hashes": hashes(),
            "model": model,
            "options": dict(flow.OPTIONS),
            "profiles": profiles(),
            "cases": cases,
            "order": order,
            "modes": ["baseline", "candidate"],
            "repairs": 0,
            "rubric": {
                "technical": "Five candidate meetings valid, independent first visibility and attributed shared-snapshot review; no repairs or critical factual/authority error.",
                "semantic": "Each candidate has at least two genuinely distinct first proposals or an explicit evidence-grounded no-alternative reason. Preserve actual concerns and role identities; normalized wording is not voting. Analyst and owner acceptance separate.",
            },
            "scope": "Paired development primitive comparison, not full API/current company run or held-out data. Both arms use the same compact proposal schema, bind native citation source/quote pairs; candidate review binds role/proposal quotations. Same owner sources and canonical backstories; baseline has earlier-first visibility and three calls, candidate has independent first plus review and six calls. Full actionable delivery is evaluated separately, not present in this proposal schema. No claim independence alone causes quality; latency/extra calls disclosed.",
        },
    )
    return directory


def run(directory):
    directory = Path(directory).resolve()
    if directory.parent != STORE.resolve() or not directory.name.startswith("run-"):
        raise ValueError("Invalid independent experiment directory")
    frozen = json.loads((directory / "freeze.json").read_text())
    tag = frozen["model"]["configuration"]["tag"]
    if (
        hashes() != frozen["source_hashes"]
        or identity(tag) != frozen["model"]
        or frozen["options"] != flow.OPTIONS
    ):
        raise ValueError("Frozen source, options or model changed")
    sd.private_save(directory, "started.json", {"time": time.time()})
    summaries = []
    for number, case in enumerate(frozen["order"], 1):
        context = frozen["cases"][case]
        sources = plan_delivery.evidence_sources(context)
        value = context["input"]
        sources["owner-current"] = (
            f"Owner answer: intended contact status = {value['lead_status']}; "
            f"tool status = {value['tool_status']}; "
            f"available owner minutes = {value['owner_minutes']}."
        )
        question = (
            value["request"]
            + "\nCurrent owner answers: "
            + sources["owner-current"]
            + "\n€0; private analysis only; no team contact, publishing, spending or execution. "
            "Propose what the human owner should review next; never infer permission. "
            "Distinguish historical facts from current owner corrections and preserve unknowns."
        )
        for mode in frozen["modes"]:
            started = time.monotonic()
            result = flow.run_rounds(
                question,
                sources,
                frozen["profiles"],
                frozen["model"]["configuration"]["resolved_tag"],
                mode,
            )
            result.update(
                case=case, meeting=number, seconds=round(time.monotonic() - started, 2)
            )
            name = f"meeting-{number:02d}-{mode}.json"
            sd.private_save(directory, name, result)
            distinct = len(
                {
                    sd.normalized_proposal_wording(value["recommendation"])
                    for value in result["first"].values()
                }
            )
            summaries.append(
                {
                    "meeting": number,
                    "mode": mode,
                    "valid": result["valid"],
                    "stage_responses": sum(
                        isinstance(x["raw"], str) for x in result["stages"]
                    ),
                    "requested_stages": sum(x["requested"] for x in result["stages"]),
                    "first_wording_count": distinct,
                    "seconds": result["seconds"],
                    "sample_hash": hashlib.sha256(
                        (directory / name).read_bytes()
                    ).hexdigest(),
                }
            )
            print(number, mode, result["valid"], result["seconds"], flush=True)
    sd.private_save(
        directory,
        "summary.json",
        {
            "meetings": summaries,
            "source_unchanged": hashes() == frozen["source_hashes"],
            "identity_unchanged": identity(tag) == frozen["model"],
            "semantic_review": "pending",
            "owner_accepted": False,
            "merged": False,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--freeze-previous")
    group.add_argument("--run")
    parser.add_argument(
        "--model",
        default="qwen2.5:14b-instruct-q4_K_M",
        choices=["llama3.1", "qwen2.5:14b-instruct-q4_K_M"],
    )
    args = parser.parse_args()
    (
        print(freeze(args.freeze_previous, args.model))
        if args.freeze_previous
        else run(args.run)
    )
