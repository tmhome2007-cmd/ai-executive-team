"""Disposable owner-controlled discovery; no inference/network or real execution."""

import json
import datetime
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from config import config
from memory.database import init_db, get_connection
from memory.evidence import create_source, review_source
from memory.business_discovery import (
    create_brief,
    get_brief,
    select_practice,
    claim_stage,
    finish_stage,
    review_practice,
    reconcile_discovery,
)
from workflows.business_discovery import run_stage, read_public_source


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        identity_patch = patch(
            "workflows.local_model_identity.resolve_model",
            return_value={
                "digest": "a" * 64,
                "configuration": {
                    "provider": "ollama",
                    "tag": "synthetic",
                    "temperature": 0.0,
                },
            },
        )
        identity_patch.start()
        self.addCleanup(identity_patch.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.database = patch.object(
            config, "DATABASE_PATH", str(Path(self.temp.name) / "test.db")
        )
        self.database.start()
        init_db()
        self.ids = [
            create_source(
                source_key=f"synthetic-{i}",
                title="Synthetic research",
                reference=f"synthetic record {i}",
                summary="Synthetic platform constraint; customer demand unknown.",
                observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )["id"]
            for i in range(3)
        ]
        self.brief = create_brief(
            "Synthetic research", "Agents do the work. Zero spending.", self.ids
        )

    def tearDown(self):
        self.database.stop()
        self.temp.cleanup()

    def research_json(self):
        from workflows.business_research_contract import SERVICES

        return json.dumps(
            {
                "options": [
                    {
                        "key": key,
                        "skills": ["Clear writing"],
                        "exercise": "Draft a private synthetic guide",
                        "checks": ["Names prerequisites", "Labels missing facts"],
                    }
                    for key in SERVICES
                ],
                "practice_choice": "documentation",
            }
        )

    def generate(self):
        with patch(
            "workflows.business_discovery._reason", return_value=self.research_json()
        ) as reason:
            result = run_stage(self.brief["id"], 1, "research")
            self.assertEqual(reason.call_count, 1)
            with self.assertRaises(RuntimeError):
                run_stage(self.brief["id"], 1, "research")
            self.assertEqual(reason.call_count, 1)
        return result

    def plan(self):
        brief = self.generate()
        return select_practice(
            brief["id"],
            brief["version"],
            "Documentation",
            "Draft a synthetic guide",
            ["Names two prerequisites", "Labels missing facts"],
            (
                datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(days=1)
            ).isoformat(),
        )

    def test_full_loop_never_approves_actions_or_credits_money(self):
        brief = self.plan()
        with patch(
            "workflows.business_discovery._reason",
            return_value="Synthetic practice guide: review the supplied evidence, label any unsupported statements unknown, and request owner assessment.",
        ):
            brief = run_stage(brief["id"], brief["version"], "practice")
        brief = review_practice(
            brief["id"],
            brief["version"],
            [True, False],
            "Checked sample: prerequisite omitted.",
            datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        self.assertEqual(brief["review"]["assessment"], "practice_failed")
        self.assertEqual(brief["budget_amount"], 0)
        self.assertEqual(brief["risk_limit"], 0)
        with get_connection() as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM action_queue").fetchone()[0], 0
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM treasury_entries").fetchone()[0], 0
            )
        with self.assertRaises(RuntimeError):
            review_practice(
                brief["id"],
                brief["version"],
                [True, True],
                "Replacement assessment",
                datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )

    def test_state_and_source_gates(self):
        with self.assertRaises(RuntimeError):
            select_practice(
                self.brief["id"], 1, "X", "Y", ["A", "B"], "2030-01-01T00:00:00Z"
            )
        review_source(self.ids[0], 1, "disputed")
        with patch("workflows.business_discovery._reason") as reason:
            with self.assertRaises(ValueError):
                run_stage(self.brief["id"], 1, "research")
            reason.assert_not_called()
        self.assertEqual(get_brief(self.brief["id"])["state"], "draft")
        with self.assertRaises(ValueError):
            create_brief("X", "Y", self.ids[:2])
        with self.assertRaises(ValueError):
            create_brief("X", "Y", [True, 2, 3])

    def test_crash_and_failure_do_not_replay(self):
        claim_stage(self.brief["id"], 1, "research")
        reconcile_discovery()
        with patch("workflows.business_discovery._reason") as reason:
            with self.assertRaises(RuntimeError):
                run_stage(
                    self.brief["id"], get_brief(self.brief["id"])["version"], "research"
                )
            reason.assert_not_called()
        self.assertEqual(get_brief(self.brief["id"])["state"], "needs_review")

    def test_review_requires_real_boolean_checks(self):
        brief = self.plan()
        with patch(
            "workflows.business_discovery._reason",
            return_value="Synthetic practice guide: review the supplied evidence, label unsupported statements unknown, and request owner assessment.",
        ):
            brief = run_stage(brief["id"], brief["version"], "practice")
        with self.assertRaises(ValueError):
            review_practice(
                brief["id"],
                brief["version"],
                [1, 1],
                "Test evidence",
                datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )
        with self.assertRaises(ValueError):
            review_practice(
                brief["id"],
                brief["version"],
                [True],
                "Test evidence",
                datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )
        with self.assertRaises(RuntimeError):
            review_practice(
                brief["id"],
                1,
                [True, True],
                "Test evidence",
                datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )

    def test_source_read_blocks_sensitive_urls_and_failed_reads(self):
        with patch(
            "tools.research_tool.PageReaderTool._run", return_value="Error: blocked"
        ) as reader:
            for url in [
                "https://user:pass@example.org",
                "https://example.org?q=private",
                "file:///tmp/data",
            ]:
                with self.assertRaises(ValueError):
                    read_public_source(url)
            reader.assert_not_called()
            with self.assertRaises(ValueError):
                read_public_source("https://example.org")
        with patch(
            "tools.research_tool.PageReaderTool._run",
            return_value="Synthetic public page contents.",
        ):
            source = read_public_source("https://example.org")
            self.assertEqual(source["verification"], "unverified")

    def test_remote_reasoning_is_rejected_and_failure_retained(self):
        from types import SimpleNamespace
        from workflows.business_discovery import _reason

        remote = SimpleNamespace(
            llm=SimpleNamespace(
                base_url="https://provider.example", model="ollama/test"
            )
        )
        with patch.dict(
            "agents.executive_agents.EXECUTIVE_AGENTS_NO_TOOLS", {"cso": remote}
        ):
            with self.assertRaisesRegex(ValueError, "local Ollama"):
                _reason("Synthetic prompt")
        with patch(
            "workflows.business_discovery._reason",
            side_effect=ValueError("Synthetic failure"),
        ):
            with self.assertRaises(ValueError):
                run_stage(self.brief["id"], 1, "research")
        self.assertEqual(get_brief(self.brief["id"])["state"], "needs_review")

    def test_normalized_ollama_provider_and_preflight(self):
        from types import SimpleNamespace
        from workflows.business_discovery import _local_agent

        local = SimpleNamespace(
            llm=SimpleNamespace(
                provider="ollama", model="llama3.1", base_url="http://localhost:11434"
            )
        )
        with patch.dict(
            "agents.executive_agents.EXECUTIVE_AGENTS_NO_TOOLS", {"cso": local}
        ):
            self.assertIs(_local_agent(), local)
        remote_provider = SimpleNamespace(
            llm=SimpleNamespace(
                provider="openai",
                model="ollama/test",
                base_url="http://localhost:11434",
            )
        )
        with (
            patch.dict(
                "agents.executive_agents.EXECUTIVE_AGENTS_NO_TOOLS",
                {"cso": remote_provider},
            ),
            patch("workflows.business_discovery._reason") as reason,
        ):
            with self.assertRaises(ValueError):
                run_stage(self.brief["id"], 1, "research")
            reason.assert_not_called()
        self.assertEqual(get_brief(self.brief["id"])["state"], "draft")
        self.assertEqual(get_brief(self.brief["id"])["version"], 1)

    def test_service_and_quote_contract_withholds_bad_comparisons(self):
        from workflows.business_research_contract import render_research
        from memory.evidence import get_source

        sources = [get_source(i) for i in self.ids]
        good = json.loads(self.research_json())
        rendered = render_research(json.dumps(good), sources)
        self.assertIn("No best business can be selected", rendered)
        for bad in ["Cloudflare Pages", "GitHub Pages", "Fiverr"]:
            broken = json.loads(self.research_json())
            broken["options"][0]["key"] = bad
            with self.assertRaises(ValueError):
                render_research(json.dumps(broken), sources)
        broken = json.loads(self.research_json())
        broken["source_quotes"] = [
            {
                "source_id": self.ids[0],
                "quote": "Invented commercial restrictions across all services",
            }
        ]
        with self.assertRaises(ValueError):
            render_research(json.dumps(broken), sources)
        broken = json.loads(self.research_json())
        broken["options"][0][
            "exercise"
        ] = "The services are not intended for commercial use"
        with self.assertRaises(ValueError):
            render_research(json.dumps(broken), sources)
        with patch(
            "workflows.business_discovery._reason",
            return_value="Cloudflare Pages is the business",
        ) as reason:
            with self.assertRaises(ValueError):
                run_stage(self.brief["id"], 1, "research")
            self.assertEqual(reason.call_count, 2)
        self.assertEqual(get_brief(self.brief["id"])["state"], "needs_review")

    def test_legacy_recommendation_cannot_advance_to_practice(self):
        brief = self.generate()
        with get_connection() as conn:
            conn.execute(
                "UPDATE business_discovery SET research_contract_version=0 WHERE id=?",
                (brief["id"],),
            )
            conn.commit()
        with self.assertRaisesRegex(RuntimeError, "validated research"):
            select_practice(
                brief["id"],
                brief["version"],
                "Documentation",
                "Private text sample",
                ["A", "B"],
                "2030-01-01T00:00:00Z",
            )
        self.assertEqual(get_brief(brief["id"])["state"], "research_ready")

    def reviewed_sample(self):
        brief = self.plan()
        claim_stage(brief["id"], brief["version"], "practice")
        brief = finish_stage(
            brief["id"],
            "practice",
            "Original synthetic sample with an unsupported pencil icon.",
        )
        return review_practice(
            brief["id"],
            brief["version"],
            [False, False],
            "Correct the invented pencil icon; use generic steps.",
            datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

    def revision_json(self):
        return json.dumps(
            {
                "revised_sample": "1. Create a task using the app’s create-task function. 2. Edit its supplied details. 3. Complete the task. Interface controls remain unknown; no new features are established.",
                "changes": ["Removed invented controls"],
                "remaining_unknowns": ["Specific interface controls are unspecified"],
            }
        )

    def test_feedback_revision_and_corrections_preserve_history(self):
        brief = self.reviewed_sample()
        original = brief["sample"]
        original_review = brief["attempts"][0]["reviews"][0]
        brief = review_practice(
            brief["id"],
            brief["version"],
            [True, False],
            "Correction: first check passed; invented interface detail still fails.",
            datetime.datetime.now(datetime.timezone.utc).isoformat(),
            correction=True,
        )
        self.assertEqual(len(brief["attempts"][0]["reviews"]), 2)
        self.assertEqual(
            brief["attempts"][0]["reviews"][1]["supersedes_review_id"],
            original_review["id"],
        )
        self.assertEqual(
            brief["attempts"][0]["reviews"][0]["review"]["results"], [False, False]
        )
        correction_id = brief["attempts"][0]["reviews"][1]["id"]
        with patch(
            "workflows.business_discovery._reason", return_value=self.revision_json()
        ) as reason:
            brief = run_stage(brief["id"], brief["version"], "revision")
            self.assertIn("Correction: first check passed", reason.call_args.args[0])
            self.assertIn(original, reason.call_args.args[0])
        self.assertEqual(brief["state"], "sample_ready")
        self.assertIsNone(brief["review"])
        self.assertEqual(len(brief["attempts"]), 2)
        self.assertEqual(brief["attempts"][0]["sample"], original)
        self.assertEqual(brief["attempts"][1]["feedback_review_id"], correction_id)
        brief = review_practice(
            brief["id"],
            brief["version"],
            [True, True],
            "Observed both checks in the revised sample.",
            datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        with get_connection() as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM action_queue").fetchone()[0], 0
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM treasury_entries").fetchone()[0], 0
            )
        self.assertEqual(brief["review"]["assessment"], "practice_passed")

    def test_legacy_history_import_is_idempotent(self):
        brief = self.plan()
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        review = json.dumps(
            {
                "results": [True, False],
                "evidence": "Legacy owner feedback",
                "assessment": "practice_failed",
                "observed_at": timestamp,
            }
        )
        with get_connection() as conn:
            conn.execute(
                "UPDATE business_discovery SET sample='Legacy exact sample',sample_created_at=?,review_json=?,state='reviewed' WHERE id=?",
                (timestamp, review, brief["id"]),
            )
            conn.commit()
        init_db()
        init_db()
        result = get_brief(brief["id"])
        self.assertEqual(len(result["attempts"]), 1)
        self.assertEqual(result["attempts"][0]["sample"], "Legacy exact sample")
        self.assertEqual(len(result["attempts"][0]["reviews"]), 1)
        self.assertEqual(
            result["attempts"][0]["reviews"][0]["review"]["evidence"],
            "Legacy owner feedback",
        )

    def test_history_rejects_rewriting_or_deleting(self):
        import sqlite3

        brief = self.reviewed_sample()
        with get_connection() as conn:
            for sql in [
                "UPDATE business_practice_samples SET sample='replacement'",
                "DELETE FROM business_practice_samples",
                "UPDATE business_practice_reviews SET review_json='{}'",
                "DELETE FROM business_practice_reviews",
            ]:
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(sql)
        self.assertEqual(get_brief(brief["id"])["sample"], brief["sample"])

    def test_revision_claim_recovery_and_correction_race(self):
        brief = self.reviewed_sample()
        claim_stage(brief["id"], brief["version"], "revision")
        with self.assertRaises(RuntimeError):
            claim_stage(brief["id"], brief["version"], "revision")
        with self.assertRaises(RuntimeError):
            review_practice(
                brief["id"],
                brief["version"] + 1,
                [True, False],
                "Attempted correction during generation",
                datetime.datetime.now(datetime.timezone.utc).isoformat(),
                correction=True,
            )
        reconcile_discovery()
        result = get_brief(brief["id"])
        self.assertEqual(result["state"], "needs_review")
        self.assertEqual(result["sample"], brief["sample"])
        self.assertEqual(len(result["attempts"]), 1)
        new_claim = claim_stage(result["id"], result["version"], "revision")
        finish_stage(
            result["id"],
            "revision",
            "Stale generation must not replace the sample.",
            claimed_version=brief["version"] + 1,
        )
        self.assertEqual(get_brief(result["id"])["version"], new_claim["version"])
        self.assertEqual(get_brief(result["id"])["sample"], brief["sample"])
        reconcile_discovery()
        result = get_brief(result["id"])
        with patch(
            "workflows.business_discovery._reason", return_value=self.revision_json()
        ):
            result = run_stage(result["id"], result["version"], "revision")
        self.assertEqual(result["state"], "sample_ready")
        self.assertEqual(len(result["attempts"]), 2)

    def test_revision_rejects_invented_controls_and_false_pass(self):
        from workflows.business_revision_contract import render_revision

        for bad in ["Tap the pencil icon.", "All checks passed.", "Set the due date."]:
            payload = json.loads(self.revision_json())
            payload["revised_sample"] = bad
            with self.assertRaises(ValueError):
                render_revision(
                    json.dumps(payload),
                    "Create, edit and complete tasks. Reminders unknown.",
                )
        brief = self.reviewed_sample()
        with patch(
            "workflows.business_discovery._reason", return_value="Malformed draft"
        ) as reason:
            with self.assertRaises(ValueError):
                run_stage(brief["id"], brief["version"], "revision")
            self.assertEqual(reason.call_count, 2)
        result = get_brief(brief["id"])
        self.assertEqual(result["state"], "needs_review")
        self.assertEqual(result["sample"], brief["sample"])
        self.assertEqual(result["review"], brief["review"])

    def test_api_forbids_budget_and_launch_fields(self):
        from foundation_api import BusinessBriefRequest, BusinessReview
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            BusinessBriefRequest(
                title="Synthetic",
                constraints="Synthetic",
                source_ids=self.ids,
                budget_amount=5,
            )
        with self.assertRaises(ValidationError):
            BusinessReview(
                expected_version=1,
                results=["true", True],
                evidence="Synthetic",
                observed_at="2026-01-01T00:00:00Z",
            )

    def test_revision_requires_complete_task_guide_and_faq_answers(self):
        from workflows.business_revision_contract import render_revision

        exercise = "Draft a task guide explaining create, edit and complete tasks with three FAQ answers."
        payload = json.loads(self.revision_json())
        with self.assertRaises(ValueError):
            render_revision(json.dumps(payload), exercise)

        payload["revised_sample"] = (
            "1. Create a task using the provided task function.\n"
            "2. Edit the task using the provided editing function.\n"
            "3. Complete the task using its completion function.\n"
            "Q: Which controls should I use?\nA: Interface controls are unspecified.\n"
            "Q: Are reminders available?\nA: Reminder behavior is unknown.\n"
            "Q: Has this guide been tested?\nA: No execution evidence was provided."
        )
        self.assertIn(
            "awaiting owner assessment", render_revision(json.dumps(payload), exercise)
        )
        self.assertIn(
            "awaiting owner assessment",
            render_revision("```json\n" + json.dumps(payload) + "\n```", exercise),
        )
        payload["revised_sample"] += "\n- Removed pencil icons from the previous draft."
        self.assertIn(
            "awaiting owner assessment", render_revision(json.dumps(payload), exercise)
        )
        escaped = dict(
            payload, revised_sample=payload["revised_sample"].replace("\n", "\\n")
        )
        self.assertIn(
            "awaiting owner assessment", render_revision(json.dumps(escaped), exercise)
        )
        payload["revised_sample"] += "\nClick the pencil icon to edit the task."
        with self.assertRaises(ValueError):
            render_revision(json.dumps(payload), exercise)

    def test_revision_does_not_add_sdk_conversion_retries(self):
        from unittest.mock import Mock
        from workflows.business_discovery import _reason

        agent = Mock(role="Synthetic executive", backstory="Synthetic personality")
        agent.llm.model = "llama3.1"
        agent.llm.base_url = "http://localhost:11434"
        agent.llm.call.return_value = self.revision_json()
        with (
            patch("workflows.business_discovery._local_agent", return_value=agent),
            patch("crewai.LLM", return_value=agent.llm) as constructor,
        ):
            self.assertEqual(
                _reason("Synthetic prompt", structured="revision"), self.revision_json()
            )
            response_format = constructor.call_args.kwargs["response_format"]
            from workflows.business_revision_contract import PracticeRevision

            self.assertIs(response_format, PracticeRevision)
            self.assertEqual(constructor.call_args.kwargs["timeout"], 120)
        self.assertNotIn("response_model", agent.llm.call.call_args.kwargs)

    def test_task_name_is_not_a_secret_but_key_prefix_is_rejected(self):
        from memory.database import _reject_secret_like_text

        _reject_secret_like_text(
            "Task-name fields and desk-based work are unspecified."
        )
        for value in [
            "sk-dummy-test-secret",
            "Key: sk-dummy-test-secret",
            '"sk-dummy-test-secret"',
        ]:
            with self.assertRaises(ValueError):
                _reject_secret_like_text(value)

    def test_instruction_check_is_excluded_without_rewriting_history(self):
        brief = self.reviewed_sample()
        with get_connection() as conn:
            conn.execute(
                "UPDATE business_discovery SET checks_json=?, review_json=? WHERE id=?",
                (
                    json.dumps(
                        ["one per line:", "Actual criterion A", "Actual criterion B"]
                    ),
                    json.dumps(dict(brief["review"], results=[False, True, True])),
                    brief["id"],
                ),
            )
            conn.commit()
        current = get_brief(brief["id"])
        self.assertEqual(current["review_assessment"], "practice_passed")
        self.assertEqual(current["ignored_check_indices"], [0])
        self.assertEqual(current["review"]["assessment"], "practice_failed")
        self.assertEqual(current["attempts"], brief["attempts"])
        candidate = create_brief("Another test", "Zero spending", self.ids)
        with patch(
            "workflows.business_discovery._reason", return_value=self.research_json()
        ):
            candidate = run_stage(candidate["id"], candidate["version"], "research")
        with self.assertRaises(ValueError):
            select_practice(
                candidate["id"],
                candidate["version"],
                "Documentation",
                "Synthetic guide",
                ["one per line:", "A", "B"],
                "2030-01-01T00:00:00Z",
            )

    def test_initial_sample_rejects_invented_features_and_repeated_scaffolding(self):
        from workflows.business_revision_contract import validate_sample

        exercise = "Write a task guide: create, edit and complete tasks. Reminder functionality is unknown. Include three FAQ answers."
        sample = "Findings\n- The exercise is a guide.\nNext Action\n- Write the guide.\n**Guide**\n1. Create a task using its create function.\n2. Edit a task using its edit function.\n3. Complete a task using its complete function.\nQ: Create?\nA: Use create.\nQ: Edit?\nA: Use edit.\nQ: Complete?\nA: Use complete.\n**Changes**\n- Removed controls."
        clean = validate_sample(sample, exercise)
        self.assertNotIn("Write the guide", clean)
        self.assertNotIn("Changes", clean)
        self.assertIn(
            "Do not set",
            validate_sample(
                clean + "\nDo not set a reminder; its behavior is unknown.", exercise
            ),
        )
        report = validate_sample(
            "**Findings**\nThe supplied fictional record establishes one observed result.\n**Unknowns**\n- Cause unknown.",
            "Write a findings report with unknowns.",
            preserve_unknowns=True,
        )
        self.assertIn("one observed result", report)
        for bad in [
            'Click the "+" button.',
            'Click "Save".',
            "Open the Tasks tab.",
            "Set a reminder (reminders unknown).",
        ]:
            with self.assertRaises(ValueError):
                validate_sample(clean + "\n" + bad, exercise)

    def test_initial_generation_withholds_bad_sample_and_repairs_once(self):
        brief = self.plan()
        bad = 'Private guide: click the "+" button to start. Unspecified functions and unknown details still need owner review.'
        good = "Private guide: inspect supplied evidence, distinguish facts from assumptions, and request owner assessment. Missing details remain unknown."
        with patch(
            "workflows.business_discovery._reason", side_effect=[bad, good]
        ) as reason:
            result = run_stage(brief["id"], brief["version"], "practice")
        self.assertEqual(reason.call_count, 2)
        self.assertEqual(result["state"], "sample_ready")
        self.assertNotIn('"+"', result["sample"])
        self.assertEqual(len(result["attempts"]), 1)

    def test_evidence_prompt_excludes_reply_policy_and_requires_explicit_unknowns(self):
        from memory.practice_quality import TEMPLATES

        template = TEMPLATES[1]
        brief = self.generate()
        brief = select_practice(
            brief["id"],
            brief["version"],
            template["service_key"],
            template["exercise"],
            template["checks"],
            (
                datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(days=1)
            ).isoformat(),
            **{
                key: template[key]
                for key in (
                    "service_key",
                    "audience",
                    "supplied_facts",
                    "deliverable_kind",
                )
            },
        )
        sample = (
            "Findings: Five checks expected; four passed; the reminder did not appear.\n"
            "Unknowns: The cause is unknown; the due time and original reproduction steps are unknown.\n"
            "Next Action: Request the missing reproduction steps and due time before another test."
        )
        with patch(
            "workflows.business_discovery._reason", return_value=sample
        ) as reason:
            result = run_stage(brief["id"], brief["version"], "practice")
        prompt = reason.call_args.args[0]
        self.assertNotIn("14-day duration", prompt)
        self.assertIn("FINAL EVIDENCE SUMMARY CONTRACT", prompt)
        self.assertEqual(result["state"], "sample_ready")

    def test_initial_generation_failure_preserves_no_invalid_sample(self):
        brief = self.plan()
        with patch(
            "workflows.business_discovery._reason",
            return_value='Click the "+" button. This is a synthetic guide with unknown details and pending owner review.',
        ) as reason:
            with self.assertRaises(ValueError):
                run_stage(brief["id"], brief["version"], "practice")
        result = get_brief(brief["id"])
        self.assertEqual(reason.call_count, 2)
        self.assertEqual(result["state"], "needs_review")
        self.assertIsNone(result["sample"])
        self.assertEqual(result["attempts"], [])

    def test_research_and_practice_completion_require_claimed_version(self):
        for stage in ("research", "practice"):
            brief = self.brief if stage == "research" else self.plan()
            claimed = claim_stage(brief["id"], brief["version"], stage)
            with get_connection() as conn:
                conn.execute(
                    "UPDATE business_discovery SET version=version+1 WHERE id=?",
                    (brief["id"],),
                )
                conn.commit()
            before = get_brief(brief["id"])
            for output in ("Stale worker output", None):
                after = finish_stage(
                    brief["id"], stage, output, claimed_version=claimed["version"]
                )
                self.assertEqual(after, before)
            self.assertEqual(before["attempts"], [])
            completed = finish_stage(
                brief["id"],
                stage,
                "Current worker output",
                claimed_version=before["version"],
            )
            self.assertEqual(
                completed["state"],
                "research_ready" if stage == "research" else "sample_ready",
            )
            if stage == "practice":
                self.assertEqual(len(completed["attempts"]), 1)
            else:
                # Start another independent brief for the practice case.
                self.brief = create_brief("Next recovery test", "Zero budget", self.ids)
