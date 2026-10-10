"""Real SQLite and CrewAI pipeline tests with an in-process synthetic LLM."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import privacy_bootstrap
from crewai import Agent
from crewai.llms.base_llm import BaseLLM
from config import config
from memory.database import init_db, log_decision, get_connection
from workflows.step_checkpoints import run_json_step, StepNeedsReview, get_step
from workflows.instance_lock import database_instance_lock


class SyntheticLLM(BaseLLM):
    calls: int = 0

    def call(self, messages, **kwargs):
        self.calls += 1
        return "Final Answer: Evidence-Supported Findings: Synthetic test only. Assumptions: Unknown. Recommendation: Validate safely. Approval Gate: No live action requested."

    def supports_function_calling(self):
        return False


class WorkflowRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.saved = config.DATABASE_PATH
        config.DATABASE_PATH = str(Path(self.temp.name) / "test.db")
        init_db()

    def tearDown(self):
        config.DATABASE_PATH = self.saved
        self.temp.cleanup()

    def test_json_result_resume_and_input_binding(self):
        with patch("builtins.print") as callback:
            callback.return_value = {"result": "saved"}
            self.assertEqual(
                run_json_step("run", "step", "a" * 64, callback), {"result": "saved"}
            )
            self.assertEqual(
                run_json_step("run", "step", "a" * 64, callback), {"result": "saved"}
            )
            self.assertEqual(callback.call_count, 1)
        with self.assertRaises(StepNeedsReview):
            run_json_step("run", "step", "b" * 64, lambda: None)

    def test_interrupted_callback_does_not_replay(self):
        def crash():
            raise KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            run_json_step("run", "effect", "a" * 64, crash)
        self.assertEqual(get_step("run", "effect")["status"], "inconclusive")
        with self.assertRaises(StepNeedsReview):
            run_json_step(
                "run", "effect", "a" * 64, lambda: self.fail("replayed effect")
            )

    def test_decision_persistence_is_idempotent_and_binds_content(self):
        fields = dict(
            topic="Test",
            agents_involved=["CEO"],
            task_description="Test",
            decision_outcome="Synthetic only",
            workflow_key="test-key",
        )
        first = log_decision(**fields)
        self.assertEqual(log_decision(**fields), first)
        with self.assertRaises(ValueError):
            log_decision(**dict(fields, decision_outcome="Changed"))
        with get_connection() as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 1
            )

    def test_second_server_cannot_reconcile_live_database(self):
        with database_instance_lock(config.DATABASE_PATH):
            with self.assertRaises(RuntimeError):
                with database_instance_lock(config.DATABASE_PATH):
                    self.fail("second instance admitted")
        with database_instance_lock(config.DATABASE_PATH):
            pass

    def test_real_crewai_tasks_resume_saved_output_without_another_llm_call(self):
        from workflows.meeting import run_executive_meeting

        llm = SyntheticLLM(model="test-only")
        agents = {
            key: Agent(
                role=key.upper(),
                goal="Synthetic test",
                backstory="Synthetic test",
                llm=llm,
                allow_delegation=False,
                verbose=False,
                max_iter=2,
            )
            for key in ("cfo", "ceo")
        }
        fields = dict(
            topic="Synthetic",
            task_description="Synthetic test evidence only.",
            agent_keys=["cfo", "ceo"],
            agents_source=agents,
            memory_context={"enabled": False},
            workflow_run_id="real-crew-test",
        )
        first = run_executive_meeting(**fields)
        calls = llm.calls
        self.assertGreaterEqual(calls, 2)
        second = run_executive_meeting(**fields)
        self.assertEqual(llm.calls, calls)
        self.assertEqual(second["final_decision"], first["final_decision"])
        self.assertEqual(
            get_step("real-crew-test", "agent:0:cfo")["status"], "succeeded"
        )

    def test_api_owner_gates_real_preparation_tool_and_live_test_file(self):
        from fastapi.testclient import TestClient
        from workflows.meeting import run_executive_meeting
        from tools.file_operation_tool import ProposeFileOperationTool
        import main
        from memory.database import get_action_by_id

        class PreparationLLM(SyntheticLLM):
            def call(self, messages, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    return (
                        "Thought: Propose the requested synthetic test file for owner review.\n"
                        "Action: propose_file_operation\n"
                        'Action Input: {"operation":"write","file_path":"evidence.txt",'
                        '"content":"Synthetic test evidence","reason":"Synthetic audit test",'
                        '"expected_outcome":"Test file exists"}'
                    )
                return "Final Answer: A synthetic file proposal awaits separate owner approval. No file has been written."

        def synthetic_meeting(**kwargs):
            preparation = bool(kwargs.get("provenance_context"))
            llm = (
                PreparationLLM(model="test-preparation")
                if preparation
                else SyntheticLLM(model="test-decision")
            )
            agents = {
                key: Agent(
                    role=key.upper(),
                    goal="Synthetic audit test",
                    backstory="Synthetic only",
                    llm=llm,
                    tools=(
                        [ProposeFileOperationTool(role="COO")]
                        if preparation and key == "coo"
                        else []
                    ),
                    allow_delegation=False,
                    verbose=False,
                    max_iter=3,
                )
                for key in kwargs["agent_keys"]
            }
            kwargs["agents_source"] = agents
            kwargs["memory_context"] = {"enabled": False}
            return run_executive_meeting(**kwargs)

        saved = (
            config.API_SECRET_KEY,
            config.ACTION_APPROVAL_HMAC_KEY,
            config.SANDBOX_MODE,
            config.WORKSPACE_ROOT,
        )
        try:
            config.API_SECRET_KEY = "audit-test-only-api-key"
            config.ACTION_APPROVAL_HMAC_KEY = "audit-test-only-seal-key"
            config.SANDBOX_MODE = False
            config.WORKSPACE_ROOT = str(Path(self.temp.name) / "workspace")
            client = TestClient(
                main.app
            )  # No lifespan: scheduled/external jobs never start.
            client.headers["X-API-Key"] = config.API_SECRET_KEY
            with (
                patch("main.run_executive_meeting", side_effect=synthetic_meeting),
                patch("main.send_notification"),
                patch("workflows.action_executor.send_notification"),
                patch("tools.file_operation_tool.send_proposal_notification"),
            ):
                request = {
                    "topic": "Synthetic audit",
                    "task_description": "Prepare only a synthetic test file.",
                    "agent_keys": ["coo", "ceo"],
                    "workflow_run_id": "api-synthetic-audit",
                }
                decision = client.post("/decisions/trigger", json=request)
                self.assertEqual(decision.status_code, 200, decision.text)
                decision_id = decision.json()["database_id"]
                again = client.post("/decisions/trigger", json=request)
                self.assertEqual(again.status_code, 200, again.text)
                self.assertEqual(again.json()["database_id"], decision_id)
                blocked = client.post(
                    f"/decisions/{decision_id}/prepare", json={"agent_keys": ["coo"]}
                )
                self.assertEqual(blocked.status_code, 409)
                approved = client.post(f"/decisions/{decision_id}/approve")
                self.assertEqual(approved.status_code, 200, approved.text)
                prepared = client.post(
                    f"/decisions/{decision_id}/prepare", json={"agent_keys": ["coo"]}
                )
                self.assertEqual(prepared.status_code, 200, prepared.text)
                with get_connection() as conn:
                    action_id = conn.execute("SELECT id FROM action_queue").fetchone()[
                        0
                    ]
                self.assertEqual(get_action_by_id(action_id)["status"], "pending")
                target = Path(config.WORKSPACE_ROOT) / "evidence.txt"
                self.assertFalse(target.exists())
                denied = client.post(f"/actions/{action_id}/execute")
                self.assertNotEqual(denied.status_code, 200)
                action_approved = client.post(f"/actions/{action_id}/approve")
                self.assertEqual(action_approved.status_code, 200, action_approved.text)
                executed = client.post(f"/actions/{action_id}/execute")
                self.assertEqual(executed.status_code, 200, executed.text)
                self.assertEqual(target.read_text(), "Synthetic test evidence")
                retry = client.post(f"/actions/{action_id}/execute")
                self.assertNotEqual(retry.status_code, 200)
        finally:
            (
                config.API_SECRET_KEY,
                config.ACTION_APPROVAL_HMAC_KEY,
                config.SANDBOX_MODE,
                config.WORKSPACE_ROOT,
            ) = saved

    def test_real_meeting_cannot_fabricate_owner_acknowledgement_on_resume(self):
        from workflows.meeting import run_executive_meeting

        class FabricatedConsentLLM(SyntheticLLM):
            def call(self, messages, **kwargs):
                self.calls += 1
                return (
                    "Final Answer: **Owner Acknowledgement**\n"
                    "The owner agrees to prioritize the proposal.\n\n"
                    "**Evidence Still Required**\nSynthetic evidence is missing."
                )

        llm = FabricatedConsentLLM(model="test-only")
        agent = Agent(
            role="CEO",
            goal="Synthetic test",
            backstory="Synthetic test",
            llm=llm,
            allow_delegation=False,
            verbose=False,
            max_iter=1,
        )
        fields = dict(
            topic="Synthetic owner consent test",
            task_description="No owner consent supplied.",
            agent_keys=["ceo"],
            agents_source={"ceo": agent},
            memory_context={"enabled": False},
            meeting_type="retrospective",
            workflow_run_id="owner-consent-test",
        )
        first = run_executive_meeting(**fields)
        calls = llm.calls
        second = run_executive_meeting(**fields)
        self.assertEqual(llm.calls, calls)
        for result in (first, second):
            self.assertNotIn("The owner agrees", result["final_decision"])
            self.assertNotIn("The owner agrees", result["individual_outputs"]["ceo"])
            self.assertIn("Pending owner review", result["final_decision"])
            self.assertIn("Synthetic evidence is missing", result["final_decision"])
            self.assertTrue(
                result["quality_warnings"]["owner_acknowledgement_corrected"]
            )

    def test_no_evidence_retrospective_suppresses_fabricated_outcomes_on_resume(self):
        from workflows.meeting import run_executive_meeting

        class InventedOutcomesLLM(SyntheticLLM):
            def call(self, messages, **kwargs):
                self.calls += 1
                return (
                    "Final Answer: **What Worked**\nThe team improved revenue and deployed changes.\n"
                    "**What Failed**\nThe company lost customers."
                )

        llm = InventedOutcomesLLM(model="test-only")
        agent = Agent(
            role="CEO",
            goal="Synthetic test",
            backstory="Synthetic test",
            llm=llm,
            allow_delegation=False,
            verbose=False,
            max_iter=1,
        )
        fields = dict(
            topic="No evidence test",
            task_description="Synthetic test only. No real company data or actions. Explain missing evidence.",
            agent_keys=["ceo"],
            agents_source={"ceo": agent},
            memory_context={"enabled": False},
            meeting_type="retrospective",
            workflow_run_id="no-evidence-test",
        )
        first = run_executive_meeting(**fields)
        calls = llm.calls
        second = run_executive_meeting(**fields)
        self.assertEqual(llm.calls, calls)
        for result in (first, second):
            for output in [
                result["final_decision"],
                *result["individual_outputs"].values(),
            ]:
                self.assertNotIn("improved revenue", output)
                self.assertNotIn("lost customers", output)
                self.assertIn("Unknown — evidence required", output)
                self.assertIn("Pending owner review", output)
            self.assertTrue(
                result["quality_warnings"]["insufficient_retrospective_evidence"]
            )
        # A supplied observation is not treated as an absence declaration.
        observed = run_executive_meeting(
            **dict(
                fields,
                workflow_run_id="observed-evidence-test",
                task_description="Observed fixture outcome: the synthetic check completed successfully.",
            )
        )
        self.assertFalse(
            observed["quality_warnings"]["insufficient_retrospective_evidence"]
        )
