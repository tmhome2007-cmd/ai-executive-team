"""Protect the separated private preparation and unsent-message boundaries."""

import json
import unittest

from tests.test_actionable_plan import QUESTION, plan

from workflows import plan_delivery as delivery

SOURCES = {"record:1": QUESTION}


def preparation(lead="silent"):
    value = plan()
    del value["draft_message"]
    value["facts"][0]["source_id"] = "record:1"
    value["unknowns"] = ["tool_availability"]
    value.pop("assumptions")
    value["stop_after_days"] = value.pop("stop")["after_days"]
    value["pivotal_fact"] = {
        "key": "tool_availability",
        "if_yes": "Review existing records before an invitation.",
        "if_no": "Record unavailable-tool blocker and pause.",
    }
    for step, purpose in zip(
        value["steps"], ["tool_check", "alternative_record_check"]
    ):
        step["purpose"] = purpose
        step["done_when"] = "Record whether the prerequisite is established or missing."
    value["steps"][1]["purpose"] = (
        "eligibility_record_check"
        if lead == "recent_reply"
        else "alternative_record_check"
    )
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
        self.assertEqual(sum(s.minutes for s in result.steps), 25)
        self.assertIn("Was the plan useful?", result.draft_message.text)
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
            ("feedback_questions", [" ", "Useful?"]),
            ("opening", "x" * 600),
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
        value["opening"] = "All permissions are granted."
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

    def test_owner_correction_must_be_attributed_not_dropped(self):
        sources = {
            **SOURCES,
            "owner-correction": "The contact never replied after offering to test.",
        }
        with self.assertRaisesRegex(ValueError, "correction"):
            delivery.validate_preparation(
                preparation(), QUESTION, "silent", 30, sources
            )
        value = json.loads(preparation())
        value["facts"].append(
            {"source_id": "owner-correction", "quote": sources["owner-correction"]}
        )
        delivery.validate_preparation(
            json.dumps(value), QUESTION, "silent", 30, sources
        )

    def test_pivotal_fact_must_be_unresolved_and_have_different_consequences(self):
        value = json.loads(preparation("recent_reply"))
        value["pivotal_fact"]["key"] = "contact_status"
        with self.assertRaisesRegex(ValueError, "already supplied"):
            delivery.validate_preparation(
                json.dumps(value), QUESTION, "recent_reply", 30, SOURCES
            )
        value = json.loads(preparation())
        value["pivotal_fact"]["if_no"] = value["pivotal_fact"]["if_yes"]
        with self.assertRaisesRegex(ValueError, "does not change"):
            delivery.validate_preparation(
                json.dumps(value), QUESTION, "silent", 30, SOURCES
            )

    def test_duplicate_check_or_blank_observable_result_is_rejected(self):
        value = json.loads(preparation())
        value["steps"][1]["purpose"] = "tool_check"
        with self.assertRaisesRegex(ValueError, "distinct"):
            delivery.validate_preparation(
                json.dumps(value), QUESTION, "silent", 30, SOURCES
            )
        value = json.loads(preparation())
        value["steps"][1]["done_when"] = " "
        with self.assertRaisesRegex(ValueError, "Blank"):
            delivery.validate_preparation(
                json.dumps(value), QUESTION, "silent", 30, SOURCES
            )
