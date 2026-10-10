"""Regression checks for discussion quality."""

import unittest
from workflows.discussion_contracts import (
    CONTRACTS,
    TEST_FIELDS,
    assess_round,
    guard_missing_prerequisites,
)


class DiscussionQualityTests(unittest.TestCase):
    def complete(self, phase="synthesis"):
        return (
            "\n".join("**" + heading + "**" for heading in CONTRACTS[phase].split("; "))
            + "\n"
            + "\n".join(
                "**"
                + field
                + ":** Unknown; obtain original reproduction details before running."
                for field in TEST_FIELDS
            )
            + "\nA passing observation does not establish cause."
        )

    def test_markdown_labels_and_blocked_test_are_recognized(self):
        for phase in ("proposal", "revision", "synthesis"):
            result = assess_round(
                self.complete(phase),
                phase,
                "Four synthetic checks passed; reminder failed; cause unknown.",
            )
            self.assertEqual(result["warnings"], [])
            self.assertIn("no independent truth", result["scope"])

    def test_vague_test_and_invented_dependencies_require_review(self):
        result = assess_round(
            "Investigate account settings and external services. Success means the reminder appears.",
            "revision",
            "Four checks passed; one reminder failed; cause unknown.",
        )
        self.assertEqual(result["status"], "review_required")
        self.assertIn("Missing test detail: Steps", result["warnings"])
        self.assertIn(
            "Unestablished context introduced: external services", result["warnings"]
        )

    def test_negative_source_does_not_establish_dependency(self):
        body = self.complete() + "\nInvestigate external services."
        self.assertIn(
            "Unestablished context introduced: external services",
            assess_round(body, "synthesis", "No external services are established.")[
                "warnings"
            ],
        )
        self.assertNotIn(
            "Unestablished context introduced: external services",
            assess_round(
                body, "synthesis", "The supplied reproduction uses external services."
            )["warnings"],
        )

    def test_separate_negation_does_not_hide_causal_claim(self):
        result = assess_round(
            self.complete() + "\nA pass proves the root cause.",
            "synthesis",
            "Cause unknown.",
        )
        self.assertTrue(
            any("Causal claim" in warning for warning in result["warnings"])
        )


class DiscussionQualityStorageTests(unittest.TestCase):
    def test_legacy_migration_preserves_records_and_immutability(self):
        import sqlite3
        from memory.discussions import init_discussions, store_discussion

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE discussion_messages (id INTEGER PRIMARY KEY, decision_id INTEGER NOT NULL, round_number INTEGER NOT NULL, phase TEXT NOT NULL, executive_key TEXT NOT NULL, body TEXT NOT NULL, profile_json TEXT NOT NULL, captured_at TEXT NOT NULL, UNIQUE(decision_id, round_number, executive_key))"
        )
        cursor.execute(
            "INSERT INTO discussion_messages VALUES(1,1,1,'proposal','ceo','Original','{}','original-time')"
        )
        init_discussions(cursor)
        init_discussions(cursor)
        row = cursor.execute("SELECT * FROM discussion_messages").fetchone()
        self.assertEqual(row["body"], "Original")
        self.assertIsNone(row["quality_json"])
        with self.assertRaises(sqlite3.IntegrityError):
            cursor.execute("UPDATE discussion_messages SET body='Changed'")
        message = dict(
            round_number=1,
            phase="proposal",
            executive_key="ceo",
            body="Original",
            profile={},
        )
        store_discussion(cursor, 1, [message])
        message["quality_checks"] = assess_round("Original", "proposal", "")
        with self.assertRaises(RuntimeError):
            store_discussion(cursor, 1, [message])
        conn.close()


class MissingPrerequisiteGuardTests(unittest.TestCase):
    def test_reported_fallback_is_replaced_and_guard_is_idempotent(self):
        body = "**Supported findings:**\nThe original reproduction steps, reminder due time, build and observation channel are still unknown.\n**Unresolved questions:**\nUnknown.\n**Recommended next test and observable result:**\nSteps: Create a task with the original due time (if known) or a variable due time.\n**Owner approval pending:**\nPending owner review."
        guarded = guard_missing_prerequisites(body, "synthesis")
        self.assertNotIn("or a variable due time", guarded)
        self.assertIn("Setup: Blocked", guarded)
        self.assertIn("Steps: Do not create a task", guarded)
        self.assertIn("Pending owner review.", guarded)
        self.assertEqual(guard_missing_prerequisites(guarded, "synthesis"), guarded)

    def test_known_prerequisites_and_critique_remain_unchanged(self):
        body = "Build: test-v1. Reminder due time: 12:00. Steps: Create the task. Cause unknown."
        self.assertEqual(guard_missing_prerequisites(body, "synthesis"), body)
        critique = (
            "Reminder due time is unknown. Challenge the variable due time fallback."
        )
        self.assertEqual(guard_missing_prerequisites(critique, "critique"), critique)


class MissingReportDetailsTests(unittest.TestCase):
    def test_report_does_not_provide_or_specify_blocks_proposal(self):
        for detail in (
            "Original reproduction steps: The report does not provide information on how the test was set up.",
            "Reminder due time: The report does not specify when the reminder was supposed to appear.",
        ):
            body = (
                "**Evidence and gaps**\n"
                + detail
                + "\n**Proposed next test**\nSteps: Trigger the reminder.\n**Expected observation**\nThe reminder will appear.\n**Owner review requested**\nPending owner review."
            )
            guarded = guard_missing_prerequisites(body, "proposal")
            self.assertIn("Setup: Blocked", guarded)
            self.assertNotIn("Steps: Trigger the reminder.", guarded)
            self.assertNotIn("The reminder will appear.", guarded)


class CritiqueReferenceTests(unittest.TestCase):
    def test_invented_and_uncited_attributions_are_withheld(self):
        from workflows.discussion_contracts import guard_critique_references

        proposal = {
            "ceo": "Setup: Blocked until missing details are supplied. Steps: Do not run."
        }
        for body in (
            "The proposal assumes the details are known and permits guessing.",
            "Claim quote: ceo | Run the test with a variable due time.",
            "Claim quote: cfo | Setup: Blocked until missing details are supplied.",
        ):
            corrected = guard_critique_references(body, proposal)
            self.assertIn("already blocks the test", corrected)
            self.assertNotIn("permits guessing", corrected)
            self.assertIn("No verified challenge", corrected)

    def test_valid_quote_and_revision_comparison(self):
        from workflows.discussion_contracts import (
            guard_critique_references,
            guard_revision_changes,
        )

        original = "Setup: Blocked until missing details are supplied."
        critique = "Claim quote: ceo | Setup: Blocked until missing details are supplied.\nThe stop condition is already present."
        self.assertEqual(
            guard_critique_references(critique, {"ceo": original}), critique
        )
        revision = "**Changes made in response to critique:**\nI added a block.\n**Revised next test:**\nSetup: Blocked"
        corrected = guard_revision_changes(revision, original)
        self.assertNotIn("I added a block.", corrected)
        self.assertIn("not a new change", corrected)
        self.assertEqual(guard_revision_changes(corrected, original), corrected)
