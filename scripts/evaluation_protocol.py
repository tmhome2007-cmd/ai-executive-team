"""Verify the frozen Sprint 6 evaluation inputs offline; never run inference."""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = {
    "development-cases.json",
    "held-out-cases.json",
    "rubric.json",
    "baseline-prompt.txt",
    "legacy-output-quality-v2.txt",
    "legacy-quality-benchmark-v1.txt",
}


def validate(directory):
    """Reject altered inputs, unsafe paths, overlapping splits and bad schedules."""
    directory = Path(directory)
    manifest = json.loads((directory / "freeze.json").read_text())
    if manifest["version"] != "sprint6-evaluation-freeze-v1":
        raise ValueError("Unsupported evaluation freeze")
    if set(manifest["files"]) != ASSETS:
        raise ValueError("Unexpected or missing evaluation asset")
    for name, expected in manifest["files"].items():
        path = directory / name
        if path.is_symlink() or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("Invalid evaluation asset")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Frozen evaluation asset changed: " + name)
    splits = {}
    for split, name in (
        ("development", "development-cases.json"),
        ("held_out", "held-out-cases.json"),
    ):
        cases = json.loads((directory / name).read_text())
        if len(cases) != 8:
            raise ValueError("Expected eight cases per split")
        ids = []
        for case in cases:
            ids.append(case["id"])
            sources = case["sources"]
            source_ids = [source["id"] for source in sources]
            if (
                not isinstance(case["id"], str)
                or not case["id"]
                or not case["question"].strip()
                or not case["allowed_next_step"].strip()
                or not sources
                or len(set(source_ids)) != len(source_ids)
                or any(not source["text"].strip() for source in sources)
                or any(
                    not isinstance(case["evidence_contract"][key], list)
                    or not case["evidence_contract"][key]
                    or any(
                        not isinstance(value, str) or not value.strip()
                        for value in case["evidence_contract"][key]
                    )
                    for key in ("must_preserve", "unknowns", "must_not_claim")
                )
            ):
                raise ValueError("Incomplete case evidence contract")
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate evaluation case")
        splits[split] = ids
    if set(splits["development"]) & set(splits["held_out"]):
        raise ValueError("Evaluation splits overlap")
    rubric = json.loads((directory / "rubric.json").read_text())
    if (
        rubric["repeats"] != 3
        or rubric["cases_per_split"] != 8
        or rubric["scheduled_samples_per_variant_per_split"] != 24
        or set(rubric["axes"])
        != {"schema", "grounding", "unsupported_claims", "usefulness"}
    ):
        raise ValueError("Unexpected evaluation rubric or denominator")
    if not re.fullmatch(r"[0-9a-f]{64}", manifest["model"]["digest"]):
        raise ValueError("Missing frozen model digest")
    return {
        "freeze_hash": hashlib.sha256(
            (directory / "freeze.json").read_bytes()
        ).hexdigest(),
        "splits": splits,
        "scheduled_samples_per_variant_per_split": 24,
        "generation_performed": False,
    }


def model_input(case):
    """Exclude assessment obligations from the generation input."""
    return json.dumps(
        {key: case[key] for key in ("id", "question", "sources", "allowed_next_step")},
        ensure_ascii=False,
        sort_keys=True,
    )


def main():
    result = validate(ROOT / "docs/evaluation/sprint6")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
