"""Crash-safe step claim ledger.

The ledger intentionally never automatically retries an interrupted/unknown
side-effect. Approved actions and synchronous agent tasks use this ledger.
Unknown outcomes require owner reconciliation rather than automatic replay.
"""

import datetime
from memory.database import get_connection


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def init_step_checkpoints() -> None:
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
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
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(workflow_step_checkpoints)")
        }
        if "input_digest" not in columns:
            conn.execute(
                "ALTER TABLE workflow_step_checkpoints ADD COLUMN input_digest TEXT"
            )
        if "result_json" not in columns:
            conn.execute(
                "ALTER TABLE workflow_step_checkpoints ADD COLUMN result_json TEXT"
            )
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


def get_step(run_id: str, step_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM workflow_step_checkpoints WHERE run_id = ? AND step_id = ?",
            (run_id, step_id),
        ).fetchone()
        return dict(row) if row else None


class StepNeedsReview(RuntimeError):
    """An interrupted step cannot safely be retried without reconciliation."""


def run_json_step(run_id: str, step_id: str, input_digest: str, callback):
    """Resume a completed JSON result, or claim once before invoking callback.

    Inputs are bound to the durable key. Unknown results always block replay,
    including a crash between a callback's effect and saving its result.
    """
    import json

    init_step_checkpoints()
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            "SELECT * FROM workflow_step_checkpoints WHERE run_id = ? AND step_id = ?",
            (run_id, step_id),
        ).fetchone()
        if existing:
            if existing["input_digest"] != input_digest:
                raise StepNeedsReview(
                    "Checkpoint inputs changed; use a new owner-reviewed run"
                )
            if (
                existing["status"] == "succeeded"
                and existing["result_json"] is not None
            ):
                return json.loads(existing["result_json"])
            raise StepNeedsReview(
                "Step is running or interrupted; manual reconciliation required"
            )
        for value in (run_id, step_id):
            if not isinstance(value, str) or not 1 <= len(value) <= 128:
                raise ValueError("Invalid checkpoint key")
        if not isinstance(input_digest, str) or len(input_digest) != 64:
            raise ValueError("Invalid checkpoint input digest")
        now = _utcnow()
        conn.execute(
            """INSERT INTO workflow_step_checkpoints
               (run_id, step_id, status, created_at, updated_at, input_digest)
               VALUES (?, ?, 'running', ?, ?, ?)""",
            (run_id, step_id, now, now, input_digest),
        )
        conn.commit()
    try:
        result = callback()
        encoded = json.dumps(result, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode("utf-8")) > 2 * 1024 * 1024:
            raise ValueError("Checkpoint result exceeds 2 MiB")
        with get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                """UPDATE workflow_step_checkpoints
                   SET status = 'succeeded', result_json = ?, updated_at = ?
                   WHERE run_id = ? AND step_id = ? AND status = 'running' """,
                (encoded, _utcnow(), run_id, step_id),
            )
            if cursor.rowcount != 1:
                raise StepNeedsReview(
                    "Step completion raced with recovery; manual reconciliation required"
                )
            conn.commit()
        return result
    except BaseException:
        finish_step(run_id, step_id, "inconclusive")
        raise
