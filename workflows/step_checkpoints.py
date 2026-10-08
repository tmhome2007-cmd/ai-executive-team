"""Crash-safe step claim ledger.

The ledger intentionally never automatically retries an interrupted/unknown
side-effect. This is a primitive for future workflow integration, not a claim
that all existing workflows already use checkpoints.
"""
import datetime
import sqlite3
from memory.database import get_connection


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def init_step_checkpoints() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workflow_step_checkpoints (
                run_id TEXT NOT NULL,
                step_id TEXT NOT NULL,
                status TEXT NOT NULL
                    CHECK (status IN ('running','succeeded','failed','inconclusive')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (run_id, step_id)
            )
        """)
        conn.commit()


def claim_step(run_id: str, step_id: str) -> bool:
    """Exactly one owner can claim a step key; any prior status blocks replay."""
    for value in (run_id, step_id):
        if not isinstance(value, str) or not (1 <= len(value) <= 128):
            raise ValueError("Invalid checkpoint key")
    now = _utcnow()
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            """INSERT OR IGNORE INTO workflow_step_checkpoints
               (run_id, step_id, status, created_at, updated_at)
               VALUES (?, ?, 'running', ?, ?)""",
            (run_id, step_id, now, now),
        )
        claimed = cursor.rowcount == 1
        conn.commit()
        return claimed


def finish_step(run_id: str, step_id: str, outcome: str) -> bool:
    """Write terminal state once. Never rewrite a completed/uncertain step."""
    if outcome not in ("succeeded", "failed", "inconclusive"):
        raise ValueError("Invalid step outcome")
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            """UPDATE workflow_step_checkpoints SET status = ?, updated_at = ?
               WHERE run_id = ? AND step_id = ? AND status = 'running'""",
            (outcome, _utcnow(), run_id, step_id),
        )
        conn.commit()
        return cursor.rowcount == 1


def reconcile_interrupted_steps() -> int:
    """On startup, mark unknown results as inconclusive, never retry them."""
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            """UPDATE workflow_step_checkpoints SET status = 'inconclusive',
               updated_at = ? WHERE status = 'running'""",
            (_utcnow(),),
        )
        count = cursor.rowcount
        conn.commit()
        return count
