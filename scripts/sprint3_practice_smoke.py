#!/usr/bin/env python3
"""Optional real local-model examples on disposable data; never owner acceptance."""

import datetime
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture", choices=["task_guide", "evidence_summary", "support_draft"]
    )
    parser.add_argument(
        "--skip-research",
        action="store_true",
        help="Use a validated fictional comparison to isolate practice output",
    )
    parser.add_argument(
        "--sprint5-transfer",
        action="store_true",
        help="Use the frozen BE-35 support or greenhouse scenario with its existing rubric",
    )
    args = parser.parse_args()
    if args.sprint5_transfer and args.fixture not in {
        "support_draft",
        "evidence_summary",
    }:
        parser.error(
            "--sprint5-transfer requires --fixture support_draft or evidence_summary"
        )
    with tempfile.TemporaryDirectory(prefix="sprint3-local-examples-") as raw:
        temp = Path(raw)
        os.environ.update(
            CREWAI_STORAGE_DIR=str(temp / "crewai"),
            LOG_DIR=str(temp / "logs"),
            DATABASE_PATH=str(temp / "test.db"),
            WORKSPACE_ROOT=str(temp / "workspace"),
            ALLOW_REMOTE_LLM="false",
            CREWAI_DISABLE_TELEMETRY="true",
            CREWAI_TRACING_ENABLED="false",
            TELEGRAM_BOT_TOKEN="",
            TELEGRAM_CHAT_ID="",
            SANDBOX_MODE="true",
            OLLAMA_BASE_URL="http://localhost:11434",
            OLLAMA_MODEL="llama3.1",
        )
        from config import config
        from memory.database import init_db, get_connection
        from memory.evidence import create_source
        from memory.business_discovery import (
            create_brief,
            claim_stage,
            finish_stage,
            select_practice,
        )
        from memory.practice_quality import TEMPLATES
        from workflows.business_research_contract import render_research, SERVICES
        from workflows.business_discovery import run_stage, _reason

        directory = (
            ROOT
            / "audit-results"
            / ("sprint3-examples-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
        )
        directory.mkdir(mode=0o700, parents=True)
        with patch.object(config, "DATABASE_PATH", str(temp / "test.db")):
            init_db()
            now = datetime.datetime.now(datetime.timezone.utc)
            ids = [
                create_source(
                    source_key=f"fixture-{i}",
                    title="Fictional platform fixture",
                    reference=f"fictional fixture {i}",
                    summary="Fictional platform constraint. No buyer evidence or commercial facts are supplied.",
                    observed_at=now.isoformat(),
                )["id"]
                for i in range(3)
            ]
            research = create_brief(
                "Fictional local comparison",
                "Private practice only; no spending, publishing or customer contact.",
                ids,
            )
            print(
                (
                    "RUN real-local-research"
                    if not args.skip_research
                    else "SKIP real-local-research; isolate private sample generation"
                ),
                flush=True,
            )
            try:
                if not args.skip_research:
                    research = run_stage(
                        research["id"], research["version"], "research"
                    )
            except (ValueError, RuntimeError) as error:
                print("FAIL real-local-research: " + str(error), flush=True)
                return 1
            if not args.skip_research and research["state"] != "research_ready":
                print(
                    "FAIL real-local-research: generation still running or needs review",
                    flush=True,
                )
                return 1
            if not args.skip_research:
                (directory / "research.txt").write_text(research["research"])
                print(
                    "PASS real-local-research structural/source contract; business selection must remain blocked",
                    flush=True,
                )
            outcomes = []
            # Independent fixtures share a validated synthetic comparison so each
            # practice test measures its deliverable rather than redoing research.
            comparison = json.dumps(
                dict(
                    options=[
                        dict(
                            key=k,
                            skills=["Writing"],
                            exercise="Private fictional sample",
                            checks=["Preserves supplied facts", "Labels unknowns"],
                        )
                        for k in SERVICES
                    ],
                    practice_choice="documentation",
                )
            )
            for template in TEMPLATES:
                if args.fixture and template["key"] != args.fixture:
                    continue
                if args.sprint5_transfer:
                    example = next(
                        item
                        for item in json.loads(
                            (ROOT / "docs/planning/be35-examples.json").read_text()
                        )
                        if item["id"]
                        == {
                            "support_draft": "return-policy-transfer",
                            "evidence_summary": "greenhouse-transfer",
                        }[template["key"]]
                    )
                    if example["checks"] != template["checks"]:
                        raise ValueError(
                            "Transfer must preserve the exact support rubric"
                        )
                    template = dict(
                        template,
                        audience=example["audience"],
                        supplied_facts=example["facts"],
                        exercise=example["request"],
                    )
                b = create_brief(
                    "Fictional " + template["key"],
                    "Private local sample only; no owner professional skills assumed.",
                    ids,
                )
                b = claim_stage(b["id"], b["version"], "research")
                b = finish_stage(
                    b["id"],
                    "research",
                    render_research(comparison, b["research_sources"]),
                    b["version"],
                )
                b = select_practice(
                    b["id"],
                    b["version"],
                    template["service_key"],
                    template["exercise"],
                    template["checks"],
                    (now + datetime.timedelta(days=1)).isoformat(),
                    **{
                        k: template[k]
                        for k in (
                            "service_key",
                            "audience",
                            "supplied_facts",
                            "deliverable_kind",
                        )
                    },
                )
                print("RUN " + template["key"], flush=True)
                (directory / (template["key"] + "-specification.json")).write_text(
                    json.dumps(template, indent=2, ensure_ascii=False)
                )
                try:
                    captures = []

                    def capture(*args, **kwargs):
                        result = _reason(*args, **kwargs)
                        captures.append(result)
                        return result

                    with patch(
                        "workflows.business_discovery._reason", side_effect=capture
                    ):
                        b = run_stage(b["id"], b["version"], "practice")
                    ok = b["state"] == "sample_ready"
                except (ValueError, RuntimeError) as error:
                    ok = False
                    (directory / (template["key"] + "-failure.txt")).write_text(
                        str(error)
                    )
                    for index, draft in enumerate(captures):
                        (
                            directory
                            / (template["key"] + f"-withheld-draft-{index+1}.txt")
                        ).write_text(
                            "Withheld local-model test draft; structural checks failed. No owner acceptance.\n\n"
                            + draft
                        )
                if ok:
                    (directory / (template["key"] + ".txt")).write_text(
                        b["sample_display"]
                    )
                for index, draft in enumerate(captures):
                    (
                        directory / (template["key"] + f"-raw-draft-{index+1}.txt")
                    ).write_text(
                        "Raw local-model draft; may fail checks. Owner assessment not recorded.\n\n"
                        + draft
                    )
                outcomes.append(
                    dict(
                        fixture=template["key"],
                        structural_checks="PASS" if ok else "FAIL",
                        owner_assessment="not_recorded",
                    )
                )
                print(
                    ("PASS " if ok else "FAIL ")
                    + template["key"]
                    + " structural checks; owner usefulness assessment not recorded",
                    flush=True,
                )
            with get_connection() as conn:
                assert (
                    conn.execute("SELECT COUNT(*) FROM action_queue").fetchone()[0] == 0
                )
                assert (
                    conn.execute("SELECT COUNT(*) FROM treasury_entries").fetchone()[0]
                    == 0
                )
            (directory / "results.json").write_text(json.dumps(outcomes, indent=2))
            for file in directory.iterdir():
                if file.is_file():
                    file.chmod(0o600)
            print("Examples: " + str(directory), flush=True)
            return 0 if all(o["structural_checks"] == "PASS" for o in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
