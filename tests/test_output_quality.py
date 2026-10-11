"""Regression checks for output quality."""

import unittest
from workflows.output_quality import assess_output, verify_source_quotes


class OutputQualityTests(unittest.TestCase):
    def test_arbitrary_labels_and_explicit_contract_are_checked(self):
        self.assertTrue(
            assess_output("The pickup window is unknown.", "Pickup window: Tuesday")
        )
        self.assertTrue(
            assess_output(
                "The tray count is not supplied.", known_fields={"tray count": 16}
            )
        )
        self.assertEqual(
            assess_output("The pickup window is unknown.", "Pickup window: unknown"), []
        )
        self.assertEqual(
            assess_output("The builder is unknown.", known_fields={"build": "v2"}), []
        )

    def test_quotes_fail_closed_on_fabricated_reference_or_quote(self):
        from workflows.output_quality import verify_evidence_quotes

        sources = {"r1": "The ledger reports sixteen sealed trays."}
        good = [{"source_id": "r1", "quote": "sixteen sealed trays"}]
        self.assertEqual(verify_evidence_quotes(good, sources), [])
        self.assertTrue(
            verify_evidence_quotes([{**good[0], "source_id": "r2"}], sources)
        )
        self.assertTrue(
            verify_evidence_quotes(
                [{**good[0], "quote": "twenty sealed trays"}], sources
            )
        )
        self.assertTrue(
            verify_evidence_quotes([{**good[0], "quote": "trays"}], sources)
        )

    def test_supplied_details_are_not_missing(self):
        evidence = "Build: fixture-v2\nReminder due time: 12:02 UTC\nObservation channel: fixture event log"
        warnings = assess_output(
            "The build and observation channel are unknown. The reminder due time is not supplied.",
            evidence,
        )
        self.assertEqual(len(warnings), 3)
        self.assertEqual(
            assess_output("The build is fixture-v2. Cause remains unknown.", evidence),
            [],
        )

    def test_causal_leap_and_consent_are_flagged(self):
        self.assertTrue(
            assess_output(
                "If both tasks pass, it suggests that the issue is not related to reminders."
            )
        )
        self.assertTrue(assess_output("The owner approved execution."))
        self.assertEqual(
            assess_output(
                "A passing observation alone does not establish cause. Pending owner review."
            ),
            [],
        )

    def test_source_quotes_require_actual_records_and_coverage(self):
        sources = {
            "https://example.test/a": "A reminder event was absent in the fixture.",
            "https://example.test/b": "The comparison was not controlled.",
        }
        good = "\n".join(
            "Source quote: " + url + " | " + text for url, text in sources.items()
        )
        self.assertEqual(verify_source_quotes(good, sources), [])
        self.assertTrue(verify_source_quotes(good.splitlines()[0], sources))
        self.assertTrue(
            verify_source_quotes(
                "Source quote: https://example.test/a | The reminders were healthy.",
                sources,
            )
        )

    def test_tool_read_capture_is_reset_and_bounded(self):
        from tools import research_tool

        research_tool._FETCHED_SOURCES["https://example.test/a"] = "Synthetic source"
        self.assertEqual(len(research_tool.get_fetched_sources()), 1)
        research_tool.reset_call_count()
        self.assertEqual(research_tool.get_fetched_sources(), {})


class GroundedResearchTests(unittest.TestCase):
    def test_three_calls_to_one_source_cannot_satisfy_coverage(self):
        import asyncio
        from unittest.mock import patch
        from workflows.daily_research import _run_research_crew_once, RESEARCH_SOURCES

        snapshot = {
            "summary": "Synthetic ungrounded summary.",
            "calls": 3,
            "sources": {RESEARCH_SOURCES[0]: "One actual source only."},
        }
        with patch("workflows.daily_research.run_json_step", return_value=snapshot):
            with self.assertRaisesRegex(ValueError, "distinct retrieved"):
                asyncio.run(_run_research_crew_once("synthetic-coverage", 1))

    def test_valid_summary_carries_actual_source_records(self):
        import asyncio
        from unittest.mock import patch
        from workflows.daily_research import _run_research_crew_once, RESEARCH_SOURCES

        sources = {
            url: "A synthetic source describes a documented test observation."
            for url in RESEARCH_SOURCES
        }
        summary = "\n".join(
            "Source quote: " + url + " | " + text for url, text in sources.items()
        )
        with patch(
            "workflows.daily_research.run_json_step",
            return_value={"summary": summary, "calls": 3, "sources": sources},
        ):
            grounded, count = asyncio.run(
                _run_research_crew_once("synthetic-grounded", 1)
            )
        self.assertEqual(count, 3)
        self.assertIn("RETRIEVED SOURCE RECORDS", grounded)
        self.assertIn("interpretation, not additional evidence", grounded)


class ResearchPublicationTests(unittest.TestCase):
    def test_actual_workflow_separates_sources_and_persists_decision(self):
        import asyncio, tempfile
        from pathlib import Path
        from unittest.mock import patch, AsyncMock
        from config import config
        from memory.database import init_db, get_connection
        from workflows.daily_research import run_daily_research

        saved = config.DATABASE_PATH
        with tempfile.TemporaryDirectory() as raw:
            config.DATABASE_PATH = str(Path(raw).resolve() / "research.db")
            try:
                init_db()
                summary = "RETRIEVED SOURCE RECORDS:\nSynthetic observed event.\nCSO SUMMARY (interpretation, not additional evidence):\nA possible interpretation."
                result = {
                    "participants": ["ceo"],
                    "final_decision": "Pending owner review.",
                    "individual_outputs": {},
                }
                with (
                    patch(
                        "workflows.daily_research._run_research_crew_once",
                        new=AsyncMock(return_value=(summary, 3)),
                    ),
                    patch(
                        "workflows.daily_research.run_executive_meeting",
                        return_value=result,
                    ) as meeting,
                    patch(
                        "workflows.daily_research.send_notification_async",
                        new=AsyncMock(),
                    ),
                ):
                    published = asyncio.run(run_daily_research("synthetic-publication"))
                self.assertTrue(published["success"], published)
                self.assertNotIn(
                    "A possible interpretation",
                    meeting.call_args.kwargs["evidence_text"],
                )
                with get_connection() as conn:
                    self.assertEqual(
                        conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 1
                    )
            finally:
                config.DATABASE_PATH = saved


class QualityNoticeTests(unittest.TestCase):
    def test_review_notice_cannot_satisfy_missing_heading_or_clear_status(self):
        from workflows.output_quality import review_notice
        from workflows.discussion_contracts import assess_round

        body = review_notice(
            "**Evidence and gaps**\nSynthetic evidence.",
            ["Missing round section: Expected observation"],
        )
        self.assertTrue(assess_output(body))
        self.assertIn(
            "Missing round section: Expected observation",
            assess_round(body, "proposal", "")["warnings"],
        )
