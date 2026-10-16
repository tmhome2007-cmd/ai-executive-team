"""Wrong action/unknown links fail without regex-based semantic claims."""

import json
import unittest

from workflows import bound_review as flow

SOURCES = {"owner-correction": "The contact did not reply. Tool readiness is unknown."}
CATALOG = {
    "reply_status": flow.ReviewTarget(
        question="Did the contact reply?",
        owner_check="Owner: privately review the recorded reply status.",
    ),
    "tool_readiness": flow.ReviewTarget(
        question="Does the tool work today?",
        owner_check="Owner: check the tool privately using safe fictional input.",
    ),
}
UNRESOLVED = ["tool_readiness"]


def sample(**changes):
    return {
        "target_id": "tool_readiness",
        "reason": "Current tool readiness is unknown.",
        "fact": {
            "source_id": "owner-correction",
            "quote": "Tool readiness is unknown.",
        },
        "assumption": None,
        **changes,
    }


class BoundReviewTests(unittest.TestCase):
    def test_settled_target_excluded_from_native_schema_and_rendered_check(self):
        payload = flow.request_payload(
            "local", "Review privately", SOURCES, "cfo", "CFO", CATALOG, UNRESOLVED
        )
        self.assertEqual(
            payload["format"]["properties"]["target_id"]["enum"], UNRESOLVED
        )
        context = json.loads(payload["prompt"].split("Input:\n", 1)[1])
        self.assertEqual(list(context["unresolved_review_targets"]), UNRESOLVED)
        value = flow.validate(json.dumps(sample()), SOURCES, CATALOG, UNRESOLVED)
        rendered = flow.render(value, SOURCES, CATALOG, UNRESOLVED)
        self.assertEqual(rendered["owner_check"], CATALOG["tool_readiness"].owner_check)
        self.assertEqual(
            rendered["unresolved_question"], CATALOG["tool_readiness"].question
        )
        self.assertIn("application catalog", rendered["check_origin"])

    def test_model_cannot_select_known_target_or_smuggle_free_action_fields(self):
        for change in (
            {"target_id": "reply_status"},
            {"recommendation": "Check whether the contact replied."},
            {"owner_check": "Contact the person now."},
            {"reason": "Owner approved execution."},
            {
                "fact": {
                    "source_id": "owner-correction",
                    "quote": "The contact replied.",
                }
            },
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                flow.validate(
                    json.dumps(sample(**change)), SOURCES, CATALOG, UNRESOLVED
                )

    def test_reconciled_state_blocks_a_previously_valid_choice(self):
        value = flow.validate(json.dumps(sample()), SOURCES, CATALOG, UNRESOLVED)
        with self.assertRaises(ValueError):
            flow.render(value, SOURCES, CATALOG, ["reply_status"])

    def test_missing_empty_or_ambiguous_state_requires_a_blocker_not_a_fake_unknown(
        self,
    ):
        for ids in ([], ["absent"], ["tool_readiness"] * 2, "tool_readiness", [None]):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                flow.unresolved_targets(CATALOG, ids)

    def test_free_reason_still_needs_semantic_review_even_when_target_is_valid(self):
        # Deliberately demonstrates the boundary: ID binding is not entailment.
        value = flow.validate(
            json.dumps(sample(reason="Whether the contact replied is unknown.")),
            SOURCES,
            CATALOG,
            UNRESOLVED,
        )
        self.assertIn("contact replied", value.reason)
        self.assertEqual(value.target_id, "tool_readiness")
