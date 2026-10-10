"""Run/replay benchmark prompt versions using synthetic data and local Ollama."""

import argparse
import datetime
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from workflows.quality_benchmark import (
    PROMPT,
    OPTIONS,
    RUBRIC_VERSION,
    assess,
    comparable,
    checker_identity,
    digest,
    local_request,
)


def private_directory(path):
    """Reject symlinks before writing private benchmark snapshots."""
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink():
            raise ValueError("Benchmark storage cannot use symlinks")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def save(path, value):
    """Create an immutable owner-only snapshot; never overwrite an earlier run."""
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(descriptor, "w") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def run(args):
    """Persist progress after each attempt; missing attempts remain incomplete."""
    fixtures = json.loads((ROOT / "docs/planning/quality-fixtures-v1.json").read_text())
    store = private_directory(ROOT / "quality-results")
    versions = private_directory(store / "prompts")
    prompt = PROMPT
    if args.prompt_version:
        if len(args.prompt_version) != 64 or any(
            c not in "0123456789abcdef" for c in args.prompt_version
        ):
            raise ValueError("Use the full saved prompt hash")
        version_path = versions / (args.prompt_version + ".json")
        if version_path.is_symlink() or version_path.stat().st_size > 100000:
            raise ValueError("Invalid saved prompt file")
        prompt = json.loads(version_path.read_text())["prompt"]
        if digest(prompt) != args.prompt_version:
            raise ValueError("Saved prompt version failed integrity check")
    if not isinstance(prompt, str) or not 1 <= len(prompt) <= 20000:
        raise ValueError("Invalid prompt snapshot")
    if len(fixtures) != 10 or len({f["id"] for f in fixtures}) != 10:
        raise ValueError("Benchmark requires ten distinct fixtures")
    prompt_hash = digest(prompt)
    snapshot = versions / (prompt_hash + ".json")
    if snapshot.is_symlink():
        raise ValueError("Prompt snapshots cannot use symlinks")
    if snapshot.exists() and json.loads(snapshot.read_text()) != {
        "prompt": prompt,
        "hash": prompt_hash,
    }:
        raise ValueError("Prompt snapshot integrity failure")
    if not snapshot.exists():
        save(snapshot, {"prompt": prompt, "hash": prompt_hash})
    model = args.model.removeprefix("ollama/")
    tags = local_request(args.base_url, "/api/tags")
    matched = [
        x for x in tags.get("models", []) if x.get("name") in {model, model + ":latest"}
    ]
    if not matched:
        raise ValueError("Requested model is not installed in local Ollama")
    model_info = {
        "name": matched[0]["name"],
        "digest": matched[0].get("digest", "unknown"),
    }
    report = {
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "dataset_hash": digest(fixtures),
        "checker_hash": checker_identity(),
        "rubric_version": RUBRIC_VERSION,
        "prompt_hash": prompt_hash,
        "model": model_info,
        "options": {
            **OPTIONS,
            "response_format": (
                "json" if getattr(args, "json_output", False) else "unconstrained"
            ),
        },
        "planned_attempts": len(fixtures) * 3,
        "attempts": [],
        "summary": {},
        "limit": "Token coverage and contract checks are not semantic verification. No AI judge, owner acceptance or launch permission.",
    }
    run_id = uuid.uuid4().hex
    directory = private_directory(store / run_id)
    save(
        directory / "manifest.json",
        {k: v for k, v in report.items() if k not in {"attempts", "summary"}},
    )
    print(f"Run {run_id}: 30 fictional attempts; prompt {prompt_hash}", flush=True)
    try:
        for fixture in fixtures:
            for repeat in range(3):
                attempt = {"fixture": fixture["id"], "repeat": repeat + 1}
                try:
                    result = local_request(
                        args.base_url,
                        "/api/generate",
                        {
                            "model": model_info["name"],
                            "stream": False,
                            "options": OPTIONS,
                            **(
                                {"format": "json"}
                                if getattr(args, "json_output", False)
                                else {}
                            ),
                            "prompt": prompt
                            + "\nFacts: "
                            + fixture["facts"]
                            + "\nNamed unknown: "
                            + fixture["unknown"],
                        },
                    )
                    if result.get("done") is not True or not isinstance(
                        result.get("response"), str
                    ):
                        raise ValueError("Incomplete generation")
                    attempt["output"] = result["response"]
                    attempt["errors"] = assess(attempt["output"], fixture)
                    attempt["status"] = "failed" if attempt["errors"] else "passed"
                except Exception as error:
                    attempt.update(status="error", errors=[type(error).__name__])
                report["attempts"].append(attempt)
                save(directory / f'attempt-{len(report["attempts"]):02}.json', attempt)
                print(
                    f'{len(report["attempts"])}/30 {fixture["id"]}: {attempt["status"]}',
                    flush=True,
                )
    finally:
        statuses = [x["status"] for x in report["attempts"]]
        report["summary"] = {
            "passed": statuses.count("passed"),
            "failed": statuses.count("failed"),
            "errors": statuses.count("error"),
            "incomplete": 30 - len(statuses),
            "denominator": 30,
        }
        save(directory / "report.json", report)
        print(json.dumps(report["summary"]))
        print(f'Report: {directory / "report.json"}')
    return 0 if report["summary"]["passed"] == 30 else 1


def recheck(path):
    """Reassess preserved raw answers under today's checker without new inference."""
    original = json.loads(path.read_text())
    fixtures = json.loads((ROOT / "docs/planning/quality-fixtures-v1.json").read_text())
    if original["dataset_hash"] != digest(fixtures):
        raise ValueError("Cannot recheck different fixture inputs")
    lookup = {fixture["id"]: fixture for fixture in fixtures}
    seen = set()
    attempts = []
    for attempt in original["attempts"]:
        identity = (attempt["fixture"], attempt["repeat"])
        if (
            identity in seen
            or identity[0] not in lookup
            or identity[1] not in (1, 2, 3)
        ):
            raise ValueError("Invalid attempt identities")
        seen.add(identity)
        item = dict(attempt)
        if item["status"] in {"passed", "failed"} and isinstance(
            item.get("output"), str
        ):
            item["errors"] = assess(item["output"], lookup[identity[0]])
            item["status"] = "failed" if item["errors"] else "passed"
        elif item["status"] != "error":
            raise ValueError("Invalid attempt status")
        attempts.append(item)
    result = dict(
        original,
        attempts=attempts,
        checker_hash=checker_identity(),
        rubric_version=RUBRIC_VERSION,
        source_report_hash=digest(original),
        source_run=path.parent.name,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )
    statuses = [item["status"] for item in attempts]
    result["summary"] = {
        "passed": statuses.count("passed"),
        "failed": statuses.count("failed"),
        "errors": statuses.count("error"),
        "incomplete": 30 - len(attempts),
        "denominator": 30,
    }
    destination = private_directory(
        private_directory(ROOT / "quality-results") / uuid.uuid4().hex
    )
    save(destination / "report.json", result)
    print("Rechecked preserved answers; no new model generation.")
    print(json.dumps(result["summary"]))
    print("Report:", destination / "report.json")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("run")
    generate.add_argument(
        "--json-output",
        action="store_true",
        help="Compare Ollama constrained JSON generation; raw answers are still checked",
    )
    generate.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", "llama3.1"))
    generate.add_argument(
        "--base-url",
        default=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
    )
    generate.add_argument(
        "--prompt-version",
        help="Replay an older saved benchmark prompt; production prompts stay unchanged",
    )
    recheck_parser = sub.add_parser("recheck")
    recheck_parser.add_argument("report", type=Path)
    summary = sub.add_parser("summary")
    summary.add_argument("--run-id", default=None)
    sub.add_parser("versions")
    compare = sub.add_parser("compare")
    compare.add_argument("left", type=Path)
    compare.add_argument("right", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "run":
            return run(args)
        if args.command == "recheck":
            return recheck(args.report)
        if args.command == "versions":
            for path in sorted((ROOT / "quality-results/prompts").glob("*.json")):
                print(path.stem)
            return 0
        if args.command == "summary":
            paths = list((ROOT / "quality-results").glob("*/report.json"))
            if args.run_id:
                paths = [p for p in paths if p.parent.name == args.run_id]
            if not paths:
                raise ValueError("No completed report")
            path = max(paths, key=lambda p: p.stat().st_mtime)
            report = json.loads(path.read_text())
            print("Latest saved run:", path.parent.name)
            print("Model:", report["model"]["name"])
            print("Contract results:", json.dumps(report["summary"]))
            failures = {}
            for attempt in report["attempts"]:
                for error in attempt.get("errors", []):
                    failures[error] = failures.get(error, 0) + 1
            for error, count in failures.items():
                print(f"{count} attempts: {error}")
            print(report["limit"])
            return 0
        print(
            json.dumps(
                comparable(
                    json.loads(args.left.read_text()),
                    json.loads(args.right.read_text()),
                ),
                indent=2,
            )
        )
        return 0
    except KeyboardInterrupt:
        print("Stopped; completed attempt snapshots retained.")
        return 130
    except (ValueError, OSError, KeyError):
        print(
            "Benchmark unavailable: check local Ollama/model, report compatibility or saved prompt version. No key or company data changed."
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
