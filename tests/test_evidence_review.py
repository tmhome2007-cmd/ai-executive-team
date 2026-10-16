"""Evidence gaps are honest outputs; exact quotes are not semantic certification."""

import json
import unittest

from workflows import evidence_review as flow
from tests.test_bound_review import CATALOG, SOURCES, UNRESOLVED


def sample(**changes):
    return {
        "target_id": "tool_readiness",
        "premise": {
            "statement": "Tool readiness is unknown.",
            "citations": [
                {"source_id": "owner-correction", "quote": "Tool readiness is unknown."}
            ],
        },
        "evidence_gap": None,
        "rationale": "A private check resolves tool readiness before any invitation.",
        **changes,
    }


class EvidenceReviewTests(unittest.TestCase):
    def test_gap_without_decorative_quote_is_valid_and_render_keeps_inference_separate(
        self,
    ):
        value = flow.validate(
            json.dumps(
                sample(
                    premise=None,
                    evidence_gap="No current readiness result is supplied.",
                )
            ),
            SOURCES,
            CATALOG,
            UNRESOLVED,
        )
        result = flow.render(value, SOURCES, CATALOG, UNRESOLVED)
        self.assertIsNone(result["premise"])
        self.assertEqual(result["owner_check"], CATALOG["tool_readiness"].owner_check)
        self.assertEqual(result["semantic_assessment"], "not automatically verified")

    def test_fabricated_quote_known_target_or_empty_gap_is_rejected(self):
        for change in (
            {"target_id": "reply_status"},
            {"premise": None},
            {"premise": None, "evidence_gap": " "},
            {
                "premise": {
                    "statement": "The tool works.",
                    "citations": [
                        {"source_id": "owner-correction", "quote": "The tool works."}
                    ],
                }
            },
            {"rationale": "Owner approved execution."},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                flow.validate(
                    json.dumps(sample(**change)), SOURCES, CATALOG, UNRESOLVED
                )

    def test_native_schema_binds_source_pairs_and_allows_null_premise(self):
        payload = flow.request_payload(
            "local", "Review", SOURCES, "cfo", "CFO", CATALOG, UNRESOLVED
        )
        self.assertEqual(
            payload["format"]["properties"]["target_id"]["enum"], UNRESOLVED
        )
        choices = payload["format"]["$defs"]["Premise"]["properties"]["citations"][
            "items"
        ]["anyOf"]
        self.assertEqual(
            choices[0]["properties"]["source_id"]["const"], "owner-correction"
        )
        self.assertIn(
            {"type": "null"}, payload["format"]["properties"]["premise"]["anyOf"]
        )

    def test_wrong_meaning_with_real_quote_demonstrates_required_semantic_review(self):
        bad = sample()
        bad["premise"]["statement"] = "Tool readiness has been confirmed."
        value = flow.validate(json.dumps(bad), SOURCES, CATALOG, UNRESOLVED)
        self.assertIn("confirmed", value.premise.statement)
