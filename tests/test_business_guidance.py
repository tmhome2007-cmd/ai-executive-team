"""Owner next steps reflect current source, assessment and permission gates."""

import unittest
from tests import test_sprint4_integration as fixtures
from memory.business_discovery import get_brief, claim_stage, create_brief
from memory.database import get_connection
from memory.evidence import review_source
from memory.executive_skills import bind_skill, decide_skill
from memory.workflow_templates import list_templates, review_template


class GuidanceTests(unittest.TestCase):
    setUp = fixtures.SprintFourIntegrationTests.setUp
    tearDown = fixtures.SprintFourIntegrationTests.tearDown
    payload = fixtures.SprintFourIntegrationTests.payload
    brief = fixtures.SprintFourIntegrationTests.brief
    sample = fixtures.SprintFourIntegrationTests.sample
    assess = fixtures.SprintFourIntegrationTests.assess
    accepted_examples = fixtures.SprintFourIntegrationTests.accepted_examples
    propose = fixtures.SprintFourIntegrationTests.propose
    interrupted = fixtures.SprintFourIntegrationTests.interrupted

    def test_pending_failed_and_passed_assessments_have_distinct_next_steps(self):
        b = self.brief()
        self.assertEqual(b["guidance"]["action"], "practice")
        b = self.sample(b)
        self.assertEqual(b["guidance"]["action"], "review_sample")
        self.assertIsNone(b["review"])
        b = self.assess(b, [False, True])
        self.assertEqual(b["guidance"]["action"], "revise")
        b = self.assess(b, [True, True], correction=True)
        self.assertEqual(b["guidance"]["action"], "read_sample")
        self.assertIn("not proof of usefulness", b["guidance"]["explanation"])
        self.assertEqual(len(b["attempts"][0]["reviews"]), 2)

    def test_missing_buyer_evidence_allows_only_private_practice_guidance(self):
        b = create_brief("Fictional research", "Private text only", self.ids)
        self.assertEqual(b["guidance"]["action"], "research")
        b = claim_stage(b["id"], b["version"], "research")
        from memory.business_discovery import finish_stage
        from workflows.business_research_contract import render_research

        b = finish_stage(
            b["id"],
            "research",
            render_research(self.payload(), b["research_sources"]),
            b["version"],
        )
        self.assertEqual(b["guidance"]["action"], "choose_practice")
        self.assertIn(
            "Missing buyer evidence blocks a business choice",
            b["guidance"]["explanation"],
        )
        self.assertIn("Selection blocked", b["research"])

    def test_disputed_source_blocks_generation_without_rewriting_brief(self):
        b = self.brief()
        review_source(self.ids[0], 1, "disputed")
        current = get_brief(b["id"])
        self.assertEqual(current["guidance"]["action"], "review_sources")
        self.assertTrue(current["guidance"]["blocked"])
        self.assertEqual(current["version"], b["version"])
        self.assertEqual(current["practice_specification"], b["practice_specification"])

    def test_revocation_blocks_new_generation_but_not_review_of_saved_sample(self):
        skill = self.propose()
        decide_skill(skill["id"], 1, "accepted", "Synthetic review")
        b = self.brief(facts="Independent fictional third exercise")
        with get_connection() as conn:
            bind_skill(conn.cursor(), b["id"], skill["id"])
            conn.commit()
        b = self.sample(b)
        decide_skill(skill["id"], 2, "revoked", "PRIVATE-SENTINEL")
        current = get_brief(b["id"])
        self.assertEqual(current["guidance"]["action"], "review_sample")
        current = self.assess(current, [False, True])
        self.assertTrue(current["guidance"]["blocked"])
        self.assertEqual(current["guidance"]["action"], "new_brief")
        self.assertNotIn("PRIVATE-SENTINEL", str(current["guidance"]))
        with self.assertRaises(ValueError):
            claim_stage(b["id"], current["version"], "revision")

    def test_withdrawn_workflow_has_blocked_recovery(self):
        b = self.brief()
        template = list_templates()[0]
        review_template(template["id"], 1, "reviewed", "Synthetic review")
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO business_workflow_bindings VALUES(?,?,?)",
                (b["id"], template["id"], "2026-10-11"),
            )
            conn.commit()
        review_template(template["id"], 2, "withdrawn", "PRIVATE-SENTINEL")
        current = get_brief(b["id"])
        self.assertTrue(current["guidance"]["blocked"])
        self.assertIn("withdrawn", current["guidance"]["explanation"])
        self.assertNotIn("PRIVATE-SENTINEL", str(current["guidance"]))

    def test_history_limit_blocks_revision_but_keeps_passed_sample_readable(self):
        b = self.brief()
        for attempt in range(10):
            b = self.sample(b, revision=attempt > 0)
            b = self.assess(b, [False, True])
        self.assertEqual(len(b["attempts"]), 10)
        self.assertEqual(b["guidance"]["action"], "new_brief")
        self.assertTrue(b["guidance"]["blocked"])
        with self.assertRaises(ValueError):
            claim_stage(b["id"], b["version"], "revision")
        b = self.assess(b, [True, True], correction=True)
        self.assertEqual(b["guidance"]["action"], "read_sample")
        self.assertEqual(len(b["attempts"]), 10)

    def test_interrupted_work_routes_to_inspector_and_keeps_frozen_inputs(self):
        b = self.brief()
        original = b["practice_specification"]
        self.interrupted(b)
        current = get_brief(b["id"])
        self.assertEqual(current["guidance"]["action"], "inspect_runs")
        self.assertEqual(current["practice_specification"], original)
        self.assertEqual(current["attempts"], [])
