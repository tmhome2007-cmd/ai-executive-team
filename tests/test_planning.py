"""Regression checks for planning."""

import asyncio
import concurrent.futures
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from config import config
from memory.database import (
    init_db,
    create_company_goal,
    transition_company_goal_status,
    log_decision,
    get_connection,
    add_treasury_entry,
)
from memory.agile import create_board, list_tasks, update_task
from memory.planning import (
    create_plan,
    review_plan,
    claim_work,
    finish_work,
    review_work,
    get_plan,
    reconcile_work,
)
from workflows.executive_planning import dispatch_planned_work


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.saved = config.DATABASE_PATH
        config.DATABASE_PATH = str(Path(self.temp.name).resolve() / "planning.db")
        init_db()
        self.goal = create_company_goal(
            "Synthetic goal", "Synthetic mission", "Evidence", status="active"
        )
        self.board = create_board("Synthetic company work", "company")
        self.tasks = [
            dict(
                key="research",
                title="Research evidence",
                acceptance_criteria="State sources and gaps",
                assignee="cso",
                depends_on=[],
                expected_cost=0,
                currency="EUR",
            ),
            dict(
                key="review",
                title="Review research",
                acceptance_criteria="Compare sources",
                assignee="cfo",
                depends_on=["research"],
                expected_cost=0,
                currency="EUR",
            ),
        ]

    def tearDown(self):
        config.DATABASE_PATH = self.saved
        self.temp.cleanup()

    def plan(self, **fields):
        return create_plan(
            **{
                **dict(
                    run_key="synthetic-plan",
                    goal_id=self.goal,
                    board_id=self.board,
                    title="Synthetic plan",
                    proposer="coo",
                    tasks=self.tasks,
                ),
                **fields,
            }
        )

    def approved(self):
        plan = self.plan()
        return review_plan(plan["id"], 1, True, "Owner reviews synthetic plan")

    def test_review_atomic_dependencies_and_one_claim(self):
        plan = self.plan()
        self.assertEqual(list_tasks(self.board), [])
        self.assertEqual(self.plan()["id"], plan["id"])
        plan = review_plan(plan["id"], 1, True, "Reviewed")
        with self.assertRaises(RuntimeError):
            review_plan(plan["id"], 1, True, "Duplicate review")
        a, b = plan["work"]
        self.assertIsNone(claim_work(b["id"]))
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: claim_work(a["id"]), range(2)))
        self.assertEqual(sum(r is not None for r in results), 1)
        decision = log_decision(
            "Research",
            ["cso"],
            "Synthetic context",
            "Pending recommendation",
            goal_id=self.goal,
        )
        finish_work(a["id"], decision_id=decision)
        self.assertIsNone(claim_work(b["id"]))
        review_work(a["id"], True, "Reviewed research result")
        self.assertIsNotNone(claim_work(b["id"]))
        with get_connection() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT status FROM decision_approvals WHERE decision_id = ?",
                    (decision,),
                ).fetchone()[0],
                "pending",
            )

    def test_cycle_budget_goal_and_crash_gate(self):
        cyclic = [{**self.tasks[0], "depends_on": ["review"]}, self.tasks[1]]
        with self.assertRaises(ValueError):
            self.plan(tasks=cyclic)
        costly = [{**self.tasks[0], "expected_cost": 5}]
        plan = self.plan(tasks=costly)
        with self.assertRaises(ValueError):
            review_plan(plan["id"], 1, True, "No funds")
        self.assertEqual(list_tasks(self.board), [])
        add_treasury_entry("funding", 5, "EUR")
        plan = review_plan(plan["id"], 1, True, "Funded estimate")
        transition_company_goal_status(self.goal, "paused")
        self.assertIsNone(claim_work(plan["work"][0]["id"]))
        transition_company_goal_status(self.goal, "active")
        claim_work(plan["work"][0]["id"])
        self.assertEqual(reconcile_work(), 1)
        self.assertIsNone(claim_work(plan["work"][0]["id"]))
        self.assertEqual(get_plan(plan["id"])["work"][0]["status"], "blocked")

    def test_owner_card_edit_during_work_is_not_overwritten(self):
        plan = self.approved()
        work = plan["work"][0]
        claim_work(work["id"])
        task = next(
            t for t in list_tasks(self.board) if t["id"] == work["agile_task_id"]
        )
        update_task(task["id"], task["version"], title="Owner changed scope")
        finish_work(work["id"], error="Synthetic failure")
        self.assertEqual(get_plan(plan["id"])["work"][0]["status"], "blocked")
        self.assertEqual(
            next(t for t in list_tasks(self.board) if t["id"] == task["id"])["title"],
            "Owner changed scope",
        )

    def test_owner_edits_after_reasoning_and_invalid_decision_lineage_fail_closed(self):
        plan = self.approved()
        work = plan["work"][0]
        claim_work(work["id"])
        unrelated = log_decision("Other scope", ["ceo"], "Synthetic", "Pending")
        with self.assertRaises(ValueError):
            finish_work(work["id"], decision_id=unrelated)
        decision = log_decision(
            "Research", ["cso"], "Synthetic", "Pending", goal_id=self.goal
        )
        finish_work(work["id"], decision_id=decision)
        card = next(
            t for t in list_tasks(self.board) if t["id"] == work["agile_task_id"]
        )
        update_task(card["id"], card["version"], title="Changed after reasoning")
        with self.assertRaises(RuntimeError):
            review_work(work["id"], True, "Stale review")
        self.assertEqual(get_plan(plan["id"])["work"][0]["status"], "review")

    def test_dispatch_to_tool_free_pending_recommendations_only(self):
        plan = self.approved()
        with patch(
            "workflows.executive_planning.run_executive_meeting",
            return_value={
                "participants": ["cso"],
                "final_decision": "Evidence required",
                "individual_outputs": {"cso": "Published synthetic analysis"},
            },
        ) as meeting:
            result = asyncio.run(dispatch_planned_work())
            self.assertEqual(len(result["dispatched_work_ids"]), 1)
            self.assertEqual(meeting.call_count, 1)
            self.assertTrue(
                all(
                    not agent.tools
                    for agent in meeting.call_args.kwargs["agents_source"].values()
                )
            )
            self.assertEqual(
                asyncio.run(dispatch_planned_work())["dispatched_work_ids"], []
            )
        with get_connection() as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM action_queue").fetchone()[0], 0
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM treasury_entries").fetchone()[0], 0
            )
        self.assertEqual(get_plan(plan["id"])["work"][0]["status"], "review")


if __name__ == "__main__":
    unittest.main()
