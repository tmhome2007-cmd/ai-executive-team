"""Reviewed executive work plans. Dispatch creates tool-free recommendations only."""

import datetime
import json
import re
from memory.database import get_connection
from memory.agile import OWNERS
from memory.experiments import _text, _number


def init_planning(cursor):
    cursor.execute("""CREATE TABLE IF NOT EXISTS executive_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT, run_key TEXT NOT NULL UNIQUE,
        goal_id INTEGER NOT NULL, board_id INTEGER NOT NULL, title TEXT NOT NULL,
        proposer TEXT NOT NULL, proposal_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'proposed',
        version INTEGER NOT NULL DEFAULT 1, review_note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS planned_work (
        id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id INTEGER NOT NULL, task_key TEXT NOT NULL,
        agile_task_id INTEGER NOT NULL, assignee TEXT NOT NULL, depends_json TEXT NOT NULL,
        expected_cost REAL NOT NULL, currency TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'waiting',
        claimed_card_version INTEGER,
        claimed_once INTEGER NOT NULL DEFAULT 0, decision_id INTEGER, note TEXT NOT NULL DEFAULT '',
        UNIQUE(plan_id, task_key)
    )""")


def _proposal(tasks):
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 20:
        raise ValueError("A plan needs one to twenty tasks")
    normalized = []
    for task in tasks:
        if not isinstance(task, dict) or set(task) != {
            "key",
            "title",
            "acceptance_criteria",
            "assignee",
            "depends_on",
            "expected_cost",
            "currency",
        }:
            raise ValueError("Invalid task proposal fields")
        item = dict(task)
        if not isinstance(item["key"], str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,40}", item["key"]
        ):
            raise ValueError("Invalid task key")
        item["title"] = _text(item["title"], "task title", 200)
        item["acceptance_criteria"] = _text(
            item["acceptance_criteria"], "acceptance criteria", 10000
        )
        if item["assignee"] not in OWNERS - {"owner"}:
            raise ValueError("Assign proposed work to a known executive")
        item["expected_cost"] = _number(
            item["expected_cost"], "expected cost", positive=True
        )
        if not isinstance(item["currency"], str) or not re.fullmatch(
            r"[A-Z]{3}", item["currency"]
        ):
            raise ValueError("Invalid plan currency")
        dependencies = item["depends_on"]
        if (
            not isinstance(dependencies, list)
            or len(dependencies) > 20
            or any(not isinstance(key, str) for key in dependencies)
            or len(set(dependencies)) != len(dependencies)
        ):
            raise ValueError("Invalid dependency list")
        normalized.append(item)
    keys = {t["key"] for t in normalized}
    if len(keys) != len(normalized) or any(
        set(t["depends_on"]) - keys for t in normalized
    ):
        raise ValueError("Duplicate or missing dependency keys")
    completed = set()
    while len(completed) < len(keys):
        ready = {
            t["key"] for t in normalized if set(t["depends_on"]) <= completed
        } - completed
        if not ready:
            raise ValueError("Plan dependency cycle")
        completed |= ready
    return normalized


def _available(cursor, currency):
    cash = cursor.execute(
        "SELECT COALESCE(SUM(CASE WHEN entry_type = 'spend' THEN -amount ELSE amount END),0) FROM treasury_entries WHERE currency = ?",
        (currency,),
    ).fetchone()[0]
    reserved = cursor.execute(
        "SELECT COALESCE(SUM(amount),0) FROM treasury_reservations WHERE currency = ? AND status = 'active'",
        (currency,),
    ).fetchone()[0]
    return cash - reserved


def create_plan(*, run_key, goal_id, board_id, title, proposer, tasks):
    run_key = _text(run_key, "plan run key", 100)
    title = _text(title, "plan title", 200)
    if proposer not in OWNERS - {"owner"}:
        raise ValueError("Unknown proposing executive")
    tasks = _proposal(tasks)
    proposal = json.dumps(tasks, sort_keys=True)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        old = cursor.execute(
            "SELECT * FROM executive_plans WHERE run_key = ?", (run_key,)
        ).fetchone()
        if old:
            if any(
                old[k] != v
                for k, v in [
                    ("goal_id", goal_id),
                    ("board_id", board_id),
                    ("title", title),
                    ("proposer", proposer),
                    ("proposal_json", proposal),
                ]
            ):
                raise RuntimeError("Plan run key reused with different inputs")
            return get_plan(old["id"])
        goal = cursor.execute(
            "SELECT status FROM company_goals WHERE id = ?", (goal_id,)
        ).fetchone()
        board = cursor.execute(
            "SELECT kind FROM agile_boards WHERE id = ?", (board_id,)
        ).fetchone()
        if (
            not goal
            or goal["status"] != "active"
            or not board
            or board["kind"] != "company"
        ):
            raise ValueError("Plans require an active goal and a company board")
        cursor.execute(
            """INSERT INTO executive_plans(run_key, goal_id, board_id, title, proposer, proposal_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                run_key,
                goal_id,
                board_id,
                title,
                proposer,
                proposal,
                datetime.datetime.now(datetime.timezone.utc).isoformat(),
            ),
        )
        ident = cursor.lastrowid
        conn.commit()
    return get_plan(ident)


def review_plan(ident, expected_version, approved, note):
    note = _text(note, "plan review note", 4000)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        plan = cursor.execute(
            "SELECT * FROM executive_plans WHERE id = ?", (ident,)
        ).fetchone()
        if not plan:
            raise LookupError("Plan not found")
        if plan["status"] != "proposed" or plan["version"] != expected_version:
            raise RuntimeError("Plan already reviewed or changed")
        if approved:
            goal = cursor.execute(
                "SELECT status FROM company_goals WHERE id = ?", (plan["goal_id"],)
            ).fetchone()
            if not goal or goal["status"] != "active":
                raise ValueError("Goal must remain active")
            tasks = json.loads(plan["proposal_json"])
            totals = {}
            for task in tasks:
                totals[task["currency"]] = (
                    totals.get(task["currency"], 0) + task["expected_cost"]
                )
            if any(
                total > _available(cursor, currency) + 1e-9
                for currency, total in totals.items()
            ):
                raise ValueError(
                    "Plan exceeds current available treasury; approval does not fund it"
                )
            for task in tasks:
                now = datetime.datetime.now().isoformat()
                cursor.execute(
                    """INSERT INTO agile_tasks(board_id,title,description,acceptance_criteria,assignee,priority,status,blocked_reason,completion_note,goal_id,created_at,updated_at)
                    VALUES (?, ?, ?, ?, ?, 'medium', 'ready', '', '', ?, ?, ?)""",
                    (
                        plan["board_id"],
                        task["title"],
                        f"Executive plan #{ident}; dependencies: {', '.join(task['depends_on']) or 'none'}",
                        task["acceptance_criteria"],
                        task["assignee"],
                        plan["goal_id"],
                        now,
                        now,
                    ),
                )
                task_id = cursor.lastrowid
                cursor.execute(
                    """INSERT INTO planned_work(plan_id,task_key,agile_task_id,assignee,depends_json,expected_cost,currency)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        ident,
                        task["key"],
                        task_id,
                        task["assignee"],
                        json.dumps(task["depends_on"]),
                        task["expected_cost"],
                        task["currency"],
                    ),
                )
        cursor.execute(
            "UPDATE executive_plans SET status = ?, version = version + 1, review_note = ? WHERE id = ? AND version = ?",
            ("approved" if approved else "rejected", note, ident, expected_version),
        )
        conn.commit()
    return get_plan(ident)


def get_plan(ident):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM executive_plans WHERE id = ?", (ident,)
        ).fetchone()
        if not row:
            return None
        plan = dict(row)
        plan["tasks"] = json.loads(plan.pop("proposal_json"))
        plan["work"] = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM planned_work WHERE plan_id = ? ORDER BY id", (ident,)
            )
        ]
        return plan


def list_plans(limit=50, offset=0):
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError("Invalid plan pagination")
    with get_connection() as conn:
        ids = [
            r[0]
            for r in conn.execute(
                "SELECT id FROM executive_plans ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        ]
    return [get_plan(i) for i in ids]


def claim_work(ident):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        work = cursor.execute(
            """SELECT w.*, p.goal_id, p.status AS plan_status, t.title, t.acceptance_criteria,
            t.assignee AS current_assignee, t.status AS card_status, t.version AS card_version, t.goal_id AS card_goal_id
            FROM planned_work w JOIN executive_plans p ON p.id = w.plan_id JOIN agile_tasks t ON t.id = w.agile_task_id WHERE w.id = ?""",
            (ident,),
        ).fetchone()
        if (
            not work
            or work["status"] != "waiting"
            or work["claimed_once"]
            or work["plan_status"] != "approved"
            or work["card_status"] != "ready"
            or work["current_assignee"] != work["assignee"]
            or work["card_goal_id"] != work["goal_id"]
        ):
            return None
        goal = cursor.execute(
            "SELECT status FROM company_goals WHERE id = ?", (work["goal_id"],)
        ).fetchone()
        if (
            not goal
            or goal["status"] != "active"
            or work["expected_cost"] > _available(cursor, work["currency"]) + 1e-9
        ):
            return None
        states = {
            r["task_key"]: r["status"]
            for r in cursor.execute(
                "SELECT task_key, status FROM planned_work WHERE plan_id = ?",
                (work["plan_id"],),
            )
        }
        if (
            any(states.get(key) != "done" for key in json.loads(work["depends_json"]))
            or cursor.execute(
                "SELECT id FROM planned_work WHERE assignee = ? AND status = 'running' LIMIT 1",
                (work["assignee"],),
            ).fetchone()
        ):
            return None
        cursor.execute(
            "UPDATE planned_work SET status = 'running', claimed_once = 1, claimed_card_version = ? WHERE id = ? AND status = 'waiting' AND claimed_once = 0",
            (work["card_version"] + 1, ident),
        )
        cursor.execute(
            "UPDATE agile_tasks SET status = 'in_progress', updated_at = ?, version = version + 1 WHERE id = ?",
            (datetime.datetime.now().isoformat(), work["agile_task_id"]),
        )
        conn.commit()
        return dict(work)


def finish_work(ident, decision_id=None, error=None):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        work = cursor.execute(
            "SELECT * FROM planned_work WHERE id = ? AND status = 'running'", (ident,)
        ).fetchone()
        if not work:
            return False
        if decision_id is not None:
            linked = cursor.execute(
                "SELECT d.goal_id FROM decisions d WHERE d.id = ?", (decision_id,)
            ).fetchone()
            goal = cursor.execute(
                "SELECT goal_id FROM executive_plans WHERE id = ?", (work["plan_id"],)
            ).fetchone()
            if not linked or linked["goal_id"] != goal["goal_id"]:
                raise ValueError("Recommendation must belong to the same plan goal")
        elif not error:
            raise ValueError("Completed reasoning requires a persisted recommendation")
        state = "blocked" if error else "review"
        note = (
            "Interrupted or failed reasoning; owner review required"
            if error
            else "Published recommendation awaits owner review; direction remains pending"
        )
        current_card = cursor.execute(
            "SELECT version FROM agile_tasks WHERE id = ?", (work["agile_task_id"],)
        ).fetchone()
        if not current_card or current_card["version"] != work["claimed_card_version"]:
            cursor.execute(
                "UPDATE planned_work SET status = 'blocked', decision_id = ?, note = 'Card changed during reasoning; review manually' WHERE id = ?",
                (decision_id, ident),
            )
            conn.commit()
            return True
        cursor.execute(
            "UPDATE planned_work SET status = ?, decision_id = ?, note = ? WHERE id = ?",
            (state, decision_id, note, ident),
        )
        cursor.execute(
            "UPDATE agile_tasks SET status = ?, blocked_reason = ?, decision_id = ?, updated_at = ?, version = version + 1 WHERE id = ?",
            (
                state,
                note if error else "",
                decision_id,
                datetime.datetime.now().isoformat(),
                work["agile_task_id"],
            ),
        )
        conn.commit()
        return True


def review_work(ident, approved, note):
    note = _text(note, "work review note", 4000)
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM planned_work WHERE id = ? AND status = 'review'", (ident,)
        ).fetchone()
        if not row:
            raise RuntimeError("Work is not awaiting review")
        card = conn.execute(
            "SELECT version, status FROM agile_tasks WHERE id = ?",
            (row["agile_task_id"],),
        ).fetchone()
        if (
            not card
            or card["status"] != "review"
            or card["version"] != row["claimed_card_version"] + 1
        ):
            raise RuntimeError(
                "Card changed after reasoning; review the changed work manually"
            )
        state = "done" if approved else "blocked"
        conn.execute(
            "UPDATE planned_work SET status = ?, note = ? WHERE id = ?",
            (state, note, ident),
        )
        conn.execute(
            "UPDATE agile_tasks SET status = ?, completion_note = ?, blocked_reason = ?, updated_at = ?, version = version + 1 WHERE id = ?",
            (
                state,
                note if approved else "",
                note if not approved else "",
                datetime.datetime.now().isoformat(),
                row["agile_task_id"],
            ),
        )
        conn.commit()
    return {"id": ident, "status": state}


def reconcile_work():
    with get_connection() as conn:
        ids = [
            r[0]
            for r in conn.execute(
                "SELECT id FROM planned_work WHERE status = 'running'"
            )
        ]
    for ident in ids:
        finish_work(ident, error="interrupted")
    return len(ids)


def workload():
    with get_connection() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT assignee, status, COUNT(*) AS count FROM planned_work GROUP BY assignee, status ORDER BY assignee, status"
            )
        ]
