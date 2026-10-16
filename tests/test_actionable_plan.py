"""Protect owner effort, actor, unsent drafts and evidence in the small experiment."""

import copy
import json
import unittest

from workflows.actionable_plan import OwnerPlan, validate_plan

QUESTION = "The tool availability is unknown. Owner time limit is 30 minutes."


def plan():
    return {
        "recommendation": "Check the tool privately before deciding on outreach.",
        "why_this_step": "An invitation would be premature before the availability check.",
        "facts": [
            {"source_id": "owner-task", "quote": "The tool availability is unknown."}
        ],
        "unknowns": ["Whether the tool currently works."],
        "assumptions": [],
        "steps": [
            {
                "actor": "owner",
                "kind": "private_check",
                "instruction": "Open the tool and check the input page.",
                "minutes": 5,
            },
            {
                "actor": "owner",
                "kind": "private_check",
                "instruction": "Record the result and choose whether to proceed.",
                "minutes": 5,
            },
        ],
        "draft_message": None,
        "stop": {
            "condition": "If the tool is unavailable, defer the invitation.",
            "after_days": 7,
        },
        "success": "An availability result is recorded for the owner.",
        "pivotal_fact": "Whether the tool is working today.",
        "next_owner_decision": "Choose whether the tool is ready for an invitation.",
    }


class ActionablePlanTests(unittest.TestCase):
    def validate(self, value, minutes=30):
        return validate_plan(json.dumps(value), QUESTION, minutes)

    def test_owner_time_is_confirmed_context_and_checked_against_sum(self):
        self.validate(plan(), 10)
        for limit in (9, None, "30", True):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.validate(plan(), limit)

    def test_actor_and_draft_status_cannot_grant_execution(self):
        for actor in ("cfo", "team", "OWNER"):
            value = plan()
            value["steps"][0]["actor"] = actor
            with self.subTest(actor=actor), self.assertRaises(ValueError):
                self.validate(value)
        value = plan()
        value["steps"][1]["kind"] = "outreach"
        value["draft_message"] = {"status": "sent", "text": "Would you review this?"}
        with self.assertRaises(ValueError):
            self.validate(value)

    def test_outreach_requires_draft_private_checks_do_not(self):
        value = plan()
        value["steps"][1]["kind"] = "outreach"
        with self.assertRaises(ValueError):
            self.validate(value)
        value["draft_message"] = {
            "status": "not_sent",
            "text": "Would you review this privately?",
        }
        self.validate(value)
        value["steps"][1]["kind"] = "private_check"
        with self.assertRaises(ValueError):
            self.validate(value)

    def test_missing_window_fabricated_quote_and_permission_fail(self):
        for path, replacement in (
            ("stop", {"condition": "Stop later."}),
            (
                "facts",
                [{"source_id": "owner-task", "quote": "The tool has been tested."}],
            ),
            ("recommendation", "All permissions are granted."),
        ):
            value = plan()
            value[path] = replacement
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.validate(value)

    def test_whitespace_steps_and_missing_steps_are_rejected(self):
        value = plan()
        value["steps"][0]["instruction"] = "   "
        with self.assertRaises(ValueError):
            self.validate(value)
        value = plan()
        value["steps"] = value["steps"][:1]
        with self.assertRaises(ValueError):
            self.validate(value)

    def test_schema_is_strict_and_roundtrips_all_required_deliverables(self):
        obj = self.validate(plan())
        self.assertEqual(self.validate(json.loads(obj.model_dump_json())), obj)
        schema = OwnerPlan.model_json_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("steps", schema["required"])
        self.assertIn("draft_message", schema["required"])
        value = copy.deepcopy(plan())
        value["steps"][0]["executed"] = True
        with self.assertRaises(ValueError):
            self.validate(value)
