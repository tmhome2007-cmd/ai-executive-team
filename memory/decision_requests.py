"""Local generation request identity; hashes/status only, never action approval."""

import datetime
import re


class RequestConflict(ValueError):
    pass


def init_decision_requests(cursor):
    cursor.execute("""CREATE TABLE IF NOT EXISTS decision_generation_requests (
        request_id TEXT PRIMARY KEY,
        input_hash TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('generating','completed','failed','interrupted','closed')),
        decision_id INTEGER REFERENCES decisions(id),
        reason_code TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""")


def _identity(request_id):
    if not isinstance(request_id, str) or not re.fullmatch(
        r"[A-Za-z0-9:_-]{1,80}", request_id
    ):
        raise ValueError("Invalid generation request identity")


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _status(cursor, request_id):
    row = cursor.execute(
        "SELECT request_id,status,decision_id,reason_code,created_at,updated_at FROM decision_generation_requests WHERE request_id=?",
        (request_id,),
    ).fetchone()
    saved = cursor.execute(
        "SELECT id FROM decisions WHERE workflow_key=?", (request_id,)
    ).fetchone()
    if saved:
        if row and row["status"] != "completed":
            cursor.execute(
                "UPDATE decision_generation_requests SET status='completed',decision_id=?,reason_code=NULL,updated_at=? WHERE request_id=?",
                (saved["id"], _now(), request_id),
            )
        return {
            "request_id": request_id,
            "status": "completed",
            "decision_id": saved["id"],
            "reason_code": None,
        }
    return dict(row) if row else None


def claim(request_id, input_hash):
    """Exactly one caller owns generation; a closed identity cannot arrive late."""
    from memory.database import get_connection

    _identity(request_id)
    if not re.fullmatch(r"[0-9a-f]{64}", input_hash):
        raise ValueError("Invalid request input hash")
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        previous = cursor.execute(
            "SELECT input_hash,status FROM decision_generation_requests WHERE request_id=?",
            (request_id,),
        ).fetchone()
        if previous:
            if previous["status"] == "closed":
                status = _status(cursor, request_id)
                conn.commit()
                return False, status
            if previous["input_hash"] != input_hash:
                raise RequestConflict(
                    "Request identity already belongs to different inputs"
                )
            status = _status(cursor, request_id)
            conn.commit()
            return False, status
        if cursor.execute(
            "SELECT id FROM decisions WHERE workflow_key=?", (request_id,)
        ).fetchone():
            raise RequestConflict(
                "Request identity belongs to a historical saved decision"
            )
        now = _now()
        cursor.execute(
            "INSERT INTO decision_generation_requests(request_id,input_hash,status,created_at,updated_at) VALUES(?,?,'generating',?,?)",
            (request_id, input_hash, now, now),
        )
        conn.commit()
        return True, {
            "request_id": request_id,
            "status": "generating",
            "decision_id": None,
            "reason_code": None,
        }


def inspect(request_id):
    from memory.database import get_connection

    _identity(request_id)
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        value = _status(conn.cursor(), request_id)
        conn.commit()
        return value


def finish(request_id, decision_id=None, reason_code=None):
    from memory.database import get_connection

    _identity(request_id)
    if reason_code not in {None, "input_rejected", "generation_failed"}:
        raise ValueError("Unsupported sanitized request reason")
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        saved = _status(cursor, request_id)
        if saved and saved["status"] == "completed":
            if decision_id is not None and saved["decision_id"] != decision_id:
                raise ValueError("Completed request belongs to another decision")
        elif decision_id is not None:
            raise ValueError(
                "A request can only complete against its saved workflow decision"
            )
        else:
            cursor.execute(
                "UPDATE decision_generation_requests SET status='failed',reason_code=?,updated_at=? WHERE request_id=? AND status='generating'",
                (reason_code, _now(), request_id),
            )
        conn.commit()


def close(request_id):
    """Owner closes only unstarted or terminal work; never cancels a live meeting."""
    from memory.database import get_connection

    _identity(request_id)
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        state = _status(cursor, request_id)
        if state and state["status"] == "generating":
            raise RequestConflict(
                "Generation is still queued or running; inspect again later"
            )
        if state:
            conn.commit()
            return state
        now = _now()
        cursor.execute(
            "INSERT INTO decision_generation_requests(request_id,input_hash,status,created_at,updated_at) VALUES(?,'','closed',?,?)",
            (request_id, now, now),
        )
        conn.commit()
        return {
            "request_id": request_id,
            "status": "closed",
            "decision_id": None,
            "reason_code": None,
        }


def recover_interrupted_requests():
    """Call only during startup protected by the database instance lock."""
    from memory.database import get_connection

    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        pending = cursor.execute(
            "SELECT request_id FROM decision_generation_requests WHERE status='generating'"
        ).fetchall()
        interrupted = 0
        for row in pending:
            state = _status(cursor, row["request_id"])
            if state["status"] != "completed":
                cursor.execute(
                    "UPDATE decision_generation_requests SET status='interrupted',reason_code=NULL,updated_at=? WHERE request_id=?",
                    (_now(), row["request_id"]),
                )
                interrupted += 1
        conn.commit()
        return interrupted
