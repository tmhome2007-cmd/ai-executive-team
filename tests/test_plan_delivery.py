"""Protect the separated private preparation and unsent-message boundaries."""

import json
import unittest

from tests.test_actionable_plan import QUESTION, plan
from workflows import plan_delivery as delivery


def preparation():
    value = plan()
    del value["draft_message"]
    return json.dumps(value)


def draft():
    return json.dumps(
        {
            "status": "not_sent",
            "opening": "Hi,",
            "live_case_request": "Do you have your own live case and want to test?",
            "safe_input_instructions": "Remove account IDs and personal details; never share credentials.",
            "feedback_questions": [
                "Was the diagnosis accurate?",
                "Were any details unsupported?",
                "Was the plan useful?",
            ],
            "closing": "No problem if this is not relevant.",
        }
    )


class PlanDeliveryTests(unittest.TestCase):
    def test_private_scope_rejects_outbound_labels_and_unrequested_draft(self):
        value = json.loads(preparation())
        value["steps"][1]["kind"] = "outreach"
        with self.assertRaises(ValueError):
            delivery.validate_preparation(json.dumps(value), QUESTION, "silent", 30)
        private = delivery.validate_preparation(preparation(), QUESTION, "silent", 30)
        with self.assertRaises(ValueError):
            delivery.assemble(private, draft(), QUESTION, "silent", 30)
        self.assertIsNone(
            delivery.assemble(private, None, QUESTION, "silent", 30).draft_message
        )

    def test_recent_reply_requires_actual_draft_and_reserves_owner_effort(self):
        private = delivery.validate_preparation(
            preparation(), QUESTION, "recent_reply", 30
        )
        with self.assertRaises(ValueError):
            delivery.assemble(private, None, QUESTION, "recent_reply", 30)
        result = delivery.assemble(private, draft(), QUESTION, "recent_reply", 30)
        self.assertEqual(result.steps[-1].kind, "outreach")
        self.assertEqual(sum(s.minutes for s in result.steps), 25)
        self.assertIn("Was the plan useful?", result.draft_message.text)
        with self.assertRaises(ValueError):
            delivery.validate_preparation(preparation(), QUESTION, "recent_reply", 24)

    def test_no_sent_status_blank_feedback_or_unbounded_message(self):
        private = delivery.validate_preparation(
            preparation(), QUESTION, "recent_reply", 30
        )
        for key, replacement in (
            ("status", "sent"),
            ("feedback_questions", [" ", "Useful?"]),
            ("opening", "x" * 600),
        ):
            value = json.loads(draft())
            value[key] = replacement
            with self.subTest(key=key), self.assertRaises(ValueError):
                delivery.assemble(
                    private, json.dumps(value), QUESTION, "recent_reply", 30
                )

    def test_missing_typed_status_and_time_cannot_be_inferred(self):
        for status in (None, "warm", "source says recent_reply"):
            with self.subTest(status=status), self.assertRaises(ValueError):
                delivery.outreach_required(status)
        for minutes in (None, True, 15, 61):
            with self.subTest(minutes=minutes), self.assertRaises(ValueError):
                delivery.preparation_payload(
                    "local", QUESTION, "CEO", "recent_reply", minutes
                )

    def test_final_guard_rejects_invented_authority_in_draft(self):
        private = delivery.validate_preparation(
            preparation(), QUESTION, "recent_reply", 30
        )
        value = json.loads(draft())
        value["opening"] = "All permissions are granted."
        with self.assertRaises(ValueError):
            delivery.assemble(private, json.dumps(value), QUESTION, "recent_reply", 30)
