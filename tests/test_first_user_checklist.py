"""Check useful fallbacks without model calls, inferred facts or execution."""

import re
import unittest

from workflows.decision_intake import IntakeInput, build_intake


def preview(**changes):
    value = IntakeInput(request="Help me get the first real user", **changes)
    return build_intake(value, lambda _: None)


class FirstUserChecklistTests(unittest.TestCase):
    def test_one_pivotal_unknown_and_format_conditional_test_data(self):
        expected = {
            "unknown": "Does the tool work today with fictional input?",
            "working": "Do existing records show another permitted conversation with a potentially eligible tester?",
            "unavailable": "Will the next owner check confirm that the unavailable tool can be used again?",
        }
        for tool, question in expected.items():
            text = preview(lead_status="silent", tool_status=tool, owner_minutes=30)[
                "checklist"
            ]
            line = next(
                line
                for line in text.splitlines()
                if line.startswith("Most decision-changing unknown")
            )
            self.assertTrue(line.endswith(question))
            self.assertEqual(line.count("?"), 1)
            self.assertIn("If yes:", text)
            self.assertIn("If no:", text)
            self.assertEqual("FICTIONAL TEST ONLY:" in text, tool == "unknown")
        unknown = preview()["checklist"]
        self.assertIn("Only for a suspension-notice text tool", unknown)
        self.assertIn("For another input format", unknown)
        self.assertIn("do not submit this notice in an incompatible format", unknown)

    def test_unanswered_request_has_conditional_steps_without_assumed_time(self):
        result = preview()
        text = result["checklist"]
        self.assertEqual(len(result["questions"]), 3)
        self.assertIn("Time budget unknown", text)
        self.assertIn("confirm that time first", text)
        self.assertIn("1. Owner", text)
        self.assertIn("2. Owner", text)
        self.assertNotIn("Draft message", text)
        self.assertIn("7 days after starting this private review", text)
        self.assertIn("not an executive recommendation", text)

    def test_answer_changes_route_and_outage_overrides_a_recent_reply(self):
        recent = preview(lead_status="recent_reply", owner_minutes=30)
        silent = preview(lead_status="silent", owner_minutes=30)
        outage = preview(
            lead_status="recent_reply", tool_status="unavailable", owner_minutes=30
        )
        self.assertNotEqual(recent["checklist"], silent["checklist"])
        self.assertIn("Draft message — NOT SENT", recent["checklist"])
        self.assertIn("never paste credentials", recent["checklist"])
        self.assertEqual(recent["checklist"].count("\n- "), 3)
        self.assertIn("measured from your sending date", recent["checklist"])
        self.assertNotIn("Draft message", silent["checklist"])
        self.assertIn("Do not assume the silent contact", silent["checklist"])
        self.assertNotIn("Draft message", outage["checklist"])
        self.assertIn("confirmed outage", outage["checklist"])
        self.assertIn("later private check", outage["checklist"])

    def test_confirmed_working_and_all_supported_budgets_remain_bounded(self):
        for minutes in range(1, 61):
            with self.subTest(minutes=minutes):
                text = preview(
                    lead_status="recent_reply",
                    tool_status="working",
                    owner_minutes=minutes,
                )["checklist"]
                if minutes < 15:
                    self.assertIn(f"Owner step — {minutes} minutes", text)
                    self.assertNotIn("1. Owner", text)
                else:
                    self.assertIn("Record today's owner confirmation", text)
                    self.assertNotIn("Use a safe fictional example", text)
                    self.assertEqual("Draft message" in text, minutes >= 30)
                    estimates = re.findall(r"Owner — (\d+) minutes", text)
                    self.assertGreaterEqual(len(estimates), 2)
                    self.assertLessEqual(sum(map(int, estimates)), minutes)

    def test_full_correction_is_bound_to_review_and_missing_link_is_not_invented(self):
        correction = "The contact never tested the tool and never replied afterward."
        first = preview(
            correction=correction, lead_status="recent_reply", owner_minutes=30
        )
        self.assertIn(correction, first["checklist"])
        self.assertIn("[tool link: confirm first]", first["checklist"])
        self.assertIn("resolve any placeholder first", first["checklist"])
        changed = preview(
            correction="The contact is a different person.",
            lead_status="recent_reply",
            owner_minutes=30,
        )
        self.assertNotEqual(first["review_hash"], changed["review_hash"])
