"""Opt-in paired F04 development probe; no framework install or model judging."""

import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.sprint7_schema_experiment import identity
from scripts import sprint7_bound_review_experiment as previous_runner
from workflows import bound_review, evidence_review
from workflows.quality_benchmark import local_request
from workflows.structured_decision import private_save

STORE = previous_runner.STORE
MODEL = previous_runner.MODEL
ASSETS = (
    *previous_runner.ASSETS,
    "workflows/evidence_review.py",
    "scripts/sprint7_evidence_review_experiment.py",
)
OPTIONS = {"temperature": 0, "num_predict": 600, "num_ctx": 4096, "seed": 47}


def hashes():
    return {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in ASSETS
    }


def freeze(previous):
    previous = Path(previous).resolve()
    if previous.parent != STORE.resolve() or not previous.name.startswith("run-"):
        raise ValueError("Expected prior private development run")
    old = json.loads((previous / "freeze.json").read_text())
    if identity(MODEL) != old["model"]:
        raise ValueError("Installed model changed")
    cases = old["cases"]
    for name in old["order"]:
        cases[name]["slot"] = name + "-1"
    synthetic = [
        (
            "missing",
            {"record": "The seller group has 83,000 members."},
            "No evidence establishes intended contact eligibility; irrelevant true statistic is not support.",
        ),
        (
            "wrong_person",
            {
                "record": "Mira replied yesterday and has a current case. The intended contact is Noor."
            },
            "Mira's status must not transfer to Noor; relevant evidence of Noor's eligibility is missing.",
        ),
        (
            "outdated",
            {
                "historical": "In May, Noor had a current case.",
                "owner-correction": "Noor has not confirmed having a current case for today's test.",
            },
            "Historical eligibility is not current confirmation; preserve explicit current uncertainty.",
        ),
        (
            "partial",
            {
                "record": "Noor replied yesterday. Noor's own current case and willingness to test are unknown."
            },
            "A reply does not prove own-case eligibility or willingness; no supported compound positive claim.",
        ),
        (
            "multiple",
            {
                "record-a": "Noor replied yesterday confirming willingness to test.",
                "record-b": "Noor's own current case has not been confirmed.",
            },
            "Either/both relevant facts may justify private eligibility review; do not imply eligibility or re-open willingness.",
        ),
    ]
    target = bound_review.ReviewTarget(
        question="Does the intended contact Noor have their own eligible current input?",
        owner_check="Owner: privately review existing records for Noor's own eligible current input. Record missing evidence; do not contact anyone.",
    )
    for number, (name, sources, expected) in enumerate(synthetic, 1):
        cases[name] = {
            "slot": f"meeting-{number:02d}",
            "sources": sources,
            "catalog": {"eligibility": target.model_dump()},
            "unresolved_ids": ["eligibility"],
            "question": "Help choose a private check before inviting intended contact Noor to test their own current input. €0; no team contact, tools, publication or execution. Current eligibility is unconfirmed; one private owner review only.",
            "analyst_expected": expected,
        }
    directory = STORE / ("run-" + uuid.uuid4().hex)
    private_save(
        directory,
        "freeze.json",
        {
            "source_hashes": hashes(),
            "model": old["model"],
            "options": OPTIONS,
            "personality": old["personality"],
            "catalog": old["catalog"],
            "cases": cases,
            "order": [*old["order"], *[x[0] for x in synthetic]],
            "modes": ["baseline", "candidate"],
            "repairs": 0,
            "rubric": {
                "support": "Analyst labels premise/citation pairs supported, partially supported, contradicted, or insufficient/irrelevant. Also assess whether premises actually matter to the chosen check; true irrelevant facts do not pass.",
                "gap": "Honest insufficiency in supplied records is allowed; do not infer global absence or borrow another person's status. No forced citation. Baseline's mandatory citation is a disclosed limitation.",
                "F01": "All generated fields preserve person, time, known reply/willingness and unknown eligibility. No silent-interest inference, invented authority or reopening settled facts.",
                "utility": "A useful private conditional check survives missing evidence. A copied fact alone is not useful. Rationale is assessed as inference, not factual entailment or proof of best strategy.",
                "gate": "Compare all eight pairs, keep invalids. Require semantic improvement without critical factual or authority regression. Native validity alone is not adoption. Human owner acceptance/full-team/held-out evaluation remain separate.",
            },
            "scope": "Eight author-exposed development cases, one CFO sample/arm, sixteen calls, no retries. Original three variants plus five newly authored development diagnostics, not held-out. Same model/profile/sources/target catalog; candidate changes schema and prompt. Both arms use600token cap, unlike prior400cap; compare within this run only. Workflow supplies step text. No automatic semantic judge; no default, API, company record or dependency changes. meeting filenames are retention-compatible sample slots, not multi-role meetings. Analyst expectations never enter payloads.",
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
        or identity(MODEL) != frozen["model"]
        or frozen["options"] != OPTIONS
    ):
        raise ValueError("Frozen assets/model/options changed")
    private_save(directory, "started.json", {"time": time.time()})
    samples = []
    for name in frozen["order"]:
        case = frozen["cases"][name]
        targets = {
            key: bound_review.ReviewTarget.model_validate(value)
            for key, value in case.get("catalog", frozen["catalog"]).items()
        }
        for mode in frozen["modes"]:
            flow = bound_review if mode == "baseline" else evidence_review
            payload = flow.request_payload(
                frozen["model"]["configuration"]["resolved_tag"],
                case["question"],
                case["sources"],
                "cfo",
                frozen["personality"],
                targets,
                case["unresolved_ids"],
            )
            payload["options"] = dict(OPTIONS)
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
                    raise ValueError("Oversized input")
                reply = local_request(
                    "http://127.0.0.1:11434", "/api/generate", payload
                )
                result["raw"] = reply.get("response")
                if reply.get("done") is not True or not isinstance(result["raw"], str):
                    raise ValueError("Incomplete response")
                value = flow.validate(
                    result["raw"], case["sources"], targets, case["unresolved_ids"]
                )
                result["proposal"] = value.model_dump()
                result["rendered"] = flow.render(
                    value, case["sources"], targets, case["unresolved_ids"]
                )
                result["valid"] = True
            except Exception as error:
                result["error_type"] = type(error).__name__
            finally:
                result["seconds"] = round(time.monotonic() - started, 2)
                filename = f"{case['slot']}-{mode}.json"
                private_save(directory, filename, result)
                samples.append(
                    {key: result[key] for key in ("case", "mode", "valid", "seconds")}
                    | {
                        "filename": filename,
                        "sample_hash": hashlib.sha256(
                            (directory / filename).read_bytes()
                        ).hexdigest(),
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
