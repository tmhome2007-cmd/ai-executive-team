"""Full fictional private-work chain; synthetic assessments never imply owner consent."""

import json
import unittest
from pathlib import Path
from unittest.mock import patch
from config import config
from tests import test_sprint3_practice_evidence as fixtures
from memory.business_discovery import review_practice
from memory.practice_artifacts import (
    export_sample,
    download_artifact,
    compare_artifacts,
)
from memory.executive_skills import create_skill, decide_skill, bind_skill
from memory.database import get_connection
from workflows.business_discovery import run_stage

SCENARIO = json.loads(
    (
        Path(__file__).resolve().parents[1] / "docs/planning/be40-scenario.json"
    ).read_text()
)


class PrivateAcceptanceTests(unittest.TestCase):
    setUp = fixtures.SprintThreeTests.setUp
    tearDown = fixtures.SprintThreeTests.tearDown
    payload = fixtures.SprintThreeTests.payload
    brief = fixtures.SprintThreeTests.brief
    assess = fixtures.SprintThreeTests.assess

    def generate(self, b, text, stage="practice"):
        response = (
            json.dumps(
                dict(
                    revised_sample=text,
                    changes=["Named the supplied unknowns explicitly"],
                    remaining_unknowns=["Interface controls and reminders"],
                )
            )
            if stage == "revision"
            else text
        )
        with patch(
            "workflows.business_discovery._reason", return_value=response
        ) as reason:
            result = run_stage(b["id"], b["version"], stage)
        self.assertEqual(reason.call_count, 1)
        self.assertEqual(result["state"], "sample_ready")
        self.assertIsNone(result["review"])
        self.assertEqual(result["guidance"]["action"], "review_sample")
        return result

    def test_complete_private_work_feedback_files_and_reviewed_procedure_reuse(self):
        config.DATABASE_PATH = str(Path(config.DATABASE_PATH).resolve())
        b = self.brief(facts=SCENARIO["facts"][0], checks=SCENARIO["checks"])
        spec = b["practice_specification"]
        frozen = b["research_sources"]
        b = self.generate(b, SCENARIO["first_draft"])
        original_id = b["attempts"][0]["id"]
        before = export_sample(original_id, "txt")
        original_bytes = download_artifact(before["id"])[0]
        with self.assertRaises(ValueError):
            create_skill(
                "premature",
                "Cannot use unassessed work",
                "Read facts",
                "Matching rubric",
                "Private only",
                [1, 2],
            )
        b = review_practice(
            b["id"],
            b["version"],
            SCENARIO["first_results"],
            SCENARIO["feedback"],
            fixtures.NOW(),
        )
        first_review = b["attempts"][0]["reviews"][-1]["id"]
        self.assertEqual(b["guidance"]["action"], "revise")
        b = self.generate(b, SCENARIO["revised_draft"], "revision")
        self.assertEqual(b["practice_specification"], spec)
        self.assertEqual(b["research_sources"], frozen)
        self.assertEqual(b["attempts"][1]["parent_sample_id"], original_id)
        self.assertEqual(b["attempts"][1]["feedback_review_id"], first_review)
        after = export_sample(b["attempts"][1]["id"], "md")
        diff = compare_artifacts(before["id"], after["id"])
        self.assertFalse(diff["identical"])
        self.assertIn("Interface controls", diff["diff"])
        self.assertEqual(download_artifact(before["id"])[0], original_bytes)
        b = self.assess(b, SCENARIO["revised_results"])
        comparison = b["feedback_summary"]["comparisons"][0]
        self.assertEqual(comparison["improved_checks"], ["Labels unknowns"])
        self.assertEqual(comparison["remaining_failures"], [])
        self.assertEqual(b["guidance"]["action"], "read_sample")
        second = self.brief(facts=SCENARIO["facts"][1], checks=SCENARIO["checks"])
        second = self.generate(
            second,
            SCENARIO["revised_draft"]
            .replace("alpha", "beta")
            .replace("creating", "editing")
            .replace("create function", "edit function"),
        )
        second = self.assess(second, [True, True])
        passing = [
            b["attempts"][-1]["reviews"][-1]["id"],
            second["attempts"][-1]["reviews"][-1]["id"],
        ]
        skill = create_skill(
            "private-task-clarity",
            "Private task clarity",
            "Read the current supplied facts; name unknown controls and reminders explicitly.",
            "Same approved rubric",
            "Text practice only; every new sample needs assessment.",
            passing,
        )
        third = self.brief(facts=SCENARIO["facts"][2], checks=SCENARIO["checks"])
        with get_connection() as conn, self.assertRaises(ValueError):
            bind_skill(conn.cursor(), third["id"], skill["id"])
        decide_skill(
            skill["id"],
            1,
            "accepted",
            "Synthetic acceptance for this test only; not actual owner acceptance.",
        )
        with get_connection() as conn:
            bind_skill(conn.cursor(), third["id"], skill["id"])
            conn.commit()
        third = self.generate(
            third,
            SCENARIO["revised_draft"]
            .replace("alpha", "gamma")
            .replace("creating", "completing")
            .replace("create function", "complete function"),
        )
        self.assertIsNone(third["review"])
        self.assertEqual(third["skill_version"]["id"], skill["id"])
        self.assertEqual(
            third["practice_specification"]["rubric_digest"], spec["rubric_digest"]
        )
        with get_connection() as conn:
            for table in (
                "actions",
                "resource_requests",
                "execution_runs",
                "capital_events",
            ):
                exists = conn.execute(
                    "SELECT name FROM sqlite_master WHERE name=?", (table,)
                ).fetchone()
                if exists:
                    self.assertEqual(
                        conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0
                    )
        self.assertEqual(download_artifact(before["id"])[0], original_bytes)
