"""Protect the separated private preparation and unsent-message boundaries."""

import json
import unittest

from tests.test_actionable_plan import QUESTION

from workflows import plan_delivery as delivery

SOURCES = {
    "record:1": QUESTION,
    "record:link": "Historical tool: https://example.com/test",
}


def preparation(lead="silent"):
    return json.dumps(
        {
            "why_this_step": "Private checks establish whether an invitation is appropriate.",
            "alternative_considered": "immediate_invitation",
            "facts": [
                {"source_id": "record:1", "quote": "The tool availability is unknown."}
            ],
            "unknowns": ["tool_availability"],
            "stop_after_days": 7,
            "pivotal_fact": {
                "key": "tool_availability",
            },
        }
    )


def draft():
    return json.dumps(
        {
            "status": "not_sent",
            "tool_link": {
                "source_id": "record:link",
                "quote": "https://example.com/test",
            },
        }
    )


class PlanDeliveryTests(unittest.TestCase):
    def test_native_fact_choices_bind_quotes_to_their_actual_source(self):
        sources = {
            "record:1": "Historical status is unknown.",
            "owner-correction": "The owner confirmed a recent reply.",
        }
        payload = delivery.preparation_payload(
            "local", QUESTION, "CEO", "recent_reply", 30, sources
        )
        choices = payload["format"]["properties"]["facts"]["items"]["anyOf"]
        pairs = {
            (item["properties"]["source_id"]["const"], quote)
            for item in choices
            for quote in item["properties"]["quote"]["enum"]
        }
        self.assertIn(("owner-correction", sources["owner-correction"]), pairs)
        self.assertNotIn(("record:1", sources["owner-correction"]), pairs)
        self.assertNotIn(("owner-correction", sources["record:1"]), pairs)
        self.assertTrue(all(quote in sources[source_id] for source_id, quote in pairs))

    def test_standard_draft_fits_maximum_link_and_preserves_complete_questions(self):
        link = "https://example.com/" + "a" * 60
        sources = {**SOURCES, "record:link": link}
        private = delivery.validate_preparation(
            preparation(), QUESTION, "recent_reply", 30, sources
        )
        value = {
            "status": "not_sent",
            "tool_link": {"source_id": "record:link", "quote": link},
        }
        result = delivery.assemble(
            private, json.dumps(value), QUESTION, "recent_reply", 30, sources
        )
        self.assertLessEqual(len(result.draft_message.text), 600)
        self.assertIn(link, result.draft_message.text)
        self.assertIn("never paste credentials", result.draft_message.text)
        self.assertIn(
            "Remove seller/account IDs, names, email, address",
            result.draft_message.text,
        )
        self.assertEqual(result.draft_message.text.count("estimate"), 1)
        self.assertEqual(result.draft_message.text.count("\n- "), 3)
        self.assertTrue(
            all(
                line.endswith("?")
                for line in result.draft_message.text.splitlines()
                if line.startswith("- ")
            )
        )
        value["tool_link"]["quote"] += "aa"
        with self.assertRaises(ValueError):
            delivery.assemble(
                private, json.dumps(value), QUESTION, "recent_reply", 30, sources
            )

    def test_no_invented_misattributed_or_executable_link(self):
        private = delivery.validate_preparation(
            preparation(), QUESTION, "recent_reply", 30, SOURCES
        )
        for source_id, quote in (
            ("record:1", "https://example.com/test"),
            ("record:link", "https://invented.com/"),
            ("record:injection", "javascript:alert(1)"),
        ):
            sources = {**SOURCES, "record:injection": "javascript:alert(1)"}
            value = {
                "status": "not_sent",
                "tool_link": {"source_id": source_id, "quote": quote},
            }
            with self.subTest(quote=quote), self.assertRaises(ValueError):
                delivery.assemble(
                    private, json.dumps(value), QUESTION, "recent_reply", 30, sources
                )
        result = delivery.assemble(
            private,
            json.dumps({"status": "not_sent", "tool_link": None}),
            QUESTION,
            "recent_reply",
            30,
            SOURCES,
        )
        self.assertIn("[tool link: confirm first]", result.draft_message.text)
        self.assertIn(
            "resolve any bracketed link placeholder", result.steps[-1].instruction
        )

    def test_private_scope_rejects_outbound_labels_and_unrequested_draft(self):
        value = json.loads(preparation())
        value["steps"] = [{"actor": "ceo", "kind": "outreach"}]
        with self.assertRaises(ValueError):
            delivery.validate_preparation(
                json.dumps(value), QUESTION, "silent", 30, SOURCES
            )
        private = delivery.validate_preparation(
            preparation(), QUESTION, "silent", 30, SOURCES
        )
        with self.assertRaises(ValueError):
            delivery.assemble(private, draft(), QUESTION, "silent", 30, SOURCES)
        self.assertIsNone(
            delivery.assemble(
                private, None, QUESTION, "silent", 30, SOURCES
            ).draft_message
        )

    def test_recent_reply_requires_actual_draft_and_reserves_owner_effort(self):
        private = delivery.validate_preparation(
            preparation("recent_reply"), QUESTION, "recent_reply", 30, SOURCES
        )
        with self.assertRaises(ValueError):
            delivery.assemble(private, None, QUESTION, "recent_reply", 30, SOURCES)
        result = delivery.assemble(
            private, draft(), QUESTION, "recent_reply", 30, SOURCES
        )
        self.assertEqual(result.steps[-1].kind, "outreach")
        self.assertEqual(sum(s.minutes for s in result.steps), 30)
        self.assertIn("Was the proposed plan useful?", result.draft_message.text)
        with self.assertRaises(ValueError):
            delivery.validate_preparation(
                preparation("recent_reply"), QUESTION, "recent_reply", 24, SOURCES
            )

    def test_no_sent_status_blank_feedback_or_unbounded_message(self):
        private = delivery.validate_preparation(
            preparation("recent_reply"), QUESTION, "recent_reply", 30, SOURCES
        )
        for key, replacement in (
            ("status", "sent"),
            (
                "feedback_questions",
                ["the proposed plan.", "Please also share your thoughts on"],
            ),
            ("tool_link", {"source_id": "record:link", "quote": "x" * 600}),
        ):
            value = json.loads(draft())
            value[key] = replacement
            with self.subTest(key=key), self.assertRaises(ValueError):
                delivery.assemble(
                    private, json.dumps(value), QUESTION, "recent_reply", 30, SOURCES
                )

    def test_missing_typed_status_and_time_cannot_be_inferred(self):
        for status in (None, "warm", "source says recent_reply"):
            with self.subTest(status=status), self.assertRaises(ValueError):
                delivery.outreach_required(status)
        for minutes in (None, True, 15, 61):
            with self.subTest(minutes=minutes), self.assertRaises(ValueError):
                delivery.preparation_payload(
                    "local", QUESTION, "CEO", "recent_reply", minutes, SOURCES
                )

    def test_final_guard_rejects_invented_authority_in_draft(self):
        private = delivery.validate_preparation(
            preparation("recent_reply"), QUESTION, "recent_reply", 30, SOURCES
        )
        value = json.loads(draft())
        value["status"] = "All permissions are granted."
        with self.assertRaises(ValueError):
            delivery.assemble(
                private, json.dumps(value), QUESTION, "recent_reply", 30, SOURCES
            )

    def test_policy_and_fictional_input_cannot_be_quoted_as_business_evidence(self):
        value = json.loads(preparation())
        policy = "Check the tool privately before inviting anyone."
        value["facts"] = [{"source_id": "owner-task", "quote": policy}]
        with self.assertRaises(ValueError):
            delivery.validate_preparation(
                json.dumps(value), QUESTION + policy, "silent", 30, SOURCES
            )
        value["facts"] = [{"source_id": "record:1", "quote": delivery.FICTIONAL_TEST}]
        with self.assertRaises(ValueError):
            delivery.validate_preparation(
                json.dumps(value),
                QUESTION + delivery.FICTIONAL_TEST,
                "silent",
                30,
                SOURCES,
            )

    def test_owner_correction_is_preserved_verbatim_by_the_application(self):
        sources = {
            **SOURCES,
            "owner-correction": "The contact never replied after offering to test.",
        }
        result = delivery.validate_preparation(
            preparation(), QUESTION, "silent", 30, sources
        )
        self.assertEqual(result.facts[0].source_id, "owner-correction")
        self.assertEqual(result.facts[0].quote, sources["owner-correction"])
        self.assertTrue(any(f.source_id == "record:1" for f in result.facts))

    def test_pivotal_fact_must_be_unresolved_and_have_different_consequences(self):
        value = json.loads(preparation("recent_reply"))
        value["pivotal_fact"]["key"] = "contact_status"
        with self.assertRaisesRegex(ValueError, "already supplied"):
            delivery.validate_preparation(
                json.dumps(value), QUESTION, "recent_reply", 30, SOURCES
            )
        value = json.loads(preparation())
        value["pivotal_fact"]["key"] = " "
        with self.assertRaises(ValueError):
            delivery.validate_preparation(
                json.dumps(value), QUESTION, "silent", 30, SOURCES
            )

    def test_operational_steps_and_success_are_workflow_rules_not_model_labels(self):
        private = delivery.validate_preparation(
            preparation(), QUESTION, "silent", 30, SOURCES
        )
        self.assertIn(delivery.FICTIONAL_TEST, private.steps[0].instruction)
        self.assertIn("Run its normal analysis", private.steps[0].instruction)
        self.assertIn("record that blocker", private.steps[1].instruction)
        self.assertIn("own current live case", private.success)
        self.assertIn("starting this private review", private.stop.condition)
        self.assertNotIn("without a reply", private.stop.condition)
        value = json.loads(preparation())
        value["recommendation"] = "Contact someone now"
        with self.assertRaises(ValueError):
            delivery.validate_preparation(
                json.dumps(value), QUESTION, "silent", 30, SOURCES
            )

    def test_partial_correction_and_clipped_reasoning_cannot_be_published(self):
        sources = {
            **SOURCES,
            "owner-correction": "The founder and CEO are different people. The founder replied last week.",
        }
        value = json.loads(preparation())
        value["facts"].append(
            {"source_id": "owner-correction", "quote": "The founder replied last week."}
        )
        result = delivery.validate_preparation(
            json.dumps(value), QUESTION, "silent", 30, sources
        )
        self.assertEqual(result.facts[0].quote, sources["owner-correction"])
        value = json.loads(preparation())
        value["why_this_step"] = "This fits because the latest reply"
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            delivery.validate_preparation(
                json.dumps(value), QUESTION, "silent", 30, SOURCES
            )

    def test_reasoning_helper_does_not_transmit_role_personality_as_evidence(self):
        payload = delivery.preparation_payload(
            "local", QUESTION, "PERSONA_MARKER_NOT_A_FACT", "silent", 30, SOURCES
        )
        self.assertNotIn("PERSONA_MARKER_NOT_A_FACT", payload["prompt"])
        self.assertIn("role-neutral", payload["prompt"])
