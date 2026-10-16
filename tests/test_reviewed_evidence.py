"""Explicit supersession must not erase unrelated evidence or guess identity."""

import json
import unittest

from workflows.reviewed_evidence import EvidenceUpdate, project_current_evidence
from workflows import independent_decision

SOURCES = {
    "history": "An offer was recorded. Reply status is unknown. Tool state is unknown.",
    "correction": "The intended contact replied yesterday. Eligibility remains unknown.",
}


def update(**changes):
    return EvidenceUpdate(
        **{
            "field": "intended-contact.reply-status",
            "old_source": "history",
            "old_quote": "Reply status is unknown.",
            "current_source": "correction",
            "current_quote": "The intended contact replied yesterday.",
            **changes,
        }
    )


class ReviewedEvidenceTests(unittest.TestCase):
    def test_only_reviewed_span_is_retired_original_bytes_and_unknowns_survive(self):
        original = dict(SOURCES)
        active, facts = project_current_evidence(SOURCES, [update()])
        self.assertEqual(SOURCES, original)
        self.assertEqual(active["correction"], SOURCES["correction"])
        self.assertNotIn("history", active)
        self.assertEqual(active["history:part1"], "An offer was recorded. ")
        self.assertEqual(active["history:part2"], " Tool state is unknown.")
        self.assertEqual(
            facts[0]["quote"], SOURCES["correction"].split(" Eligibility")[0]
        )

    def test_skipped_or_unknown_identity_does_not_automatically_replace_history(self):
        active, facts = project_current_evidence(SOURCES, [])
        self.assertEqual(active, SOURCES)
        self.assertEqual(facts, [])
        self.assertIsNot(active, SOURCES)

    def test_missing_ambiguous_misattributed_or_duplicate_updates_fail(self):
        for sources, updates in (
            (SOURCES, [update(old_source="absent")]),
            (SOURCES, [update(current_quote="The contact never replied.")]),
            (SOURCES, [update(old_quote="The contact never replied.")]),
            (SOURCES, [update(), update()]),
            ({**SOURCES, "history": SOURCES["history"] * 2}, [update()]),
            (SOURCES, [update(current_source="history")]),
            (SOURCES, [update().model_dump()]),
        ):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                project_current_evidence(sources, updates)

    def test_overlaps_chains_and_cycles_fail_before_mutation(self):
        overlapping = update(
            field="other", old_quote="Reply status is unknown. Tool state is unknown."
        )
        chain = update(
            field="other",
            old_source="correction",
            old_quote="The intended contact replied yesterday.",
            current_source="third",
            current_quote="The newer statement is available.",
        )
        for updates in ([update(), overlapping], [update(), chain]):
            sources = {**SOURCES, "third": "The newer statement is available."}
            original = dict(sources)
            with self.assertRaises(ValueError):
                project_current_evidence(sources, updates)
            self.assertEqual(sources, original)

    def test_separate_subjects_and_untouched_source_content_are_preserved(self):
        sources = {**SOURCES, "other-contact": "Another contact did not reply."}
        active, _ = project_current_evidence(sources, [update()])
        self.assertEqual(active["other-contact"], sources["other-contact"])
        active, _ = project_current_evidence(
            {
                "history": "Reply status is unknown.",
                **{k: v for k, v in SOURCES.items() if k != "history"},
            },
            [update()],
        )
        self.assertNotIn("history", active)

    def test_projected_ids_cannot_overwrite_original_sources(self):
        with self.assertRaises(ValueError):
            project_current_evidence(
                {**SOURCES, "history:part1": "Another supplied source."}, [update()]
            )

    def test_native_quote_choices_and_runtime_guard_exclude_retired_claim(self):
        active, _ = project_current_evidence(SOURCES, [update()])
        unknowns = ["Does the contact have eligible input?"]
        payload = independent_decision.proposal_payload(
            "local", "Review privately", active, "cfo", "CFO", unknowns
        )
        choices = payload["format"]["properties"]["fact"]["anyOf"]
        self.assertNotIn("Reply status is unknown.", json.dumps(choices))
        value = {
            "recommendation": "Review eligibility privately.",
            "reason": "Eligibility remains unknown.",
            "fact": {"source_id": "correction", "quote": update().current_quote},
            "unknown": unknowns[0],
            "assumption": None,
        }
        self.assertIsNotNone(
            independent_decision.validate_proposal(json.dumps(value), active, unknowns)
        )
        value["fact"] = {"source_id": "history", "quote": update().old_quote}
        with self.assertRaises(ValueError):
            independent_decision.validate_proposal(json.dumps(value), active, unknowns)
