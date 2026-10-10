"""Real SQLite proof of review-bound skill reuse and revocation boundaries."""

import json
import sqlite3
from unittest.mock import patch
from fastapi.testclient import TestClient
import unittest
from tests import test_sprint3_practice_evidence as practice_fixtures
from memory.database import get_connection
from memory.business_discovery import get_brief, claim_stage, finish_stage
from memory.executive_skills import (
    create_skill,
    decide_skill,
    get_skill,
    bind_skill,
    eligible_reviews,
)
from config import config


class ExecutiveSkillsTests(unittest.TestCase):
    # Reuse the disposable fixture builders without rerunning inherited test cases.
    setUp = practice_fixtures.SprintThreeTests.setUp
    tearDown = practice_fixtures.SprintThreeTests.tearDown
    payload = practice_fixtures.SprintThreeTests.payload
    brief = practice_fixtures.SprintThreeTests.brief
    sample = practice_fixtures.SprintThreeTests.sample
    assess = practice_fixtures.SprintThreeTests.assess

    def accepted_examples(self):
        result = []
        for facts in (
            "Fictional app alpha supports create. Unknown reminders.",
            "Fictional app beta supports edit. Unknown reminders.",
        ):
            result.append(
                self.assess(self.sample(self.brief(facts=facts)), [True, True])
            )
        self.examples = result
        return [item["attempts"][-1]["reviews"][-1]["id"] for item in result]

    def propose(self):
        return create_skill(
            "evidence-summary",
            "Private evidence summary",
            "1. Read the new facts.\n2. Preserve counts.\n3. Label unknowns and request owner review.",
            "Matching private exercise rubric",
            "No tools, money or launch. Every new sample needs review.",
            self.accepted_examples(),
        )

    def test_acceptance_reuse_and_revocation_keep_history(self):
        skill = self.propose()
        self.assertFalse(skill["usable"])
        third = self.brief(
            facts="Fictional app gamma supports completion; interface unknown."
        )
        with get_connection() as conn, self.assertRaises(ValueError):
            bind_skill(conn.cursor(), third["id"], skill["id"])
        accepted = decide_skill(
            skill["id"], 1, "accepted", "Reviewed procedure and both exact examples"
        )
        self.assertTrue(accepted["usable"])
        with get_connection() as conn:
            bind_skill(conn.cursor(), third["id"], skill["id"])
            conn.commit()
        self.assertEqual(get_brief(third["id"])["skill_version"]["id"], skill["id"])
        running = claim_stage(third["id"], third["version"], "practice")
        published = finish_stage(
            third["id"],
            "practice",
            "Private fictional third example with unknowns and no owner approval.",
            running["version"],
        )
        reviewed = self.assess(published, [True, True])
        decide_skill(skill["id"], 2, "revoked", "Owner revoked this procedure")
        self.assertEqual(get_brief(third["id"])["attempts"], reviewed["attempts"])
        with self.assertRaises(ValueError):
            claim_stage(third["id"], reviewed["version"], "revision")
        with self.assertRaises(RuntimeError):
            decide_skill(skill["id"], 2, "accepted", "Cannot restore a revoked version")

    def test_same_example_and_changed_rubric_are_rejected(self):
        skill = self.propose()
        decide_skill(skill["id"], 1, "accepted", "Reviewed")
        for third in (
            self.brief(facts="Fictional app alpha supports create. Unknown reminders."),
            self.brief(
                facts="Different facts", checks=["Changed check", "Other check"]
            ),
        ):
            with get_connection() as conn, self.assertRaises(ValueError):
                bind_skill(conn.cursor(), third["id"], skill["id"])
        with self.assertRaises(ValueError):
            create_skill(
                "bad-key",
                "Name",
                "Procedure",
                "Prereq",
                "Limits",
                [skill["evidence"][0]["review_id"]] * 2,
            )

    def test_corrected_source_invalidates_future_use(self):
        skill = self.propose()
        decide_skill(skill["id"], 1, "accepted", "Reviewed")
        self.assess(self.examples[0], [False, True], correction=True)
        self.assertFalse(get_skill(skill["id"])["usable"])
        self.assertNotIn(
            skill["evidence"][0]["review_id"],
            [x["review_id"] for x in eligible_reviews()],
        )
        third = self.brief(facts="Fictional third facts")
        with get_connection() as conn, self.assertRaises(ValueError):
            bind_skill(conn.cursor(), third["id"], skill["id"])

    def test_revocation_blocks_inflight_publication(self):
        skill = self.propose()
        decide_skill(skill["id"], 1, "accepted", "Reviewed")
        third = self.brief(facts="Independent fictional third exercise")
        with get_connection() as conn:
            bind_skill(conn.cursor(), third["id"], skill["id"])
            conn.commit()
        running = claim_stage(third["id"], third["version"], "practice")
        decide_skill(
            skill["id"], 2, "revoked", "Withdrawn while generation was running"
        )
        with self.assertRaises(ValueError):
            finish_stage(
                third["id"], "practice", "Private generated answer", running["version"]
            )
        self.assertEqual(get_brief(third["id"])["attempts"], [])
        self.assertEqual(
            finish_stage(third["id"], "practice", None, running["version"])["state"],
            "needs_review",
        )

    def test_append_only_and_new_versions(self):
        skill = self.propose()
        with get_connection() as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "UPDATE executive_skill_versions SET procedure='changed' WHERE id=?",
                    (skill["id"],),
                )
        next_version = create_skill(
            skill["skill_key"],
            "New draft",
            "New procedure",
            "Prerequisites",
            "Limitations",
            [x["review_id"] for x in skill["evidence"]],
        )
        self.assertEqual(next_version["version"], 2)
        self.assertEqual(get_skill(skill["id"])["procedure"], skill["procedure"])

    def test_owner_api_auth_validation_and_stale_state(self):
        from main import app

        skill = self.propose()
        client = TestClient(app)
        with patch.object(config, "API_SECRET_KEY", "synthetic-skills-owner-key"):
            headers = {"X-API-Key": config.API_SECRET_KEY}
            self.assertEqual(client.get("/skills").status_code, 401)
            self.assertEqual(
                client.post(
                    f"/skills/{skill['id']}/decision",
                    json={"expected_version": 1, "state": "accepted", "note": "Review"},
                ).status_code,
                401,
            )
            self.assertEqual(
                client.get("/skills", headers=headers).headers["cache-control"],
                "no-store",
            )
            self.assertEqual(
                client.post(
                    f"/skills/{skill['id']}/decision",
                    headers=headers,
                    json={
                        "expected_version": 1,
                        "state": "accepted",
                        "note": "Reviewed",
                    },
                ).status_code,
                200,
            )
            self.assertEqual(
                client.post(
                    f"/skills/{skill['id']}/decision",
                    headers=headers,
                    json={
                        "expected_version": 1,
                        "state": "accepted",
                        "note": "Repeated",
                    },
                ).status_code,
                409,
            )
            payload = dict(
                skill_key="other",
                name="Other",
                procedure="Procedure",
                prerequisites="Prereq",
                limitations="Limits",
                review_ids=[True, 1],
            )
            self.assertEqual(
                client.post("/skills", headers=headers, json=payload).status_code, 422
            )

    def test_failed_binding_rolls_back_plan_and_generation_uses_procedure(self):
        from memory.business_discovery import create_brief, select_practice
        from workflows.business_research_contract import render_research
        from workflows.business_discovery import run_stage
        import datetime

        skill = self.propose()
        fresh = create_brief("New reuse", "Private only", self.ids)
        running = claim_stage(fresh["id"], fresh["version"], "research")
        fresh = finish_stage(
            fresh["id"],
            "research",
            render_research(self.payload(), running["research_sources"]),
            running["version"],
        )
        due = (
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)
        ).isoformat()
        values = dict(
            service_key="documentation",
            audience="Owner",
            supplied_facts="Fictional third case: a reminder is unknown",
            deliverable_kind="other_text",
            skill_version_id=skill["id"],
        )
        with self.assertRaises(ValueError):
            select_practice(
                fresh["id"],
                fresh["version"],
                "Documentation",
                "Draft a private summary",
                ["Preserves facts", "Labels unknowns"],
                due,
                **values,
            )
        self.assertEqual(get_brief(fresh["id"])["state"], "research_ready")
        self.assertIsNone(get_brief(fresh["id"])["practice_specification"])
        decide_skill(skill["id"], 1, "accepted", "Reviewed exact version")
        prepared = select_practice(
            fresh["id"],
            fresh["version"],
            "Documentation",
            "Draft a private summary",
            ["Preserves facts", "Labels unknowns"],
            due,
            **values,
        )

        def reason(prompt, structured=False):
            self.assertIn(skill["procedure"].splitlines()[0], prompt)
            self.assertIn("Fictional third case", prompt)
            return "The fictional third case says a reminder is unknown. No cause or interface details are established. Request supplied evidence before choosing a further private test. Owner review is pending."

        with (
            patch("workflows.business_discovery._local_agent"),
            patch(
                "workflows.business_discovery._reason", side_effect=reason
            ) as inference,
        ):
            result = run_stage(prepared["id"], prepared["version"], "practice")
        self.assertEqual(result["state"], "sample_ready")
        self.assertEqual(inference.call_count, 1)
        self.assertEqual(
            get_skill(skill["id"])["uses"][0]["owner_assessment"], "not_assessed"
        )

    def test_revocation_stops_repair_inference(self):
        from workflows.business_discovery import run_stage

        skill = self.propose()
        decide_skill(skill["id"], 1, "accepted", "Reviewed")
        third = self.brief(facts="Unfamiliar third case")
        with get_connection() as conn:
            bind_skill(conn.cursor(), third["id"], skill["id"])
            conn.commit()

        def revoked_during_inference(prompt, structured=False):
            decide_skill(skill["id"], 2, "revoked", "Withdrawn during generation")
            return "Invalid short draft"

        with (
            patch("workflows.business_discovery._local_agent"),
            patch(
                "workflows.business_discovery._reason",
                side_effect=revoked_during_inference,
            ) as inference,
        ):
            with self.assertRaises(ValueError):
                run_stage(third["id"], third["version"], "practice")
        self.assertEqual(inference.call_count, 1)
        self.assertEqual(get_brief(third["id"])["state"], "needs_review")
