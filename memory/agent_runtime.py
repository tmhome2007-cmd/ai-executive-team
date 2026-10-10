"""Observed executive runs; store identifiers and states, never conversation text."""

import datetime
from memory.database import get_connection


def init_agent_runtime(cursor):
    cursor.execute("""CREATE TABLE IF NOT EXISTS agent_runtime (
        id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, step_id TEXT NOT NULL,
        executive_key TEXT NOT NULL, state TEXT NOT NULL, updated_at TEXT NOT NULL,
        UNIQUE(run_id,step_id))""")


def record_state(run_id, step_id, executive_key, state):
    from workflows.capability_policy import ROLE_ALIASES

    if executive_key not in set(ROLE_ALIASES.values()) or state not in {
        "running",
        "idle",
        "unknown",
    }:
        raise ValueError("Invalid executive runtime state")
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO agent_runtime(run_id,step_id,executive_key,state,updated_at)
            VALUES(?,?,?,?,?) ON CONFLICT(run_id,step_id) DO UPDATE SET
            state=excluded.state,updated_at=excluded.updated_at""",
            (
                run_id,
                step_id,
                executive_key,
                state,
                datetime.datetime.now(datetime.timezone.utc).isoformat(),
            ),
        )
        conn.commit()


def recover_agent_runtime():
    with get_connection() as conn:
        conn.execute("UPDATE agent_runtime SET state='unknown' WHERE state='running'")
        conn.commit()
