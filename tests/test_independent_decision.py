"""First proposals stay independent; critique cannot invent role attribution."""

import json
import unittest
from unittest.mock import Mock

from tests.test_structured_decision import sample
from workflows import independent_decision as flow
from workflows import structured_decision as sd

SOURCES = {
    "owner-task": "The ledger records 12 forms. Distinct participants are unknown."
}
PROFILES = {"cso": "Canonical CSO", "cfo": "Canonical CFO", "ceo": "Canonical CEO"}


class IndependentDecisionTests(unittest.TestCase):
    def test_first_inputs_are_independent_and_reviews_share_attributed_snapshot(self):
        inputs = []
        recommendations = [
            "Review the supplied ledger privately.",
            "Inspect its duplicate entries privately.",
            "Check the participant records privately.",
        ]

        def transport(base, path, payload):
            context, _ = json.JSONDecoder().raw_decode(
                payload["prompt"].split("Input:\n", 1)[1]
            )
            inputs.append(context)
            if "first_proposals_not_evidence" not in context:
                raw = sample(recommendations[len(inputs) - 1])
            else:
                raw = {
                    "selected_role": "ceo",
                    "justification": "The participant records address the unresolved identity question.",
                    "objections": [
                        {
                            "target_role": "cfo",
                            "proposal_quote": recommendations[1],
                            "concern": "Duplicates do not establish distinct participants.",
                        }
                    ],
                    "no_alternative_reason": None,
                }
            return {"done": True, "response": json.dumps(raw)}

        result = flow.run_rounds(
            "Review the ledger", SOURCES, PROFILES, "local", "candidate", transport
        )
        self.assertTrue(result["valid"])
        self.assertEqual(len(inputs), 6)
        for context in inputs[:3]:
            self.assertEqual(context["prior_proposals_not_evidence"], {})
            self.assertEqual(context["personality"], PROFILES[context["role"]])
        snapshot = inputs[3]["first_proposals_not_evidence"]
        self.assertEqual(set(snapshot), set(PROFILES))
        self.assertEqual(inputs[4]["first_proposals_not_evidence"], snapshot)
        self.assertEqual(inputs[5]["first_proposals_not_evidence"], snapshot)
        self.assertIn("CSO objects to CFO proposal", result["brief"])
        self.assertIn("No implied vote", result["brief"])
        self.assertEqual(result["first"]["cfo"]["recommendation"], recommendations[1])

    def test_unknown_target_misattribution_and_unexplained_convergence_rejected(self):
        first = {
            key: sd.validate_contribution(json.dumps(sample()), SOURCES)
            for key in PROFILES
        }
        valid = {
            "selected_role": "ceo",
            "justification": "The available ledger is the relevant private input.",
            "objections": [],
            "no_alternative_reason": "Only one relevant private input is supplied.",
        }
        self.assertEqual(
            flow.validate_review(json.dumps(valid), first, SOURCES).selected_role, "ceo"
        )
        for change in (
            {"selected_role": "owner"},
            {"no_alternative_reason": None},
            {
                "objections": [
                    {
                        "target_role": "cto",
                        "proposal_quote": "Review the supplied ledger privately.",
                        "concern": "The participant count is unknown.",
                    }
                ]
            },
            {
                "objections": [
                    {
                        "target_role": "cfo",
                        "proposal_quote": "Publish the supplied ledger now.",
                        "concern": "Publishing is outside this task.",
                    }
                ]
            },
            {"justification": "Owner approved execution."},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                flow.validate_review(json.dumps({**valid, **change}), first, SOURCES)

    def test_failures_retained_without_retry_or_partial_review(self):
        transport = Mock(return_value={"done": True, "response": "not JSON"})
        result = flow.run_rounds(
            "Review", SOURCES, PROFILES, "local", "candidate", transport
        )
        self.assertFalse(result["valid"])
        self.assertIsNone(result["brief"])
        self.assertEqual(transport.call_count, 3)
        self.assertTrue(
            all(x["raw"] == "not JSON" and not x["valid"] for x in result["stages"])
        )
        self.assertEqual(result["reviews"], {})

    def test_baseline_keeps_sequential_visibility_for_comparison(self):
        inputs = []

        def transport(base, path, payload):
            context = json.loads(payload["prompt"].split("Input:\n", 1)[1])
            inputs.append(context)
            return {"done": True, "response": json.dumps(sample())}

        result = flow.run_rounds(
            "Review", SOURCES, PROFILES, "local", "baseline", transport
        )
        self.assertTrue(result["valid"])
        self.assertEqual(
            [len(x["prior_proposals_not_evidence"]) for x in inputs], [0, 1, 2]
        )
        self.assertEqual(result["reviews"], {})
