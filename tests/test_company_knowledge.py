"""Real SQLite navigation, truthful explanations and shared memory exclusions."""

import datetime
import json
import unittest
from unittest.mock import patch
from tests import test_sprint3_practice_evidence as fixtures
from memory.database import (
    get_connection,
    create_company_goal,
    log_decision,
    propose_action,
    create_executive_memory,
    get_executive_memories,
    action_provenance_scope,
)
from memory.company_knowledge import search_knowledge, knowledge_record
from memory.memory_reconciliation import reconcile_memory
from memory.evidence import review_source, add_evidence_link


class CompanyKnowledgeTests(unittest.TestCase):
    setUp = fixtures.SprintThreeTests.setUp
    tearDown = fixtures.SprintThreeTests.tearDown
    payload = fixtures.SprintThreeTests.payload
    brief = fixtures.SprintThreeTests.brief
    sample = fixtures.SprintThreeTests.sample
    assess = fixtures.SprintThreeTests.assess

    def lesson(self, text="Synthetic lesson", key="lesson", **fields):
        return create_executive_memory(
            executive_key="ceo",
            memory_kind="general_lesson",
            lesson=text,
            fingerprint=key,
            **fields,
        )[0]

    def annotate(self, ident, **fields):
        return reconcile_memory(
            ident,
            expected_version=1,
            operation="annotate",
            source_ids=[self.ids[0]],
            note="Synthetic owner annotation",
            **fields,
        )

    def chain(self):
        goal = create_company_goal(
            "Synthetic mission",
            "Private test",
            "Document observations",
            status="active",
        )
        decision = log_decision(
            "Synthetic decision",
            ["ceo"],
            "Private task",
            "Unverified recommendation",
            True,
            goal_id=goal,
            source_ids=self.ids,
        )
        with get_connection() as conn:
            decision_uuid = conn.execute(
                "SELECT sync_uuid FROM decisions WHERE id=?", (decision,)
            ).fetchone()[0]
        with action_provenance_scope(decision, decision_uuid, "preparation"):
            action = propose_action(
                "cto",
                "Private proposed text",
                "Synthetic action; not executed",
                expected_outcome="Expected private result",
                expected_cost_amount=0,
                currency="EUR",
            )
        lesson = self.lesson(
            source_goal_id=goal, source_decision_id=decision, source_action_id=action
        )
        return goal, decision, action, lesson

    def test_recorded_chain_and_metadata_privacy(self):
        goal, decision, action, lesson = self.chain()
        for kind, ident, target, target_id in [
            ("goal", goal, "decision", decision),
            ("decision", decision, "action", action),
            ("action", action, "outcome", action),
            ("outcome", action, "action", action),
            ("lesson", lesson, "decision", decision),
        ]:
            record = knowledge_record(kind, ident)
            self.assertTrue(
                any(
                    l["target"]["kind"] == target
                    and l["target"]["id"] == target_id
                    and l["available"]
                    for l in record["links"]
                )
            )
        result = json.dumps(search_knowledge()) + json.dumps(
            knowledge_record("action", action)
        )
        self.assertNotIn("Synthetic action; not executed", result)
        for private in [
            "approval_seal",
            "action_detail",
            "result_detail",
            "API_SECRET_KEY",
        ]:
            self.assertNotIn(private, result)
        self.assertEqual(
            knowledge_record("decision", decision)["node"]["approval_status"], "pending"
        )

    def test_correction_withholds_original_and_keeps_provenance(self):
        old = self.lesson("Old synthetic fact")
        result = reconcile_memory(
            old,
            expected_version=1,
            operation="correct",
            source_ids=[self.ids[0]],
            note="Source-backed correction",
            lesson="Corrected synthetic fact",
        )
        new = result["replacement_id"]
        current = search_knowledge(kind="lesson", mode="current")["items"]
        self.assertEqual([r["id"] for r in current], [new])
        self.assertEqual([r["id"] for r in get_executive_memories("ceo")], [new])
        historical = knowledge_record("lesson", old)
        self.assertEqual(historical["details"]["lesson"], "Old synthetic fact")
        self.assertFalse(historical["node"]["context"]["eligible"])
        self.assertTrue(
            any(
                l["target"]["id"] == new and l["relation"] == "corrected by"
                for l in historical["links"]
            )
        )
        self.assertEqual(
            historical["details"]["revisions"][0]["note"], "Source-backed correction"
        )
        self.assertEqual(len(search_knowledge(kind="lesson")["items"]), 2)

    def test_conflicts_expiry_and_dispute_explanations_match_retrieval(self):
        a = self.lesson("First inconsistent claim", "a")
        b = self.lesson("Other inconsistent claim", "b")
        self.annotate(a, claim_key="same-fact")
        self.annotate(b, claim_key="same-fact")
        expired = self.lesson("Expired claim", "expired")
        self.annotate(expired, expires_at="2020-01-01T00:00:00Z")
        disputed = self.lesson("Disputed source claim", "disputed")
        self.annotate(disputed)
        review_source(self.ids[0], 1, "disputed")
        self.assertEqual(get_executive_memories("ceo"), [])
        self.assertFalse(search_knowledge(kind="lesson", mode="current")["items"])
        for ident in [a, b, expired, disputed]:
            self.assertFalse(
                knowledge_record("lesson", ident)["node"]["context"]["eligible"]
            )
        self.assertIn(
            "conflicting_claim",
            knowledge_record("lesson", a)["node"]["context"]["reasons"],
        )
        self.assertIn(
            "expired", knowledge_record("lesson", expired)["node"]["context"]["reasons"]
        )
        self.assertIn(
            "source_disputed",
            knowledge_record("lesson", disputed)["node"]["context"]["reasons"],
        )

    def test_missing_source_and_expired_source_fail_closed(self):
        missing = self.lesson("Missing evidence", "missing")
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO memory_lifecycle(memory_id,source_ids) VALUES(?,?)",
                (missing, "[999999]"),
            )
            conn.commit()
        self.assertIn(
            "source_missing",
            knowledge_record("lesson", missing)["node"]["context"]["reasons"],
        )
        from memory.evidence import create_source

        source = create_source(
            source_key="expired-evidence",
            title="Old evidence",
            reference="Synthetic test",
            summary="Old synthetic source",
            observed_at="2020-01-01T00:00:00Z",
            expires_at="2020-02-01T00:00:00Z",
        )
        expired = self.lesson("Expired evidence", "expired-evidence")
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO memory_lifecycle(memory_id,source_ids) VALUES(?,?)",
                (expired, json.dumps([source["id"]])),
            )
            conn.commit()
        self.assertIn(
            "source_expired",
            knowledge_record("lesson", expired)["node"]["context"]["reasons"],
        )
        self.assertIn(
            "expired", knowledge_record("evidence", source["id"])["node"]["warnings"]
        )
        self.assertEqual(get_executive_memories("ceo"), [])

    def test_stable_identity_mismatch_is_not_a_followable_link(self):
        goal, decision, action, lesson = self.chain()
        with get_connection() as conn:
            conn.execute(
                "UPDATE action_queue SET source_decision_sync_uuid=? WHERE id=?",
                ("wrong-cross-machine-identity", action),
            )
            conn.commit()
        for kind, ident, target in [
            ("action", action, "decision"),
            ("decision", decision, "action"),
        ]:
            links = [
                l
                for l in knowledge_record(kind, ident)["links"]
                if l["target"]["kind"] == target
            ]
            self.assertEqual(len(links), 1)
            self.assertFalse(links[0]["available"])

    def test_search_is_bound_bounded_and_read_only(self):
        self.lesson("Literal % _ ' search", "search")
        self.assertEqual(len(search_knowledge("%", kind="lesson")["items"]), 1)
        self.assertFalse(search_knowledge("' OR 1=1 --")["items"])

        def snapshot():
            with get_connection() as conn:
                return (
                    [
                        tuple(r)
                        for r in conn.execute(
                            "SELECT * FROM executive_memories ORDER BY id"
                        )
                    ],
                    [
                        tuple(r)
                        for r in conn.execute(
                            "SELECT * FROM memory_lifecycle ORDER BY memory_id"
                        )
                    ],
                )

        before = snapshot()
        with self.assertRaises(ValueError):
            search_knowledge(kind="executive_memories; DROP TABLE decisions")
        for kwargs in [
            {"limit": 51},
            {"offset": -1},
            {"query": "a" * 201},
            {"mode": "automatic"},
            {"query": "line\nfeed"},
        ]:
            with self.assertRaises(ValueError):
                search_knowledge(**kwargs)
        page = search_knowledge(limit=1)
        self.assertEqual(len(page["items"]), 1)
        self.assertTrue(page["has_more"])
        self.assertNotEqual(
            page["items"][0], search_knowledge(limit=1, offset=1)["items"][0]
        )
        with self.assertRaises(LookupError):
            knowledge_record("goal", 999999)
        with self.assertRaises(ValueError):
            knowledge_record("goal", True)
        self.assertEqual(snapshot(), before)

    def test_practice_and_skill_provenance_preserve_corrected_assessments(self):
        from tests import test_executive_skills as skills

        # Reuse builders on this same disposable fixture, never inherited tests.
        self.accepted_examples = lambda: skills.ExecutiveSkillsTests.accepted_examples(
            self
        )
        s = skills.ExecutiveSkillsTests.propose(self)
        from memory.executive_skills import decide_skill

        s = decide_skill(s["id"], 1, "accepted", "Owner reviewed synthetic examples")
        node = knowledge_record("skill", s["id"])
        self.assertEqual(node["node"]["status"], "accepted")
        reviews = [
            l["target"]["id"] for l in node["links"] if l["target"]["kind"] == "review"
        ]
        self.assertEqual(len(reviews), 2)
        review = knowledge_record("review", reviews[0])
        sample_id = next(
            l["target"]["id"]
            for l in review["links"]
            if l["target"]["kind"] == "sample"
        )
        self.assertTrue(any(l["target"]["kind"] == "skill" for l in review["links"]))
        from memory.business_discovery import get_brief, review_practice

        with get_connection() as conn:
            brief_id = conn.execute(
                "SELECT brief_id FROM business_practice_samples WHERE id=?",
                (sample_id,),
            ).fetchone()[0]
        b = get_brief(brief_id)
        review_practice(
            b["id"],
            b["version"],
            [False, True],
            "Corrected owner assessment",
            fixtures.NOW(),
            correction=True,
        )
        self.assertIn(
            "superseded assessment",
            knowledge_record("review", reviews[0])["node"]["warnings"],
        )
        self.assertIn(
            "Source assessments changed",
            knowledge_record("skill", s["id"])["node"]["warnings"][0],
        )
        self.assertIsNotNone(
            knowledge_record("review", reviews[0])["node"]["recorded_at"]
        )

    def test_api_auth_private_headers_and_validation(self):
        from main import app
        from fastapi.testclient import TestClient
        from config import config

        with patch.object(config, "API_SECRET_KEY", "synthetic-knowledge-key"):
            client = TestClient(app)
            headers = {"X-API-Key": "synthetic-knowledge-key"}
            self.assertEqual(client.get("/company/knowledge").status_code, 401)
            r = client.get("/company/knowledge", headers=headers)
            self.assertEqual(r.status_code, 200)
            self.assertIn("no-store", r.headers["cache-control"])
            self.assertEqual(
                client.get("/company/knowledge?limit=999", headers=headers).status_code,
                422,
            )
            self.assertEqual(
                client.get(
                    "/company/knowledge/not-supported/1", headers=headers
                ).status_code,
                422,
            )
            self.assertEqual(
                client.get(
                    "/company/knowledge/goal/999999", headers=headers
                ).status_code,
                404,
            )
            self.assertEqual(
                client.post(
                    "/company/knowledge", headers=headers, json={"approve": True}
                ).status_code,
                405,
            )

    def test_multiple_source_claims_and_links_are_paginated(self):
        goal, decision, action, lesson = self.chain()
        add_evidence_link(
            source_id=self.ids[0],
            entity_kind="decision",
            entity_id=decision,
            relation="supports",
            claim="Synthetic support claim",
        )
        add_evidence_link(
            source_id=self.ids[1],
            entity_kind="decision",
            entity_id=decision,
            relation="contradicts",
            claim="Synthetic opposing claim",
        )
        for i in range(32):
            self.lesson(
                f"Private history {i}", f"page-{i}", source_decision_id=decision
            )
        first = knowledge_record("decision", decision)
        self.assertEqual(len(first["links"]), 30)
        self.assertTrue(first["has_more_links"])
        second = knowledge_record("decision", decision, 30)
        claims = [
            l
            for l in first["links"] + second["links"]
            if l["origin"] == "evidence_links"
        ]
        self.assertGreaterEqual(len(claims), 5)
        self.assertTrue(any(l["relation"] == "contradicts" for l in claims))
        self.assertTrue(
            all(
                l["verification"] == "recorded link; claim not independently verified"
                for l in claims
            )
        )
        self.assertFalse(second["has_more_links"])
        reverse = knowledge_record("evidence", self.ids[1])
        self.assertTrue(
            any(
                l["relation"] == "contradicts"
                and l["claim"] == "Synthetic opposing claim"
                for l in reverse["links"]
            )
        )

    def test_long_detail_excerpts_report_omissions(self):
        goal = create_company_goal(
            "Large history", "a" * 13000, "Synthetic completion criteria"
        )
        detail = knowledge_record("goal", goal)
        self.assertEqual(len(detail["details"]["description"]), 12000)
        self.assertEqual(detail["truncated_fields"], ["description"])

    def test_mismatched_outcome_identity_is_withheld_both_directions(self):
        goal, decision, action, lesson = self.chain()
        with get_connection() as conn:
            conn.execute(
                "UPDATE action_outcomes SET action_sync_uuid=? WHERE action_id=?",
                ("wrong-action-identity", action),
            )
            conn.commit()
        for kind, target in [("action", "outcome"), ("outcome", "action")]:
            links = [
                l
                for l in knowledge_record(kind, action)["links"]
                if l["target"]["kind"] == target
            ]
            self.assertEqual(len(links), 1)
            self.assertFalse(links[0]["available"])
