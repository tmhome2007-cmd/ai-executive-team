"""Owner-reviewed memory lifecycle with retained source-backed revisions."""

import datetime
import json
import uuid
from memory.database import get_connection
from memory.experiments import _text, _date


def init_memory_reconciliation(cursor):
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS memory_lifecycle (
        memory_id INTEGER PRIMARY KEY, version INTEGER NOT NULL DEFAULT 1,
        state TEXT NOT NULL DEFAULT 'active', claim_key TEXT NOT NULL DEFAULT '',
        source_ids TEXT NOT NULL DEFAULT '[]', expires_at TEXT, superseded_by INTEGER)"""
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS memory_claim ON memory_lifecycle(claim_key,state,memory_id)"
    )
    cursor.execute("""CREATE TABLE IF NOT EXISTS memory_revisions (
        id INTEGER PRIMARY KEY, memory_id INTEGER NOT NULL, version INTEGER NOT NULL,
        operation TEXT NOT NULL, previous_lesson TEXT NOT NULL, replacement_id INTEGER,
        source_ids TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL,
        UNIQUE(memory_id,version))""")
    cursor.execute(
        "CREATE TRIGGER IF NOT EXISTS curated_memory_preserve BEFORE UPDATE OF lesson,supporting_evidence ON executive_memories WHEN EXISTS(SELECT 1 FROM memory_lifecycle WHERE memory_id=OLD.id) BEGIN SELECT RAISE(ABORT,'Correct curated memories through retained revisions'); END"
    )
    cursor.execute(
        "CREATE TRIGGER IF NOT EXISTS curated_memory_no_delete BEFORE DELETE ON executive_memories WHEN EXISTS(SELECT 1 FROM memory_lifecycle WHERE memory_id=OLD.id) BEGIN SELECT RAISE(ABORT,'Curated memory provenance is retained'); END"
    )
    for operation in ("UPDATE", "DELETE"):
        cursor.execute(
            f"CREATE TRIGGER IF NOT EXISTS memory_revision_no_{operation.lower()} BEFORE {operation} ON memory_revisions BEGIN SELECT RAISE(ABORT,'Memory provenance is retained'); END"
        )  # nosec B608 # Literal operations.


def curated_memories(limit=50, offset=0):
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError("Invalid memory pagination")
    with get_connection() as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT m.*,COALESCE(l.version,1) AS version,COALESCE(l.state,'active') AS lifecycle_state,COALESCE(l.claim_key,'') AS claim_key,COALESCE(l.source_ids,'[]') AS source_ids,l.expires_at,l.superseded_by FROM executive_memories m LEFT JOIN memory_lifecycle l ON l.memory_id=m.id ORDER BY m.id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        ]
        conflicts = {
            r[0]
            for r in conn.execute(
                "SELECT l.claim_key FROM memory_lifecycle l JOIN executive_memories m ON m.id=l.memory_id WHERE l.claim_key!='' AND l.state IN ('active','conflicted') AND m.is_active=1 GROUP BY l.claim_key HAVING COUNT(DISTINCT m.lesson)>1"
            )
        }
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for row in rows:
        row["source_ids"] = json.loads(row["source_ids"])
        row["conflict_review_required"] = (
            row["claim_key"] in conflicts or row["lifecycle_state"] == "conflicted"
        )
        row["expired"] = bool(
            row["expires_at"]
            and datetime.datetime.fromisoformat(
                row["expires_at"].replace("Z", "+00:00")
            )
            <= datetime.datetime.fromisoformat(now)
        )
    return rows


def reconcile_memory(
    ident,
    *,
    expected_version,
    operation,
    source_ids,
    note,
    lesson=None,
    claim_key="",
    expires_at=None,
):
    if operation not in {"annotate", "correct", "expire", "conflict"}:
        raise ValueError("Invalid memory operation")
    note = _text(note, "memory review note", 2000)
    claim_key = _text(claim_key, "claim key", 120, required=False)
    if (
        not isinstance(source_ids, list)
        or not 1 <= len(source_ids) <= 20
        or any(type(i) is not int or i < 1 for i in source_ids)
        or len(set(source_ids)) != len(source_ids)
    ):
        raise ValueError("Memory reconciliation requires unique source IDs")
    if operation == "correct":
        lesson = _text(lesson, "corrected lesson", 2000)
    elif lesson is not None:
        raise ValueError("Only corrections can replace a lesson")
    expires_at = _date(expires_at, "memory expiry") if expires_at else None
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM executive_memories WHERE id=?", (ident,)
        ).fetchone()
        if not row:
            raise LookupError("Memory not found")
        conn.execute(
            "INSERT OR IGNORE INTO memory_lifecycle(memory_id) VALUES(?)", (ident,)
        )
        state = dict(
            conn.execute(
                "SELECT * FROM memory_lifecycle WHERE memory_id=?", (ident,)
            ).fetchone()
        )
        if type(expected_version) is not int or state["version"] != expected_version:
            raise RuntimeError("Memory changed; refresh")
        if state["state"] == "conflicted" and operation == "annotate":
            raise RuntimeError("Conflicted memories require a source-backed correction")
        if state["state"] in {"superseded", "expired"}:
            raise RuntimeError("Terminal memory cannot be reactivated")
        for source in source_ids:
            record = conn.execute(
                "SELECT verification,expires_at FROM evidence_sources WHERE id=?",
                (source,),
            ).fetchone()
            if not record:
                raise LookupError("Source not found")
            if record["verification"] == "disputed" or (
                record["expires_at"]
                and datetime.datetime.fromisoformat(
                    record["expires_at"].replace("Z", "+00:00")
                )
                <= datetime.datetime.fromisoformat(now)
            ):
                raise ValueError("Memory requires current, undisputed source records")
        replacement = None
        if operation == "correct":
            replacement = conn.execute(
                """INSERT INTO executive_memories(created_at,updated_at,executive_key,memory_kind,lesson,supporting_evidence,confidence,is_active,source_goal_id,source_goal_sync_uuid,source_decision_id,source_decision_sync_uuid,source_action_id,source_action_sync_uuid,fingerprint,sync_uuid)
                VALUES(?,?,?,?,?,?,?,1,?,?,?,?,?,?,?,?)""",
                (
                    now,
                    now,
                    row["executive_key"],
                    row["memory_kind"],
                    lesson,
                    "Owner-reviewed correction; source IDs: "
                    + ",".join(map(str, source_ids)),
                    row["confidence"],
                    row["source_goal_id"],
                    row["source_goal_sync_uuid"],
                    row["source_decision_id"],
                    row["source_decision_sync_uuid"],
                    row["source_action_id"],
                    row["source_action_sync_uuid"],
                    "revision:" + str(uuid.uuid4()),
                    str(uuid.uuid4()),
                ),
            ).lastrowid
            conn.execute(
                "INSERT INTO memory_lifecycle(memory_id,claim_key,source_ids,expires_at) VALUES(?,?,?,?)",
                (replacement, claim_key, json.dumps(source_ids), expires_at),
            )
        next_state = {
            "correct": "superseded",
            "expire": "expired",
            "conflict": "conflicted",
            "annotate": "active",
        }[operation]
        conn.execute(
            "INSERT INTO memory_revisions(memory_id,version,operation,previous_lesson,replacement_id,source_ids,note,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (
                ident,
                expected_version + 1,
                operation,
                row["lesson"],
                replacement,
                json.dumps(source_ids),
                note,
                now,
            ),
        )
        conn.execute(
            "UPDATE memory_lifecycle SET version=version+1,state=?,claim_key=?,source_ids=?,expires_at=?,superseded_by=? WHERE memory_id=?",
            (
                next_state,
                claim_key,
                json.dumps(source_ids),
                expires_at,
                replacement,
                ident,
            ),
        )
        if next_state != "active":
            conn.execute(
                "UPDATE executive_memories SET is_active=0 WHERE id=?", (ident,)
            )
        conn.commit()
    return {
        "memory_id": ident,
        "version": expected_version + 1,
        "state": next_state,
        "replacement_id": replacement,
    }


def expire_memories():
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            "SELECT memory_id,version,source_ids FROM memory_lifecycle WHERE state='active' AND expires_at IS NOT NULL AND julianday(expires_at)<=julianday(?)",
            (now,),
        ).fetchall()
        for row in rows:
            original = conn.execute(
                "SELECT lesson FROM executive_memories WHERE id=?", (row["memory_id"],)
            ).fetchone()
            conn.execute(
                "INSERT INTO memory_revisions(memory_id,version,operation,previous_lesson,source_ids,note,created_at) VALUES(?,?,?,?,?,?,?)",
                (
                    row["memory_id"],
                    row["version"] + 1,
                    "expire",
                    original["lesson"],
                    row["source_ids"],
                    "Configured expiry reached",
                    now,
                ),
            )
            conn.execute(
                "UPDATE memory_lifecycle SET state='expired',version=version+1 WHERE memory_id=?",
                (row["memory_id"],),
            )
            conn.execute(
                "UPDATE executive_memories SET is_active=0 WHERE id=?",
                (row["memory_id"],),
            )
        conn.commit()
    return len(rows)
