"""
memory/database.py

SQLite-opslaglaag voor het opslaan en ophalen van beslissingen 
en actievoorstellen van het AI Executive Team.
"""

import os
import sqlite3
import datetime
import sys
import uuid
import json
import threading
import hashlib
import hmac
from pathlib import Path
from contextlib import contextmanager

# Zorg ervoor dat de hoofdmap van het project bereikbaar is voor imports
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from config import config
from workflows.meeting_types import VALID_MEETING_TYPES


VALID_ACTION_STATUSES = {
    "pending",
    "approved",
    "rejected",
    "executing",
    "executed",
    "executed_dry_run",
    "blocked_dangerous",
    "execution_failed",
}
VALID_ACTION_TYPES = {"shell", "file_operation", "browser_action"}
VALID_DECISION_APPROVAL_STATUSES = {"pending", "approved", "rejected"}
VALID_PREPARATION_STATUSES = {"not_started", "in_progress", "completed", "failed"}
VALID_RESOURCE_REQUEST_STATUSES = {"pending", "approved", "rejected", "fulfilled"}
VALID_RESOURCE_TYPES = {
    "access", "credential", "plugin", "data", "budget", "service", "hardware", "other"
}
VALID_TREASURY_ENTRY_TYPES = {"funding", "spend", "refund"}
VALID_TREASURY_RESERVATION_STATUSES = {"active", "released", "consumed"}
VALID_GOAL_STATUSES = {"draft", "active", "paused", "completed", "abandoned"}
VALID_GOAL_PRIORITIES = {"critical", "high", "medium", "low"}
VALID_FOLLOWUP_STATUSES = {"open", "resolved", "dismissed"}
VALID_FOLLOWUP_SEVERITIES = {"info", "attention", "critical"}
VALID_EXECUTIVE_MEMORY_KINDS = {
    "decision_approved",
    "decision_rejected",
    "outcome_succeeded",
    "outcome_failed",
    "outcome_partial",
    "outcome_inconclusive",
    "general_lesson",
}
VALID_FOLLOWUP_EVENT_TYPES = {
    "strategy_review",
    "owner_decision_review",
    "owner_preparation_review",
    "owner_action_review",
    "owner_resource_review",
    "outcome_measurement",
    "adverse_outcome_review",
    "overdue_goal_review",
}
_ACTION_PROVENANCE_LOCK = threading.RLock()
_ACTION_PROVENANCE_CONTEXT: dict | None = None

VALID_OUTCOME_STATUSES = {
    "not_started",
    "measurement_pending",
    "succeeded",
    "failed",
    "partial",
    "inconclusive",
}

_SECRET_LIKE_PATTERNS = (
    "sk-",
    "ghp_",
    "github_pat_",
    "xoxb-",
    "xoxp-",
    "AIza",
    "-----BEGIN PRIVATE KEY-----",
    "password=",
    "api_key=",
    "token=",
)


def _reject_secret_like_text(*values: str | None) -> None:
    combined = "\n".join(value for value in values if value)
    lowered = combined.lower()
    for pattern in _SECRET_LIKE_PATTERNS:
        if pattern.lower() in lowered:
            raise ValueError(
                "Potential secret detected. Store credentials in the configured secret/plugin "
                "system and record only a non-secret description here."
            )


def _sync_signing_key() -> bytes:
    key = (getattr(config, "SYNC_HMAC_KEY", "") or config.API_SECRET_KEY).strip()
    if not key:
        raise ValueError("SYNC_HMAC_KEY/API_SECRET_KEY is required for authenticated sync")
    return key.encode("utf-8")


def _sync_record_signature(record: dict) -> str:
    payload = {
        key: value
        for key, value in record.items()
        if key != "_signature"
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hmac.new(_sync_signing_key(), canonical, hashlib.sha256).hexdigest()


def _sync_record_signature_valid(record: dict) -> bool:
    supplied = record.get("_signature")
    if not isinstance(supplied, str) or not supplied:
        return False
    expected = _sync_record_signature(record)
    return hmac.compare_digest(supplied, expected)


_SYNC_TABLE_COLUMNS = {
    "decisions": {
        "timestamp", "topic", "agents_involved", "task_description",
        "decision_outcome", "sandbox_mode", "sync_uuid", "goal_sync_uuid",
        "meeting_type",
    },
    "action_queue": {
        "timestamp", "proposed_by", "action_description", "action_detail",
        "status", "reviewed_at", "action_type", "result_detail", "sync_uuid",
        "source_decision_sync_uuid", "source_phase",
    },
    "action_outcomes": {
        "action_sync_uuid", "expected_outcome", "expected_impact",
        "expected_cost_amount", "currency", "outcome_status", "actual_outcome",
        "actual_impact", "actual_cost_amount", "measured_at",
        "next_recommendation", "notes", "updated_at", "sync_uuid",
    },
    "resource_requests": {
        "timestamp", "requested_by", "resource_type", "resource_name",
        "reason", "required_for", "amount", "currency", "status",
        "reviewed_at", "fulfilled_at", "fulfillment_note",
        "source_decision_sync_uuid", "source_phase", "sync_uuid",
    },
    "treasury_entries": {
        "timestamp", "entry_type", "amount", "currency", "note",
        "source_action_sync_uuid", "source_decision_sync_uuid", "sync_uuid",
    },
    "treasury_reservations": {
        "timestamp", "amount", "currency", "status", "released_at",
        "consumed_at", "source_action_sync_uuid", "source_decision_sync_uuid",
        "sync_uuid",
    },
    "company_goals": {
        "created_at", "updated_at", "title", "description", "success_criteria",
        "priority", "target_date", "status", "completed_at", "completion_note",
        "sync_uuid",
    },
    "followup_events": {
        "created_at", "updated_at", "event_type", "status", "severity",
        "reason", "fingerprint", "goal_sync_uuid", "source_action_sync_uuid",
        "source_decision_sync_uuid", "generated_decision_sync_uuid",
        "resolved_at", "sync_uuid",
    },
    "executive_memories": {
        "created_at", "updated_at", "executive_key", "memory_kind", "lesson",
        "supporting_evidence", "confidence", "is_active", "source_goal_sync_uuid",
        "source_decision_sync_uuid", "source_action_sync_uuid", "fingerprint",
        "sync_uuid",
    },
}


def init_db() -> None:
    """
    Initialiseert de SQLite-database.
    Maakt de mappen aan en bouwt de tabellen 'decisions' en 'action_queue' op.
    """
    db_path = config.DATABASE_PATH
    db_dir = os.path.dirname(db_path)
    
    # 1. Zorg ervoor dat de map van de database bestaat
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    # 2. Verbind met de database en maak de tabellen aan
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Tabel 0: owner-defined company goals / missions.
    # Agents may work toward these goals but cannot silently create or rewrite
    # them; mutations happen only through authenticated owner-facing APIs.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS company_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            success_criteria TEXT NOT NULL,
            priority TEXT NOT NULL,
            target_date TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            completed_at TEXT,
            completion_note TEXT,
            sync_uuid TEXT NOT NULL UNIQUE
        )
    """)
    conn.commit()

    # Autonomous follow-up audit queue. The deterministic scanner creates
    # these records; tool-free meetings may create a new pending decision, but
    # no follow-up event itself can approve/prepare/execute anything.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS followup_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            severity TEXT NOT NULL,
            reason TEXT NOT NULL,
            fingerprint TEXT NOT NULL UNIQUE,
            goal_id INTEGER,
            goal_sync_uuid TEXT,
            source_action_id INTEGER,
            source_action_sync_uuid TEXT,
            source_decision_id INTEGER,
            source_decision_sync_uuid TEXT,
            generated_decision_id INTEGER,
            generated_decision_sync_uuid TEXT,
            resolved_at TEXT,
            sync_uuid TEXT NOT NULL UNIQUE
        )
    """)
    conn.commit()

    # Structured executive memory. Memories are historical/advisory only:
    # they never override current evidence or owner-approved state.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS executive_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            executive_key TEXT NOT NULL,
            memory_kind TEXT NOT NULL,
            lesson TEXT NOT NULL,
            supporting_evidence TEXT,
            confidence REAL NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            source_goal_id INTEGER,
            source_goal_sync_uuid TEXT,
            source_decision_id INTEGER,
            source_decision_sync_uuid TEXT,
            source_action_id INTEGER,
            source_action_sync_uuid TEXT,
            fingerprint TEXT NOT NULL UNIQUE,
            sync_uuid TEXT NOT NULL UNIQUE
        )
    """)
    conn.commit()

    # Tabel 1: Bestuursbesluiten
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            topic TEXT NOT NULL,
            agents_involved TEXT NOT NULL,
            task_description TEXT NOT NULL,
            decision_outcome TEXT NOT NULL,
            sandbox_mode INTEGER NOT NULL,
            sync_uuid TEXT,
            goal_id INTEGER,
            goal_sync_uuid TEXT,
            meeting_type TEXT NOT NULL DEFAULT 'strategy'
        )
    """)

    # Migratie + backfill voor bestaande databases: sync_uuid is de STABIELE
    # identiteit van een rij over meerdere machines heen — de lokale
    # autoincrement 'id' is dat NIET, want die verschilt per machine/database.
    # Zonder deze kolom zou export/import (zie export_history_to_jsonl /
    # import_history_from_jsonl) geen betrouwbare manier hebben om te weten
    # of een rij al eerder is gesynchroniseerd.
    try:
        cursor.execute("ALTER TABLE decisions ADD COLUMN sync_uuid TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE decisions ADD COLUMN goal_id INTEGER")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE decisions ADD COLUMN goal_sync_uuid TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE decisions ADD COLUMN meeting_type TEXT NOT NULL DEFAULT 'strategy'")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    cursor.execute("SELECT id FROM decisions WHERE sync_uuid IS NULL")
    for (row_id,) in cursor.fetchall():
        cursor.execute("UPDATE decisions SET sync_uuid = ? WHERE id = ?", (str(uuid.uuid4()), row_id))
    conn.commit()

    # Tabel 2: Action Approval Queue
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS action_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            proposed_by TEXT NOT NULL,
            action_description TEXT NOT NULL,
            action_detail TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            reviewed_at TEXT,
            action_type TEXT NOT NULL DEFAULT 'shell',
            result_detail TEXT,
            source_decision_id INTEGER,
            source_decision_sync_uuid TEXT,
            source_phase TEXT
        )
    """)

    # Migratie voor bestaande databases die dateren van vóór result_detail:
    # slaat het resultaat van EXECUTIE op (stdout, screenshot_path, etc. als
    # JSON) — zonder dit veld verdween een browser-screenshot of shell-output
    # zodra de actie eenmaal in de permanente geschiedenis stond, want die
    # werd alleen ooit teruggegeven aan de aanroeper van execute_action(),
    # nooit opgeslagen.
    try:
        cursor.execute("ALTER TABLE action_queue ADD COLUMN result_detail TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # Migratie voor BESTAANDE databases die dateren van vóór action_type:
    # CREATE TABLE IF NOT EXISTS raakt een reeds bestaande tabel niet aan,
    # dus voegen we de kolom hier apart toe als hij nog ontbreekt. SQLite
    # geeft een OperationalError als de kolom al bestaat — dat vangen we
    # gewoon af, want dan is er niets te doen.
    try:
        cursor.execute("ALTER TABLE action_queue ADD COLUMN action_type TEXT NOT NULL DEFAULT 'shell'")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # kolom bestaat al — prima, niets te migreren

    try:
        cursor.execute("ALTER TABLE action_queue ADD COLUMN sync_uuid TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # Provenance: koppelt iedere actie die uit een voorbereiding komt aan
    # de oorspronkelijke beslissing. source_decision_id is lokaal gemak;
    # source_decision_sync_uuid is de stabiele cross-machine identiteit.
    try:
        cursor.execute("ALTER TABLE action_queue ADD COLUMN source_decision_id INTEGER")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE action_queue ADD COLUMN source_decision_sync_uuid TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE action_queue ADD COLUMN source_phase TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    cursor.execute("SELECT id FROM action_queue WHERE sync_uuid IS NULL")
    for (row_id,) in cursor.fetchall():
        cursor.execute("UPDATE action_queue SET sync_uuid = ? WHERE id = ?", (str(uuid.uuid4()), row_id))
    conn.commit()

    # Tabel 3: expliciete menselijke approval gate voor beslissingen.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS decision_approvals (
            decision_id INTEGER PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'pending',
            reviewed_at TEXT,
            preparation_status TEXT NOT NULL DEFAULT 'not_started',
            prepared_at TEXT,
            preparation_outcome TEXT
        )
    """)

    # Migratie voor databases die de Phase-2 tabel al zonder outcome-kolom
    # hebben gezien.
    try:
        cursor.execute("ALTER TABLE decision_approvals ADD COLUMN preparation_outcome TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # Tabel 4: business-outcome tracking per action. Technische execution
    # (stdout/screenshot/etc.) blijft in action_queue.result_detail; deze tabel
    # meet of het BEDRIJFSDOEL van de actie werkelijk werd bereikt.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS action_outcomes (
            action_id INTEGER PRIMARY KEY,
            action_sync_uuid TEXT NOT NULL UNIQUE,
            expected_outcome TEXT,
            expected_impact TEXT,
            expected_cost_amount REAL,
            currency TEXT,
            outcome_status TEXT NOT NULL DEFAULT 'not_started',
            actual_outcome TEXT,
            actual_impact TEXT,
            actual_cost_amount REAL,
            measured_at TEXT,
            next_recommendation TEXT,
            notes TEXT,
            updated_at TEXT NOT NULL,
            sync_uuid TEXT NOT NULL UNIQUE
        )
    """)

    # Backfill: iedere bestaande actie krijgt een outcome-record. We doen
    # bewust GEEN aannames over oude expected/actual outcomes.
    cursor.execute("""
        SELECT id, sync_uuid
        FROM action_queue
        WHERE sync_uuid IS NOT NULL
    """)
    for action_id, action_sync_uuid in cursor.fetchall():
        cursor.execute(
            """
            INSERT OR IGNORE INTO action_outcomes (
                action_id, action_sync_uuid, outcome_status,
                updated_at, sync_uuid
            ) VALUES (?, ?, 'not_started', ?, ?)
            """,
            (
                action_id,
                action_sync_uuid,
                datetime.datetime.now().isoformat(),
                str(uuid.uuid4()),
            ),
        )
    conn.commit()

    # Tabel 5: gestructureerde resource/capability requests. Dit zijn GEEN
    # executable actions. Approval betekent alleen dat de eigenaar akkoord is
    # om de resource te verschaffen; credentials/secrets zelf worden hier
    # bewust nooit opgeslagen.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resource_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            requested_by TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_name TEXT NOT NULL,
            reason TEXT NOT NULL,
            required_for TEXT,
            amount REAL,
            currency TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            reviewed_at TEXT,
            fulfilled_at TEXT,
            fulfillment_note TEXT,
            source_decision_id INTEGER,
            source_decision_sync_uuid TEXT,
            source_phase TEXT,
            sync_uuid TEXT NOT NULL UNIQUE
        )
    """)
    conn.commit()

    # Tabel 6: immutable-ish treasury ledger. Positive amounts are stored;
    # entry_type determines direction. Reservations live separately so
    # earmarking money never masquerades as real spend.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS treasury_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            entry_type TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            note TEXT,
            source_action_id INTEGER,
            source_action_sync_uuid TEXT,
            source_decision_id INTEGER,
            source_decision_sync_uuid TEXT,
            sync_uuid TEXT NOT NULL UNIQUE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS treasury_reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            released_at TEXT,
            consumed_at TEXT,
            source_action_id INTEGER UNIQUE,
            source_action_sync_uuid TEXT UNIQUE,
            source_decision_id INTEGER,
            source_decision_sync_uuid TEXT,
            sync_uuid TEXT NOT NULL UNIQUE
        )
    """)
    conn.commit()

    # Bestaande beslissingen van vóór Phase 2 krijgen veilig 'pending':
    # niets uit oude historie wordt stilzwijgend als goedgekeurd behandeld.
    cursor.execute("""
        INSERT OR IGNORE INTO decision_approvals (
            decision_id, status, reviewed_at, preparation_status, prepared_at
        )
        SELECT id, 'pending', NULL, 'not_started', NULL
        FROM decisions
    """)
    conn.commit()

    conn.commit()
    conn.close()
    try:
        os.chmod(db_path, 0o600)
    except OSError:
        pass


@contextmanager
def get_connection():
    """
    Context manager voor een veilige SQLite-verbinding.
    Stelt row_factory in op sqlite3.Row voor makkelijke toegang tot kolommen via sleutelnamen.
    """
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ===================================================================
# COMPANY GOALS / MISSIONS
# ===================================================================

def _normalize_goal_target_date(target_date: str | None) -> str | None:
    if target_date is None or not target_date.strip():
        return None
    value = target_date.strip()
    try:
        parsed = datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("target_date must use YYYY-MM-DD format") from exc
    return parsed.isoformat()


def create_company_goal(
    title: str,
    description: str,
    success_criteria: str,
    priority: str = "medium",
    target_date: str | None = None,
    status: str = "draft",
) -> int:
    title = title.strip()
    description = description.strip()
    success_criteria = success_criteria.strip()
    if not title or not description or not success_criteria:
        raise ValueError("title, description, and success_criteria are required")
    if priority not in VALID_GOAL_PRIORITIES:
        raise ValueError(f"Unsupported goal priority: {priority}")
    if status not in {"draft", "active"}:
        raise ValueError("New goals may only start as draft or active")
    target_date = _normalize_goal_target_date(target_date)
    _reject_secret_like_text(title, description, success_criteria)
    now = datetime.datetime.now().isoformat()

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO company_goals (
                created_at, updated_at, title, description, success_criteria,
                priority, target_date, status, sync_uuid
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now, now, title, description, success_criteria, priority,
                target_date, status, str(uuid.uuid4()),
            ),
        )
        goal_id = cursor.lastrowid
        conn.commit()
        return goal_id


def get_company_goal(goal_id: int) -> dict | None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM company_goals WHERE id = ?", (goal_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_company_goals(
    *,
    statuses: tuple[str, ...] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    if statuses and any(status not in VALID_GOAL_STATUSES for status in statuses):
        raise ValueError("Unsupported goal status filter")
    with get_connection() as conn:
        cursor = conn.cursor()
        params: list = []
        where = ""
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            where = f"WHERE g.status IN ({placeholders})"
            params.extend(statuses)
        cursor.execute(
            f"""
            SELECT g.*,
                   (SELECT COUNT(*) FROM decisions d WHERE d.goal_id = g.id) AS linked_decision_count,
                   (
                       SELECT COUNT(*)
                       FROM action_queue q
                       JOIN decisions d ON d.id = q.source_decision_id
                       WHERE d.goal_id = g.id
                   ) AS linked_action_count,
                   (
                       SELECT COUNT(*)
                       FROM action_outcomes o
                       JOIN action_queue q ON q.id = o.action_id
                       JOIN decisions d ON d.id = q.source_decision_id
                       WHERE d.goal_id = g.id
                         AND o.outcome_status IN ('succeeded','failed','partial','inconclusive')
                   ) AS measured_outcome_count
            FROM company_goals g
            {where}
            ORDER BY
                CASE g.priority
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    ELSE 4
                END,
                g.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]


def update_company_goal(
    goal_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
    success_criteria: str | None = None,
    priority: str | None = None,
    target_date: str | None = None,
) -> dict | None:
    goal = get_company_goal(goal_id)
    if goal is None:
        return None
    if goal["status"] in {"completed", "abandoned"}:
        raise ValueError("Terminal goals cannot be edited")
    updates: dict[str, object] = {}
    for key, value in {
        "title": title,
        "description": description,
        "success_criteria": success_criteria,
    }.items():
        if value is not None:
            clean = value.strip()
            if not clean:
                raise ValueError(f"{key} cannot be empty")
            _reject_secret_like_text(clean)
            updates[key] = clean
    if priority is not None:
        if priority not in VALID_GOAL_PRIORITIES:
            raise ValueError(f"Unsupported goal priority: {priority}")
        updates["priority"] = priority
    if target_date is not None:
        updates["target_date"] = _normalize_goal_target_date(target_date)
    if not updates:
        return goal
    updates["updated_at"] = datetime.datetime.now().isoformat()

    with get_connection() as conn:
        cursor = conn.cursor()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        cursor.execute(
            f"UPDATE company_goals SET {assignments} WHERE id = ?",
            (*updates.values(), goal_id),
        )
        conn.commit()
    return get_company_goal(goal_id)


def transition_company_goal_status(
    goal_id: int,
    new_status: str,
    completion_note: str | None = None,
) -> dict | None:
    if new_status not in VALID_GOAL_STATUSES:
        raise ValueError(f"Unsupported goal status: {new_status}")
    goal = get_company_goal(goal_id)
    if goal is None:
        return None

    allowed = {
        "draft": {"active", "abandoned"},
        "active": {"paused", "completed", "abandoned"},
        "paused": {"active", "completed", "abandoned"},
        "completed": set(),
        "abandoned": set(),
    }
    if new_status not in allowed[goal["status"]]:
        raise ValueError(
            f"Goal cannot transition from '{goal['status']}' to '{new_status}'"
        )
    if new_status in {"completed", "abandoned"}:
        if not (completion_note or "").strip():
            raise ValueError("completion_note is required for completed/abandoned goals")
        _reject_secret_like_text(completion_note)
    elif completion_note is not None:
        raise ValueError("completion_note is only valid for completed/abandoned goals")

    now = datetime.datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        if new_status in {"completed", "abandoned"}:
            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM action_queue q
                JOIN decisions d ON d.id = q.source_decision_id
                WHERE d.goal_id = ? AND q.status = 'executing'
                """,
                (goal_id,),
            )
            if int(cursor.fetchone()["count"] or 0) > 0:
                conn.rollback()
                raise ValueError(
                    "Goal cannot be closed while a linked action is executing; "
                    "review the real-world result first"
                )

            # Terminal goal closure cancels unexecuted goal-specific work and
            # releases its reserved capital so treasury cannot remain stranded.
            cursor.execute(
                """
                UPDATE treasury_reservations
                SET status = 'released', released_at = ?
                WHERE status = 'active'
                  AND source_action_id IN (
                      SELECT q.id
                      FROM action_queue q
                      JOIN decisions d ON d.id = q.source_decision_id
                      WHERE d.goal_id = ?
                        AND q.status IN ('pending', 'approved')
                  )
                """,
                (now, goal_id),
            )
            cursor.execute(
                """
                UPDATE action_queue
                SET status = 'rejected', reviewed_at = ?
                WHERE id IN (
                    SELECT q.id
                    FROM action_queue q
                    JOIN decisions d ON d.id = q.source_decision_id
                    WHERE d.goal_id = ?
                      AND q.status IN ('pending', 'approved')
                )
                """,
                (now, goal_id),
            )
            cursor.execute(
                """
                UPDATE resource_requests
                SET status = 'rejected', reviewed_at = ?
                WHERE source_decision_id IN (
                    SELECT id FROM decisions WHERE goal_id = ?
                )
                  AND status IN ('pending', 'approved')
                """,
                (now, goal_id),
            )

        cursor.execute(
            """
            UPDATE company_goals
            SET status = ?, updated_at = ?,
                completed_at = CASE WHEN ? IN ('completed','abandoned') THEN ? ELSE NULL END,
                completion_note = CASE WHEN ? IN ('completed','abandoned') THEN ? ELSE NULL END
            WHERE id = ? AND status = ?
            """,
            (
                new_status, now, new_status, now, new_status,
                completion_note.strip() if completion_note else None,
                goal_id, goal["status"],
            ),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            raise ValueError("Goal status transition race detected")
        conn.commit()
    return get_company_goal(goal_id)


def get_company_goal_lineage(goal_id: int) -> dict | None:
    goal = get_company_goal(goal_id)
    if goal is None:
        return None
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id
            FROM decisions
            WHERE goal_id = ?
            ORDER BY timestamp ASC
            """,
            (goal_id,),
        )
        decision_ids = [row["id"] for row in cursor.fetchall()]

    decision_lineages = [
        lineage
        for decision_id in decision_ids
        if (lineage := get_decision_lineage(decision_id)) is not None
    ]
    outcome_counts = {"succeeded": 0, "failed": 0, "partial": 0, "inconclusive": 0}
    total_spend: dict[str, float] = {}
    for lineage in decision_lineages:
        for action in lineage.get("actions", []):
            status = action.get("outcome_status")
            if status in outcome_counts:
                outcome_counts[status] += 1
        for entry in lineage.get("treasury", {}).get("entries", []):
            if entry.get("entry_type") == "spend":
                code = entry["currency"]
                total_spend[code] = round(
                    total_spend.get(code, 0.0) + float(entry["amount"]),
                    2,
                )

    return {
        "goal": goal,
        "decision_count": len(decision_lineages),
        "outcome_counts": outcome_counts,
        "spend_by_currency": total_spend,
        "decisions": decision_lineages,
    }


# ===================================================================
# STRUCTURED EXECUTIVE MEMORY
# ===================================================================

def create_executive_memory(
    *,
    executive_key: str,
    memory_kind: str,
    lesson: str,
    supporting_evidence: str | None = None,
    confidence: float = 0.7,
    source_goal_id: int | None = None,
    source_decision_id: int | None = None,
    source_action_id: int | None = None,
    fingerprint: str,
) -> tuple[int, bool]:
    executive_key = executive_key.strip().lower().replace(" ", "_")
    lesson = lesson.strip()
    fingerprint = fingerprint.strip()
    if not executive_key or not lesson or not fingerprint:
        raise ValueError("executive_key, lesson, and fingerprint are required")
    if memory_kind not in VALID_EXECUTIVE_MEMORY_KINDS:
        raise ValueError(f"Unsupported executive memory kind: {memory_kind}")
    if not (0.0 <= float(confidence) <= 1.0):
        raise ValueError("confidence must be between 0 and 1")
    if len(lesson) > 2000:
        raise ValueError("Executive memory lesson is too long")
    if supporting_evidence is not None and len(supporting_evidence) > 4000:
        supporting_evidence = supporting_evidence[:4000]
    _reject_secret_like_text(lesson, supporting_evidence)

    source_goal_sync_uuid = None
    source_decision_sync_uuid = None
    source_action_sync_uuid = None

    with get_connection() as conn:
        cursor = conn.cursor()

        if source_goal_id is not None:
            cursor.execute("SELECT sync_uuid FROM company_goals WHERE id = ?", (source_goal_id,))
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Source goal not found")
            source_goal_sync_uuid = row["sync_uuid"]

        if source_decision_id is not None:
            cursor.execute(
                "SELECT sync_uuid, goal_id, goal_sync_uuid FROM decisions WHERE id = ?",
                (source_decision_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Source decision not found")
            source_decision_sync_uuid = row["sync_uuid"]
            if source_goal_id is None and row["goal_id"] is not None:
                source_goal_id = row["goal_id"]
                source_goal_sync_uuid = row["goal_sync_uuid"]

        if source_action_id is not None:
            cursor.execute(
                "SELECT sync_uuid, source_decision_id, source_decision_sync_uuid FROM action_queue WHERE id = ?",
                (source_action_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Source action not found")
            source_action_sync_uuid = row["sync_uuid"]
            if source_decision_id is None and row["source_decision_id"] is not None:
                source_decision_id = row["source_decision_id"]
                source_decision_sync_uuid = row["source_decision_sync_uuid"]
                cursor.execute(
                    "SELECT goal_id, goal_sync_uuid FROM decisions WHERE id = ?",
                    (source_decision_id,),
                )
                drow = cursor.fetchone()
                if drow and source_goal_id is None:
                    source_goal_id = drow["goal_id"]
                    source_goal_sync_uuid = drow["goal_sync_uuid"]

        cursor.execute(
            "SELECT id FROM executive_memories WHERE fingerprint = ?",
            (fingerprint,),
        )
        existing = cursor.fetchone()
        if existing:
            now = datetime.datetime.now().isoformat()
            cursor.execute(
                """
                UPDATE executive_memories
                SET lesson = ?, supporting_evidence = ?, confidence = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    lesson,
                    supporting_evidence.strip() if supporting_evidence else None,
                    float(confidence),
                    now,
                    existing["id"],
                ),
            )
            conn.commit()
            return int(existing["id"]), False

        now = datetime.datetime.now().isoformat()
        cursor.execute(
            """
            INSERT INTO executive_memories (
                created_at, updated_at, executive_key, memory_kind, lesson,
                supporting_evidence, confidence, is_active,
                source_goal_id, source_goal_sync_uuid,
                source_decision_id, source_decision_sync_uuid,
                source_action_id, source_action_sync_uuid,
                fingerprint, sync_uuid
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now, now, executive_key, memory_kind, lesson,
                supporting_evidence.strip() if supporting_evidence else None,
                float(confidence),
                source_goal_id, source_goal_sync_uuid,
                source_decision_id, source_decision_sync_uuid,
                source_action_id, source_action_sync_uuid,
                fingerprint, str(uuid.uuid4()),
            ),
        )
        memory_id = cursor.lastrowid
        conn.commit()
        return int(memory_id), True


def get_executive_memories(
    executive_key: str,
    *,
    active_only: bool = True,
    limit: int = 8,
    goal_id: int | None = None,
) -> list[dict]:
    executive_key = executive_key.strip()
    if not executive_key:
        return []
    clauses = ["executive_key = ?"]
    params: list = [executive_key]
    if active_only:
        clauses.append("is_active = 1")
    if goal_id is not None:
        clauses.append("(source_goal_id = ? OR source_goal_id IS NULL)")
        params.append(goal_id)
    where = " AND ".join(clauses)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT *
            FROM executive_memories
            WHERE {where}
            ORDER BY confidence DESC, created_at DESC
            LIMIT ?
            """,
            (*params, limit),
        )
        return [dict(row) for row in cursor.fetchall()]


def set_executive_memory_active(memory_id: int, is_active: bool) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE executive_memories
            SET is_active = ?, updated_at = ?
            WHERE id = ?
            """,
            (1 if is_active else 0, datetime.datetime.now().isoformat(), memory_id),
        )
        conn.commit()
        return cursor.rowcount == 1


def create_decision_memories(decision_id: int, approval_status: str) -> list[int]:
    decision = get_decision_by_id(decision_id)
    if decision is None:
        return []
    if approval_status not in {"approved", "rejected"}:
        raise ValueError("Decision memory requires approved or rejected status")

    kind = "decision_approved" if approval_status == "approved" else "decision_rejected"
    lesson = (
        f"Owner {approval_status} strategic direction '{decision['topic']}'. "
        "Treat this as historical governance context, not proof that the same direction "
        "is correct for a future situation."
    )
    evidence = (
        f"Decision #{decision_id}; topic={decision['topic']}; "
        f"owner_status={approval_status}; recommendation={decision['decision_outcome']}"
    )

    created_ids: list[int] = []
    for executive_key in [
        key.strip().lower().replace(" ", "_")
        for key in (decision.get("agents_involved") or "").split(",")
        if key.strip()
    ]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE executive_memories
                SET is_active = 0, updated_at = ?
                WHERE executive_key = ?
                  AND source_decision_id = ?
                  AND memory_kind IN ('decision_approved', 'decision_rejected')
                  AND memory_kind != ?
                  AND is_active = 1
                """,
                (datetime.datetime.now().isoformat(), executive_key, decision_id, kind),
            )
            conn.commit()

        memory_id, created = create_executive_memory(
            executive_key=executive_key,
            memory_kind=kind,
            lesson=lesson,
            supporting_evidence=evidence,
            confidence=0.8,
            source_goal_id=decision.get("goal_id"),
            source_decision_id=decision_id,
            fingerprint=f"decision:{decision['sync_uuid']}:{approval_status}:{executive_key}",
        )
        if created:
            created_ids.append(memory_id)
    return created_ids


def create_action_outcome_memories(action_id: int) -> list[int]:
    action = get_action_by_id(action_id)
    if action is None:
        return []
    outcome_status = action.get("outcome_status")
    if outcome_status not in {"succeeded", "failed", "partial", "inconclusive"}:
        return []
    source_decision_id = action.get("source_decision_id")
    if source_decision_id is None:
        return []
    decision = get_decision_by_id(source_decision_id)
    if decision is None:
        return []

    kind = f"outcome_{outcome_status}"
    lesson = (
        f"Measured action '{action.get('action_description')}' had business outcome "
        f"'{outcome_status}'. Reuse only the lesson, not the old conclusion: compare "
        "current evidence before applying it again."
    )
    evidence_parts = [
        f"Action #{action_id}",
        f"expected_outcome={action.get('expected_outcome') or 'unknown'}",
        f"expected_impact={action.get('expected_impact') or 'unknown'}",
        f"actual_outcome={action.get('actual_outcome') or 'unknown'}",
        f"actual_impact={action.get('actual_impact') or 'unknown'}",
        f"next_recommendation={action.get('next_recommendation') or 'none'}",
    ]
    evidence = "; ".join(evidence_parts)
    confidence = {
        "succeeded": 0.9,
        "failed": 0.9,
        "partial": 0.75,
        "inconclusive": 0.5,
    }[outcome_status]

    created_ids: list[int] = []
    roles = [
        key.strip().lower().replace(" ", "_")
        for key in (decision.get("agents_involved") or "").split(",")
        if key.strip()
    ]
    for executive_key in roles:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE executive_memories
                SET is_active = 0, updated_at = ?
                WHERE executive_key = ?
                  AND source_action_id = ?
                  AND memory_kind LIKE 'outcome_%'
                  AND memory_kind != ?
                  AND is_active = 1
                """,
                (datetime.datetime.now().isoformat(), executive_key, action_id, kind),
            )
            conn.commit()

        memory_id, created = create_executive_memory(
            executive_key=executive_key,
            memory_kind=kind,
            lesson=lesson,
            supporting_evidence=evidence,
            confidence=confidence,
            source_goal_id=decision.get("goal_id"),
            source_decision_id=source_decision_id,
            source_action_id=action_id,
            fingerprint=(
                f"action:{action['sync_uuid']}:outcome:{outcome_status}:{executive_key}"
            ),
        )
        if created:
            created_ids.append(memory_id)
    return created_ids


# ===================================================================
# AUTONOMOUS FOLLOW-UP EVENTS
# ===================================================================

def create_followup_event(
    *,
    event_type: str,
    severity: str,
    reason: str,
    fingerprint: str,
    goal_id: int | None = None,
    source_action_id: int | None = None,
    source_decision_id: int | None = None,
) -> tuple[int, bool]:
    if event_type not in VALID_FOLLOWUP_EVENT_TYPES:
        raise ValueError(f"Unsupported follow-up event type: {event_type}")
    if severity not in VALID_FOLLOWUP_SEVERITIES:
        raise ValueError(f"Unsupported follow-up severity: {severity}")
    reason = (reason or "").strip()
    fingerprint = (fingerprint or "").strip()
    if not reason or not fingerprint:
        raise ValueError("Follow-up reason and fingerprint are required")
    _reject_secret_like_text(reason, fingerprint)

    goal_sync_uuid = None
    source_action_sync_uuid = None
    source_decision_sync_uuid = None
    with get_connection() as conn:
        cursor = conn.cursor()

        if goal_id is not None:
            cursor.execute("SELECT sync_uuid FROM company_goals WHERE id = ?", (goal_id,))
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Goal not found")
            goal_sync_uuid = row["sync_uuid"]

        if source_action_id is not None:
            cursor.execute(
                "SELECT sync_uuid, source_decision_id, source_decision_sync_uuid FROM action_queue WHERE id = ?",
                (source_action_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Source action not found")
            source_action_sync_uuid = row["sync_uuid"]
            if source_decision_id is None:
                source_decision_id = row["source_decision_id"]
                source_decision_sync_uuid = row["source_decision_sync_uuid"]

        if source_decision_id is not None and source_decision_sync_uuid is None:
            cursor.execute("SELECT sync_uuid FROM decisions WHERE id = ?", (source_decision_id,))
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Source decision not found")
            source_decision_sync_uuid = row["sync_uuid"]

        cursor.execute(
            "SELECT id FROM followup_events WHERE fingerprint = ?",
            (fingerprint,),
        )
        existing = cursor.fetchone()
        if existing:
            return int(existing["id"]), False

        now = datetime.datetime.now().isoformat()
        cursor.execute(
            """
            INSERT INTO followup_events (
                created_at, updated_at, event_type, status, severity, reason,
                fingerprint, goal_id, goal_sync_uuid,
                source_action_id, source_action_sync_uuid,
                source_decision_id, source_decision_sync_uuid, sync_uuid
            ) VALUES (?, ?, ?, 'open', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now, now, event_type, severity, reason, fingerprint,
                goal_id, goal_sync_uuid,
                source_action_id, source_action_sync_uuid,
                source_decision_id, source_decision_sync_uuid,
                str(uuid.uuid4()),
            ),
        )
        event_id = cursor.lastrowid
        conn.commit()
        return int(event_id), True


def get_followup_event(event_id: int) -> dict | None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT f.*, g.title AS goal_title,
                   sd.topic AS source_decision_topic,
                   gd.topic AS generated_decision_topic
            FROM followup_events f
            LEFT JOIN company_goals g ON g.id = f.goal_id
            LEFT JOIN decisions sd ON sd.id = f.source_decision_id
            LEFT JOIN decisions gd ON gd.id = f.generated_decision_id
            WHERE f.id = ?
            """,
            (event_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_followup_events(
    *,
    statuses: tuple[str, ...] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    if statuses and any(status not in VALID_FOLLOWUP_STATUSES for status in statuses):
        raise ValueError("Unsupported follow-up status filter")
    with get_connection() as conn:
        cursor = conn.cursor()
        params: list = []
        where = ""
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            where = f"WHERE f.status IN ({placeholders})"
            params.extend(statuses)
        cursor.execute(
            f"""
            SELECT f.*, g.title AS goal_title,
                   sd.topic AS source_decision_topic,
                   gd.topic AS generated_decision_topic
            FROM followup_events f
            LEFT JOIN company_goals g ON g.id = f.goal_id
            LEFT JOIN decisions sd ON sd.id = f.source_decision_id
            LEFT JOIN decisions gd ON gd.id = f.generated_decision_id
            {where}
            ORDER BY
                CASE f.severity
                    WHEN 'critical' THEN 1
                    WHEN 'attention' THEN 2
                    ELSE 3
                END,
                f.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]


def transition_followup_event_status(
    event_id: int,
    new_status: str,
    allowed_from: tuple[str, ...] = ("open",),
) -> bool:
    if new_status not in VALID_FOLLOWUP_STATUSES:
        raise ValueError(f"Unsupported follow-up status: {new_status}")
    if not allowed_from or any(s not in VALID_FOLLOWUP_STATUSES for s in allowed_from):
        raise ValueError("Invalid follow-up allowed_from states")
    now = datetime.datetime.now().isoformat()
    placeholders = ", ".join("?" for _ in allowed_from)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            UPDATE followup_events
            SET status = ?, updated_at = ?,
                resolved_at = CASE WHEN ? IN ('resolved','dismissed') THEN ? ELSE resolved_at END
            WHERE id = ? AND status IN ({placeholders})
            """,
            (new_status, now, new_status, now, event_id, *allowed_from),
        )
        conn.commit()
        return cursor.rowcount == 1


def link_followup_generated_decision(event_id: int, decision_id: int) -> bool:
    decision = get_decision_by_id(decision_id)
    if decision is None:
        raise ValueError("Generated decision not found")
    now = datetime.datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE followup_events
            SET generated_decision_id = ?, generated_decision_sync_uuid = ?, updated_at = ?
            WHERE id = ? AND status = 'open' AND generated_decision_id IS NULL
            """,
            (decision_id, decision["sync_uuid"], now, event_id),
        )
        conn.commit()
        return cursor.rowcount == 1


# ===================================================================
# FUNCTIES VOOR BESTUURSBESLUITEN (DECISIONS)
# ===================================================================

def log_decision(
    topic: str,
    agents_involved: list[str],
    task_description: str,
    decision_outcome: str,
    sandbox_mode: bool = True,
    goal_id: int | None = None,
    meeting_type: str = "strategy",
) -> int:
    """
    Slaat een nieuwe beslissing op in de database en geeft de nieuwe rij-ID terug.
    """
    timestamp = datetime.datetime.now().isoformat()
    agents_str = ",".join(agents_involved)
    sandbox_flag = 1 if sandbox_mode else 0
    new_sync_uuid = str(uuid.uuid4())
    goal_sync_uuid = None
    if meeting_type not in VALID_MEETING_TYPES:
        raise ValueError(f"Unsupported meeting type: {meeting_type}")

    with get_connection() as conn:
        cursor = conn.cursor()
        if goal_id is not None:
            cursor.execute(
                "SELECT sync_uuid, status FROM company_goals WHERE id = ?",
                (goal_id,),
            )
            goal = cursor.fetchone()
            if goal is None:
                raise ValueError("Goal not found")
            if goal["status"] != "active":
                raise ValueError(
                    f"Decisions may only be linked to active goals; current goal status is '{goal['status']}'"
                )
            goal_sync_uuid = goal["sync_uuid"]

        cursor.execute("""
            INSERT INTO decisions (
                timestamp, topic, agents_involved, task_description, decision_outcome,
                sandbox_mode, sync_uuid, goal_id, goal_sync_uuid, meeting_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp, topic, agents_str, task_description, decision_outcome,
            sandbox_flag, new_sync_uuid, goal_id, goal_sync_uuid, meeting_type,
        ))
        
        decision_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT OR IGNORE INTO decision_approvals (
                decision_id, status, reviewed_at, preparation_status, prepared_at
            ) VALUES (?, 'pending', NULL, 'not_started', NULL)
            """,
            (decision_id,),
        )
        conn.commit()
        return decision_id


def get_decision_by_id(decision_id: int) -> dict | None:
    """Haalt één beslissing op, inclusief approval/preparation status."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                d.id, d.timestamp, d.topic, d.agents_involved,
                d.task_description, d.decision_outcome, d.sandbox_mode,
                d.sync_uuid, d.goal_id, d.goal_sync_uuid, d.meeting_type,
                g.title AS goal_title, g.status AS goal_status,
                COALESCE(a.status, 'pending') AS approval_status,
                a.reviewed_at AS approval_reviewed_at,
                COALESCE(a.preparation_status, 'not_started') AS preparation_status,
                a.prepared_at,
                a.preparation_outcome,
                (
                    SELECT COUNT(*)
                    FROM action_queue q
                    WHERE q.source_decision_id = d.id
                ) AS linked_action_count,
                (
                    SELECT COUNT(*)
                    FROM resource_requests r
                    WHERE r.source_decision_id = d.id
                ) AS linked_resource_request_count
            FROM decisions d
            LEFT JOIN decision_approvals a ON a.decision_id = d.id
            LEFT JOIN company_goals g ON g.id = d.goal_id
            WHERE d.id = ?
            """,
            (decision_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def transition_decision_approval(
    decision_id: int,
    new_status: str,
    allowed_from: tuple[str, ...],
) -> bool:
    """Atomische menselijke approval/reject overgang voor een beslissing."""
    if new_status not in VALID_DECISION_APPROVAL_STATUSES:
        raise ValueError(f"Unsupported decision approval status: {new_status}")
    if not allowed_from or any(s not in VALID_DECISION_APPROVAL_STATUSES for s in allowed_from):
        raise ValueError(f"Invalid decision allowed_from statuses: {allowed_from}")

    now = datetime.datetime.now().isoformat()
    placeholders = ", ".join("?" for _ in allowed_from)
    params = (new_status, now, decision_id, *allowed_from)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            UPDATE decision_approvals
            SET status = ?, reviewed_at = ?
            WHERE decision_id = ?
              AND status IN ({placeholders})
              AND preparation_status NOT IN ('in_progress', 'completed')
            """,
            params,
        )
        conn.commit()
        return cursor.rowcount == 1


def claim_decision_for_preparation(decision_id: int) -> bool:
    """Reserveert een goedgekeurde beslissing atomair voor één preparation-run."""
    now = datetime.datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE decision_approvals
            SET preparation_status = 'in_progress', prepared_at = ?
            WHERE decision_id = ?
              AND status = 'approved'
              AND preparation_status IN ('not_started', 'failed')
            """,
            (now, decision_id),
        )
        conn.commit()
        return cursor.rowcount == 1


def finish_decision_preparation(
    decision_id: int,
    success: bool,
    outcome: str | None = None,
) -> bool:
    """Zet preparation atomair naar completed/failed en bewaart het plan."""
    target = "completed" if success else "failed"
    now = datetime.datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE decision_approvals
            SET preparation_status = ?, prepared_at = ?, preparation_outcome = ?
            WHERE decision_id = ? AND preparation_status = 'in_progress'
            """,
            (target, now, outcome, decision_id),
        )
        conn.commit()
        return cursor.rowcount == 1


def has_daily_research_attempt_on(date_value: datetime.date) -> bool:
    """
    Controleert rechtstreeks in SQL of er op deze kalenderdatum al een daily
    research poging (succes OF failure) is gelogd. Dit mag niet afhangen van
    een willekeurige 'laatste N beslissingen'-window: veel ad-hoc beslissingen
    later op dezelfde dag mogen de scheduler niet laten vergeten dat de run
    al plaatsvond.
    """
    date_prefix = date_value.isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 1
            FROM decisions
            WHERE topic LIKE 'Daily Research%'
              AND substr(timestamp, 1, 10) = ?
            LIMIT 1
            """,
            (date_prefix,),
        )
        return cursor.fetchone() is not None


def get_recent_decisions(limit: int = 10, offset: int = 0) -> list[dict]:
    """
    Haalt beslissingen op, gesorteerd op datum (nieuwste eerst), met
    paginering via offset — nodig zodra de geschiedenis weken/maanden aan
    data bevat en een dashboard niet alles in één keer hoeft te laden.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                d.id, d.timestamp, d.topic, d.agents_involved, d.task_description,
                d.decision_outcome, d.sandbox_mode, d.sync_uuid,
                d.goal_id, d.goal_sync_uuid, d.meeting_type,
                g.title AS goal_title, g.status AS goal_status,
                COALESCE(a.status, 'pending') AS approval_status,
                a.reviewed_at AS approval_reviewed_at,
                COALESCE(a.preparation_status, 'not_started') AS preparation_status,
                a.prepared_at,
                a.preparation_outcome,
                (
                    SELECT COUNT(*)
                    FROM action_queue q
                    WHERE q.source_decision_id = d.id
                ) AS linked_action_count,
                (
                    SELECT COUNT(*)
                    FROM resource_requests r
                    WHERE r.source_decision_id = d.id
                ) AS linked_resource_request_count
            FROM decisions d
            LEFT JOIN decision_approvals a ON a.decision_id = d.id
            LEFT JOIN company_goals g ON g.id = d.goal_id
            ORDER BY d.timestamp DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


# ===================================================================
# ACTION PROVENANCE CONTEXT
# ===================================================================

@contextmanager
def action_provenance_scope(
    decision_id: int,
    decision_sync_uuid: str,
    phase: str = "preparation",
    allowed_browser_urls: set[str] | None = None,
):
    """
    Process-wide provenance scope for one serialized CrewAI execution.

    CrewAI may invoke tools from an internal worker thread, so thread-local
    state is not reliable here. Heavy executive meetings are already serialized
    by workflows.execution_lock.EXECUTION_LOCK, which guarantees only one
    tool-capable meeting can own this scope at a time.
    """
    global _ACTION_PROVENANCE_CONTEXT

    scoped_value = {
        "decision_id": decision_id,
        "decision_sync_uuid": decision_sync_uuid,
        "phase": phase,
        "created_action_ids": [],
        "created_resource_request_ids": [],
        "allowed_browser_urls": {
            str(url).strip()
            for url in (allowed_browser_urls or set())
            if str(url).strip()
        },
    }

    with _ACTION_PROVENANCE_LOCK:
        if _ACTION_PROVENANCE_CONTEXT is not None:
            raise RuntimeError("Action provenance scope is already active")
        _ACTION_PROVENANCE_CONTEXT = scoped_value

    try:
        yield scoped_value
    finally:
        with _ACTION_PROVENANCE_LOCK:
            _ACTION_PROVENANCE_CONTEXT = None


def _current_action_provenance() -> dict | None:
    with _ACTION_PROVENANCE_LOCK:
        return _ACTION_PROVENANCE_CONTEXT


# ===================================================================
# STRUCTURED RESOURCE / CAPABILITY REQUESTS
# ===================================================================

def browser_url_allowed_by_provenance(url: str) -> bool:
    """
    Preparation browser actions may only target URLs explicitly supplied in
    trusted preparation context. Independent/manual proposals without an
    active provenance scope keep their existing human-review behavior.
    """
    provenance = _current_action_provenance()
    if provenance is None:
        return True
    allowed = provenance.get("allowed_browser_urls")
    if allowed is None:
        return True
    candidate = (url or "").strip()
    return candidate in allowed


def propose_resource_request(
    requested_by: str,
    resource_type: str,
    resource_name: str,
    reason: str,
    required_for: str | None = None,
    amount: float | None = None,
    currency: str | None = None,
) -> int:
    if resource_type not in VALID_RESOURCE_TYPES:
        raise ValueError(f"Unsupported resource_type: {resource_type}")
    _reject_secret_like_text(resource_name, reason, required_for)
    if not resource_name.strip() or not reason.strip():
        raise ValueError("resource_name and reason are required")
    if amount is not None:
        if amount < 0:
            raise ValueError("amount cannot be negative")
        if resource_type != "budget":
            raise ValueError("amount is only allowed for budget requests")
        if not currency:
            raise ValueError("currency is required for budget requests with an amount")
    if currency is not None:
        currency = currency.strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("currency must be a 3-letter code such as EUR or USD")

    provenance = _current_action_provenance()
    timestamp = datetime.datetime.now().isoformat()
    new_sync_uuid = str(uuid.uuid4())

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO resource_requests (
                timestamp, requested_by, resource_type, resource_name,
                reason, required_for, amount, currency, status,
                source_decision_id, source_decision_sync_uuid, source_phase,
                sync_uuid
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
            """,
            (
                timestamp, requested_by, resource_type, resource_name,
                reason, required_for, amount, currency,
                provenance.get("decision_id") if provenance else None,
                provenance.get("decision_sync_uuid") if provenance else None,
                provenance.get("phase") if provenance else None,
                new_sync_uuid,
            ),
        )
        request_id = cursor.lastrowid
        conn.commit()

    if provenance is not None:
        with _ACTION_PROVENANCE_LOCK:
            provenance.setdefault("created_resource_request_ids", []).append(request_id)
    return request_id


def get_resource_request_by_id(request_id: int) -> dict | None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT r.*, d.topic AS source_decision_topic,
                   d.goal_id AS source_goal_id, g.title AS source_goal_title
            FROM resource_requests r
            LEFT JOIN decisions d ON d.id = r.source_decision_id
            LEFT JOIN company_goals g ON g.id = d.goal_id
            WHERE r.id = ?
            """,
            (request_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_resource_requests(
    *,
    statuses: tuple[str, ...] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    with get_connection() as conn:
        cursor = conn.cursor()
        if statuses:
            if any(status not in VALID_RESOURCE_REQUEST_STATUSES for status in statuses):
                raise ValueError("Unsupported resource request status")
            placeholders = ", ".join("?" for _ in statuses)
            cursor.execute(
                f"""
                SELECT r.*, d.topic AS source_decision_topic,
                       d.goal_id AS source_goal_id, g.title AS source_goal_title
                FROM resource_requests r
                LEFT JOIN decisions d ON d.id = r.source_decision_id
                LEFT JOIN company_goals g ON g.id = d.goal_id
                WHERE r.status IN ({placeholders})
                ORDER BY r.timestamp DESC
                LIMIT ? OFFSET ?
                """,
                (*statuses, limit, offset),
            )
        else:
            cursor.execute(
                """
                SELECT r.*, d.topic AS source_decision_topic,
                       d.goal_id AS source_goal_id, g.title AS source_goal_title
                FROM resource_requests r
                LEFT JOIN decisions d ON d.id = r.source_decision_id
                LEFT JOIN company_goals g ON g.id = d.goal_id
                ORDER BY r.timestamp DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
        return [dict(row) for row in cursor.fetchall()]


def get_resource_requests_for_decision(decision_id: int) -> list[dict]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT r.*, d.topic AS source_decision_topic,
                   d.goal_id AS source_goal_id, g.title AS source_goal_title
            FROM resource_requests r
            LEFT JOIN decisions d ON d.id = r.source_decision_id
            LEFT JOIN company_goals g ON g.id = d.goal_id
            WHERE r.source_decision_id = ?
            ORDER BY r.timestamp ASC
            """,
            (decision_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def transition_resource_request_status(
    request_id: int,
    new_status: str,
    allowed_from: tuple[str, ...],
    fulfillment_note: str | None = None,
) -> bool:
    if new_status not in VALID_RESOURCE_REQUEST_STATUSES:
        raise ValueError(f"Unsupported resource request status: {new_status}")
    if not allowed_from or any(s not in VALID_RESOURCE_REQUEST_STATUSES for s in allowed_from):
        raise ValueError(f"Invalid resource request allowed_from: {allowed_from}")
    if new_status == "fulfilled" and not (fulfillment_note or "").strip():
        raise ValueError("fulfillment_note is required when marking a request fulfilled")
    if fulfillment_note is not None:
        _reject_secret_like_text(fulfillment_note)

    now = datetime.datetime.now().isoformat()
    placeholders = ", ".join("?" for _ in allowed_from)
    with get_connection() as conn:
        cursor = conn.cursor()
        if new_status == "fulfilled":
            cursor.execute(
                f"""
                UPDATE resource_requests
                SET status = ?, reviewed_at = COALESCE(reviewed_at, ?),
                    fulfilled_at = ?, fulfillment_note = ?
                WHERE id = ? AND status IN ({placeholders})
                """,
                (new_status, now, now, fulfillment_note.strip(), request_id, *allowed_from),
            )
        else:
            cursor.execute(
                f"""
                UPDATE resource_requests
                SET status = ?, reviewed_at = ?
                WHERE id = ? AND status IN ({placeholders})
                """,
                (new_status, now, request_id, *allowed_from),
            )
        conn.commit()
        return cursor.rowcount == 1


# ===================================================================
# COMPANY TREASURY / BUDGET
# ===================================================================

def _normalize_currency(currency: str) -> str:
    value = (currency or "").strip().upper()
    if len(value) != 3 or not value.isalpha():
        raise ValueError("currency must be a 3-letter code such as EUR or USD")
    return value


def add_treasury_entry(
    entry_type: str,
    amount: float,
    currency: str,
    note: str | None = None,
    *,
    source_action_id: int | None = None,
    source_action_sync_uuid: str | None = None,
    source_decision_id: int | None = None,
    source_decision_sync_uuid: str | None = None,
) -> int:
    if entry_type not in VALID_TREASURY_ENTRY_TYPES:
        raise ValueError(f"Unsupported treasury entry type: {entry_type}")
    if amount <= 0:
        raise ValueError("Treasury amount must be greater than zero")
    currency = _normalize_currency(currency)
    if note:
        _reject_secret_like_text(note)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO treasury_entries (
                timestamp, entry_type, amount, currency, note,
                source_action_id, source_action_sync_uuid,
                source_decision_id, source_decision_sync_uuid, sync_uuid
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.datetime.now().isoformat(), entry_type, amount, currency, note,
                source_action_id, source_action_sync_uuid,
                source_decision_id, source_decision_sync_uuid, str(uuid.uuid4()),
            ),
        )
        entry_id = cursor.lastrowid
        conn.commit()
        return entry_id


def get_treasury_summary(currency: str | None = None) -> dict:
    with get_connection() as conn:
        cursor = conn.cursor()
        params: tuple = ()
        where = ""
        if currency:
            currency = _normalize_currency(currency)
            where = "WHERE currency = ?"
            params = (currency,)

        cursor.execute(
            f"""
            SELECT currency,
                   SUM(CASE
                       WHEN entry_type IN ('funding', 'refund') THEN amount
                       WHEN entry_type = 'spend' THEN -amount
                       ELSE 0
                   END) AS cash_balance
            FROM treasury_entries
            {where}
            GROUP BY currency
            """,
            params,
        )
        balances = {row["currency"]: float(row["cash_balance"] or 0) for row in cursor.fetchall()}

        reservation_where = (
            "WHERE currency = ? AND status = 'active'"
            if currency
            else "WHERE status = 'active'"
        )
        cursor.execute(
            f"""
            SELECT currency, SUM(amount) AS reserved
            FROM treasury_reservations
            {reservation_where}
            GROUP BY currency
            """,
            params,
        )
        reserved = {row["currency"]: float(row["reserved"] or 0) for row in cursor.fetchall()}

        currencies = sorted(set(balances) | set(reserved))
        by_currency = {}
        for code in currencies:
            cash = balances.get(code, 0.0)
            held = reserved.get(code, 0.0)
            by_currency[code] = {
                "cash_balance": round(cash, 2),
                "reserved": round(held, 2),
                "available": round(cash - held, 2),
            }

        return {"currencies": by_currency}


def get_treasury_history(limit: int = 50, offset: int = 0) -> list[dict]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT e.*, d.topic AS source_decision_topic,
                   d.goal_id AS source_goal_id, g.title AS source_goal_title
            FROM treasury_entries e
            LEFT JOIN decisions d ON d.id = e.source_decision_id
            LEFT JOIN company_goals g ON g.id = d.goal_id
            ORDER BY e.timestamp DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_treasury_reservation_for_action(action_id: int) -> dict | None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM treasury_reservations WHERE source_action_id = ?",
            (action_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def reserve_action_budget(action_id: int) -> dict | None:
    action = get_action_by_id(action_id)
    if action is None:
        raise ValueError("Action not found")
    amount = action.get("expected_cost_amount")
    currency = action.get("currency")
    if amount is None or amount == 0:
        return None
    if amount < 0 or not currency:
        raise ValueError("Paid actions require a non-negative expected cost and currency")
    currency = _normalize_currency(currency)

    existing = get_treasury_reservation_for_action(action_id)
    if existing:
        if existing["status"] == "active":
            return existing
        raise ValueError("Action already has a terminal treasury reservation")

    summary = get_treasury_summary(currency)["currencies"].get(
        currency,
        {"cash_balance": 0.0, "reserved": 0.0, "available": 0.0},
    )
    if summary["available"] + 1e-9 < float(amount):
        raise ValueError(
            f"Insufficient available treasury funds: need {amount:.2f} {currency}, "
            f"available {summary['available']:.2f} {currency}"
        )

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO treasury_reservations (
                timestamp, amount, currency, status,
                source_action_id, source_action_sync_uuid,
                source_decision_id, source_decision_sync_uuid, sync_uuid
            ) VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?)
            """,
            (
                datetime.datetime.now().isoformat(), amount, currency,
                action_id, action.get("sync_uuid"),
                action.get("source_decision_id"), action.get("source_decision_sync_uuid"),
                str(uuid.uuid4()),
            ),
        )
        reservation_id = cursor.lastrowid
        conn.commit()
    return get_treasury_reservation_for_action(action_id)


def approve_action_with_treasury(action_id: int) -> dict:
    """
    Atomically approves a pending action and, when an expected monetary cost
    exists, reserves that amount from the matching currency treasury.
    """
    now = datetime.datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            """
            SELECT q.id, q.status, q.sync_uuid, q.source_decision_id,
                   q.source_decision_sync_uuid,
                   o.expected_cost_amount, o.currency
            FROM action_queue q
            LEFT JOIN action_outcomes o ON o.action_id = q.id
            WHERE q.id = ?
            """,
            (action_id,),
        )
        row = cursor.fetchone()
        if row is None:
            conn.rollback()
            raise ValueError("Action not found")
        action = dict(row)
        if action["status"] != "pending":
            conn.rollback()
            raise ValueError(f"Action cannot be approved from status '{action['status']}'")

        amount = action.get("expected_cost_amount")
        currency = action.get("currency")
        reservation_id = None

        if amount is not None and float(amount) > 0:
            if not currency:
                conn.rollback()
                raise ValueError("Paid actions require currency before approval")
            currency = _normalize_currency(currency)

            cursor.execute(
                """
                SELECT COALESCE(SUM(
                    CASE
                        WHEN entry_type IN ('funding', 'refund') THEN amount
                        WHEN entry_type = 'spend' THEN -amount
                        ELSE 0
                    END
                ), 0) AS cash_balance
                FROM treasury_entries
                WHERE currency = ?
                """,
                (currency,),
            )
            cash = float(cursor.fetchone()["cash_balance"] or 0)

            cursor.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS reserved
                FROM treasury_reservations
                WHERE currency = ? AND status = 'active'
                """,
                (currency,),
            )
            reserved = float(cursor.fetchone()["reserved"] or 0)
            available = cash - reserved
            if available + 1e-9 < float(amount):
                conn.rollback()
                raise ValueError(
                    f"Insufficient available treasury funds: need {float(amount):.2f} {currency}, "
                    f"available {available:.2f} {currency}"
                )

            cursor.execute(
                """
                INSERT INTO treasury_reservations (
                    timestamp, amount, currency, status,
                    source_action_id, source_action_sync_uuid,
                    source_decision_id, source_decision_sync_uuid, sync_uuid
                ) VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?)
                """,
                (
                    now, float(amount), currency,
                    action_id, action.get("sync_uuid"),
                    action.get("source_decision_id"),
                    action.get("source_decision_sync_uuid"),
                    str(uuid.uuid4()),
                ),
            )
            reservation_id = cursor.lastrowid

        cursor.execute(
            """
            UPDATE action_queue
            SET status = 'approved', reviewed_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (now, action_id),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            raise ValueError("Action approval race detected")

        conn.commit()
        return {
            "action_id": action_id,
            "status": "approved",
            "reservation_id": reservation_id,
            "reserved_amount": float(amount) if reservation_id else 0.0,
            "currency": currency if reservation_id else None,
        }


def reject_action_with_treasury(action_id: int) -> dict:
    """Atomically rejects an action and releases any active reservation."""
    now = datetime.datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("SELECT status FROM action_queue WHERE id = ?", (action_id,))
        row = cursor.fetchone()
        if row is None:
            conn.rollback()
            raise ValueError("Action not found")
        if row["status"] not in {"pending", "approved"}:
            conn.rollback()
            raise ValueError(f"Action cannot be rejected from status '{row['status']}'")

        cursor.execute(
            """
            UPDATE action_queue
            SET status = 'rejected', reviewed_at = ?
            WHERE id = ? AND status IN ('pending', 'approved')
            """,
            (now, action_id),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            raise ValueError("Action rejection race detected")

        cursor.execute(
            """
            UPDATE treasury_reservations
            SET status = 'released', released_at = ?
            WHERE source_action_id = ? AND status = 'active'
            """,
            (now, action_id),
        )
        released = cursor.rowcount == 1
        conn.commit()
        return {"action_id": action_id, "status": "rejected", "reservation_released": released}


def release_action_budget(action_id: int) -> bool:
    now = datetime.datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE treasury_reservations
            SET status = 'released', released_at = ?
            WHERE source_action_id = ? AND status = 'active'
            """,
            (now, action_id),
        )
        conn.commit()
        return cursor.rowcount == 1


def record_action_spend(action_id: int, amount: float, currency: str, note: str | None = None) -> dict:
    if amount < 0:
        raise ValueError("actual spend cannot be negative")
    action = get_action_by_id(action_id)
    if action is None:
        raise ValueError("Action not found")
    currency = _normalize_currency(currency)

    reservation = get_treasury_reservation_for_action(action_id)
    reserved_amount = 0.0
    if reservation and reservation["status"] == "active":
        if reservation["currency"] != currency:
            raise ValueError("Actual spend currency must match the reserved currency")
        reserved_amount = float(reservation["amount"])

    already_spent = 0.0
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM treasury_entries
            WHERE source_action_id = ? AND entry_type = 'spend'
            """,
            (action_id,),
        )
        already_spent = float(cursor.fetchone()["total"] or 0)

    if already_spent > 0:
        raise ValueError("Spend has already been recorded for this action")

    summary = get_treasury_summary(currency)["currencies"].get(
        currency,
        {"cash_balance": 0.0, "reserved": 0.0, "available": 0.0},
    )
    extra_needed = max(0.0, float(amount) - reserved_amount)
    if summary["available"] + 1e-9 < extra_needed:
        raise ValueError(
            f"Actual spend exceeds treasury capacity: extra {extra_needed:.2f} {currency} "
            f"needed, available {summary['available']:.2f} {currency}"
        )

    entry_id = None
    if float(amount) > 0:
        entry_id = add_treasury_entry(
            "spend",
            float(amount),
            currency,
            note or f"Actual cost for action #{action_id}",
            source_action_id=action_id,
            source_action_sync_uuid=action.get("sync_uuid"),
            source_decision_id=action.get("source_decision_id"),
            source_decision_sync_uuid=action.get("source_decision_sync_uuid"),
        )

    now = datetime.datetime.now().isoformat()
    if reservation and reservation["status"] == "active":
        with get_connection() as conn:
            cursor = conn.cursor()
            if float(amount) > 0:
                cursor.execute(
                    """
                    UPDATE treasury_reservations
                    SET status = 'consumed', consumed_at = ?
                    WHERE source_action_id = ? AND status = 'active'
                    """,
                    (now, action_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE treasury_reservations
                    SET status = 'released', released_at = ?
                    WHERE source_action_id = ? AND status = 'active'
                    """,
                    (now, action_id),
                )
            conn.commit()

    return {
        "entry_id": entry_id,
        "action_id": action_id,
        "amount": float(amount),
        "currency": currency,
        "reservation_consumed": bool(reservation and reservation["status"] == "active"),
    }


def get_treasury_for_decision(decision_id: int) -> dict:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM treasury_entries
            WHERE source_decision_id = ?
            ORDER BY timestamp ASC
            """,
            (decision_id,),
        )
        entries = [dict(row) for row in cursor.fetchall()]
        cursor.execute(
            """
            SELECT *
            FROM treasury_reservations
            WHERE source_decision_id = ?
            ORDER BY timestamp ASC
            """,
            (decision_id,),
        )
        reservations = [dict(row) for row in cursor.fetchall()]
        return {"entries": entries, "reservations": reservations}


# ===================================================================
# FUNCTIES VOOR ACTIEVOORSTELLEN (ACTION QUEUE)
# ===================================================================

def propose_action(
    proposed_by: str,
    action_description: str,
    action_detail: str,
    action_type: str = "shell",
    expected_outcome: str | None = None,
    expected_impact: str | None = None,
    expected_cost_amount: float | None = None,
    currency: str | None = None,
) -> int:
    """
    Voegt een voorgestelde actie toe aan de action_queue met de status 'pending'.
    action_type is 'shell' (raw shell-commando, bestaand gedrag) of
    'file_operation' (gestructureerde read/write/append, veiliger dan een
    ruwe shell-string omdat er geen shell aan te pas komt).
    Retourneert het gegenereerde rij-ID.
    """
    if action_type not in VALID_ACTION_TYPES:
        raise ValueError(
            f"Unsupported action_type '{action_type}'. Allowed: {sorted(VALID_ACTION_TYPES)}"
        )
    _reject_secret_like_text(
        proposed_by,
        action_description,
        action_detail,
        expected_outcome,
        expected_impact,
    )
    if expected_cost_amount is not None and expected_cost_amount < 0:
        raise ValueError("expected_cost_amount cannot be negative")
    if expected_cost_amount is not None and not currency:
        raise ValueError("currency is required when expected_cost_amount is provided")
    if currency is not None:
        currency = currency.strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("currency must be a 3-letter code such as EUR or USD")

    timestamp = datetime.datetime.now().isoformat()
    new_sync_uuid = str(uuid.uuid4())
    provenance = _current_action_provenance()
    source_decision_id = provenance.get("decision_id") if provenance else None
    source_decision_sync_uuid = provenance.get("decision_sync_uuid") if provenance else None
    source_phase = provenance.get("phase") if provenance else None

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO action_queue (
                timestamp, proposed_by, action_description, action_detail,
                status, action_type, sync_uuid,
                source_decision_id, source_decision_sync_uuid, source_phase
            )
            VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)
        """, (
            timestamp, proposed_by, action_description, action_detail,
            action_type, new_sync_uuid,
            source_decision_id, source_decision_sync_uuid, source_phase,
        ))
        
        action_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO action_outcomes (
                action_id, action_sync_uuid, expected_outcome, expected_impact,
                expected_cost_amount, currency, outcome_status, updated_at, sync_uuid
            ) VALUES (?, ?, ?, ?, ?, ?, 'not_started', ?, ?)
            """,
            (
                action_id,
                new_sync_uuid,
                expected_outcome,
                expected_impact,
                expected_cost_amount,
                currency,
                datetime.datetime.now().isoformat(),
                str(uuid.uuid4()),
            ),
        )
        conn.commit()

        if provenance is not None:
            with _ACTION_PROVENANCE_LOCK:
                provenance.setdefault("created_action_ids", []).append(action_id)

        return action_id


def get_latest_action_id() -> int:
    """Retourneert de hoogste action_queue id, of 0 als er nog geen acties zijn."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(MAX(id), 0) AS max_id FROM action_queue")
        return int(cursor.fetchone()["max_id"])


def get_actions_after_id(action_id: int) -> list[dict]:
    """Retourneert acties die ná een bekende queue-snapshot zijn aangemaakt."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT q.id, q.timestamp, q.proposed_by, q.action_description, q.action_detail,
                   q.status, q.reviewed_at, q.action_type, q.result_detail, q.sync_uuid,
                   q.source_decision_id, q.source_decision_sync_uuid, q.source_phase,
                   d.topic AS source_decision_topic,
                   d.goal_id AS source_goal_id, g.title AS source_goal_title,
                   o.expected_outcome, o.expected_impact, o.expected_cost_amount, o.currency,
                   o.outcome_status, o.actual_outcome, o.actual_impact, o.actual_cost_amount,
                   o.measured_at, o.next_recommendation, o.notes AS outcome_notes
            FROM action_queue q
            LEFT JOIN decisions d ON d.id = q.source_decision_id
            LEFT JOIN company_goals g ON g.id = d.goal_id
            LEFT JOIN action_outcomes o ON o.action_id = q.id
            WHERE q.id > ?
            ORDER BY q.id ASC
            """,
            (action_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_pending_actions() -> list[dict]:
    """
    Haalt alle acties op met status 'pending', meest recente eerst.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT q.id, q.timestamp, q.proposed_by, q.action_description, q.action_detail,
                   q.status, q.reviewed_at, q.action_type, q.result_detail, q.sync_uuid,
                   q.source_decision_id, q.source_decision_sync_uuid, q.source_phase,
                   d.topic AS source_decision_topic,
                   d.goal_id AS source_goal_id, g.title AS source_goal_title,
                   o.expected_outcome, o.expected_impact, o.expected_cost_amount, o.currency,
                   o.outcome_status, o.actual_outcome, o.actual_impact, o.actual_cost_amount,
                   o.measured_at, o.next_recommendation, o.notes AS outcome_notes
            FROM action_queue q
            LEFT JOIN decisions d ON d.id = q.source_decision_id
            LEFT JOIN company_goals g ON g.id = d.goal_id
            LEFT JOIN action_outcomes o ON o.action_id = q.id
            WHERE q.status IN ('pending', 'approved', 'executing')
            ORDER BY q.timestamp DESC
        """)
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def update_action_status(action_id: int, new_status: str) -> bool:
    """
    Interne status-update voor terminal execution paths. Valideert altijd dat
    de doelstatus een bekende status is. User-facing transitions gebruiken
    transition_action_status() zodat de verwachte bronstatus atomair wordt
    afgedwongen.
    """
    if new_status not in VALID_ACTION_STATUSES:
        raise ValueError(f"Unsupported action status: {new_status}")

    reviewed_at = datetime.datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE action_queue
            SET status = ?, reviewed_at = ?
            WHERE id = ?
        """, (new_status, reviewed_at, action_id))

        conn.commit()
        return cursor.rowcount > 0


def transition_action_status(
    action_id: int,
    new_status: str,
    allowed_from: tuple[str, ...],
) -> bool:
    """
    Atomische compare-and-set statusovergang. De UPDATE slaagt alleen wanneer
    de rij op het moment van schrijven nog in één van allowed_from staat.
    Dit sluit races tussen dashboard/Telegram-knoppen en dubbele requests.
    """
    if new_status not in VALID_ACTION_STATUSES:
        raise ValueError(f"Unsupported action status: {new_status}")
    if not allowed_from or any(s not in VALID_ACTION_STATUSES for s in allowed_from):
        raise ValueError(f"Invalid allowed_from statuses: {allowed_from}")

    reviewed_at = datetime.datetime.now().isoformat()
    placeholders = ", ".join("?" for _ in allowed_from)
    params = (new_status, reviewed_at, action_id, *allowed_from)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            UPDATE action_queue
            SET status = ?, reviewed_at = ?
            WHERE id = ? AND status IN ({placeholders})
            """,
            params,
        )
        conn.commit()
        return cursor.rowcount == 1


def claim_action_for_execution(action_id: int) -> bool:
    """Reserveert een approved actie atomair voor exact één executor."""
    return transition_action_status(action_id, "executing", ("approved",))


def record_execution_result(action_id: int, result_detail_json: str) -> bool:
    """
    Slaat het resultaat van een uitvoering (stdout, screenshot_path, etc. als
    JSON-string) permanent op bij de actie. Wordt aangeroepen door
    workflows/action_executor.py DIRECT NA update_action_status(), zodat het
    resultaat ook na een paginaherlading of in Action History zichtbaar
    blijft — niet alleen in het tijdelijke React-state van de sessie waarin
    de uitvoering plaatsvond.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE action_queue
            SET result_detail = ?
            WHERE id = ?
        """, (result_detail_json, action_id))

        conn.commit()
        return cursor.rowcount > 0

def get_action_outcome(action_id: int) -> dict | None:
    """Retourneert de business-outcome tracking voor één actie."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT o.*
            FROM action_outcomes o
            WHERE o.action_id = ?
            """,
            (action_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def update_action_outcome(
    action_id: int,
    *,
    expected_outcome: str | None = None,
    expected_impact: str | None = None,
    expected_cost_amount: float | None = None,
    currency: str | None = None,
    outcome_status: str | None = None,
    actual_outcome: str | None = None,
    actual_impact: str | None = None,
    actual_cost_amount: float | None = None,
    next_recommendation: str | None = None,
    notes: str | None = None,
) -> dict | None:
    """
    Werkt outcomevelden bij zonder technische execution-resultaten te
    overschrijven. Alleen expliciet meegegeven waarden worden gewijzigd.
    """
    if outcome_status is not None and outcome_status not in VALID_OUTCOME_STATUSES:
        raise ValueError(f"Unsupported outcome status: {outcome_status}")
    if expected_cost_amount is not None and expected_cost_amount < 0:
        raise ValueError("expected_cost_amount cannot be negative")
    if actual_cost_amount is not None and actual_cost_amount < 0:
        raise ValueError("actual_cost_amount cannot be negative")
    if currency is not None:
        currency = currency.strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("currency must be a 3-letter code such as EUR or USD")

    fields = {
        "expected_outcome": expected_outcome,
        "expected_impact": expected_impact,
        "expected_cost_amount": expected_cost_amount,
        "currency": currency,
        "outcome_status": outcome_status,
        "actual_outcome": actual_outcome,
        "actual_impact": actual_impact,
        "actual_cost_amount": actual_cost_amount,
        "next_recommendation": next_recommendation,
        "notes": notes,
    }
    updates = {key: value for key, value in fields.items() if value is not None}
    if not updates:
        return get_action_outcome(action_id)

    terminal_business_statuses = {"succeeded", "failed", "partial", "inconclusive"}
    if outcome_status in terminal_business_statuses:
        updates["measured_at"] = datetime.datetime.now().isoformat()
    updates["updated_at"] = datetime.datetime.now().isoformat()

    assignments = ", ".join(f"{key} = ?" for key in updates)
    values = list(updates.values()) + [action_id]
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE action_outcomes SET {assignments} WHERE action_id = ?",
            values,
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None

    return get_action_outcome(action_id)


def update_action_outcome_with_treasury(
    action_id: int,
    *,
    expected_outcome: str | None = None,
    expected_impact: str | None = None,
    expected_cost_amount: float | None = None,
    currency: str | None = None,
    outcome_status: str | None = None,
    actual_outcome: str | None = None,
    actual_impact: str | None = None,
    actual_cost_amount: float | None = None,
    next_recommendation: str | None = None,
    notes: str | None = None,
) -> dict | None:
    """
    Transactional outcome update. When actual_cost_amount is supplied, the
    treasury spend and reservation consumption happen in the SAME SQLite
    transaction as the outcome update.
    """
    if outcome_status is not None and outcome_status not in VALID_OUTCOME_STATUSES:
        raise ValueError(f"Unsupported outcome status: {outcome_status}")
    if expected_cost_amount is not None and expected_cost_amount < 0:
        raise ValueError("expected_cost_amount cannot be negative")
    if actual_cost_amount is not None and actual_cost_amount < 0:
        raise ValueError("actual_cost_amount cannot be negative")
    normalized_currency = _normalize_currency(currency) if currency is not None else None

    now = datetime.datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            """
            SELECT q.id, q.status, q.sync_uuid, q.source_decision_id,
                   q.source_decision_sync_uuid,
                   o.currency AS existing_currency, o.actual_cost_amount
            FROM action_queue q
            JOIN action_outcomes o ON o.action_id = q.id
            WHERE q.id = ?
            """,
            (action_id,),
        )
        action_row = cursor.fetchone()
        if action_row is None:
            conn.rollback()
            return None
        action = dict(action_row)

        effective_currency = normalized_currency or action.get("existing_currency")
        if (expected_cost_amount is not None or actual_cost_amount is not None) and not effective_currency:
            conn.rollback()
            raise ValueError("currency is required when recording a monetary amount")
        if effective_currency:
            effective_currency = _normalize_currency(effective_currency)

        fields = {
            "expected_outcome": expected_outcome,
            "expected_impact": expected_impact,
            "expected_cost_amount": expected_cost_amount,
            "currency": normalized_currency,
            "outcome_status": outcome_status,
            "actual_outcome": actual_outcome,
            "actual_impact": actual_impact,
            "actual_cost_amount": actual_cost_amount,
            "next_recommendation": next_recommendation,
            "notes": notes,
        }
        updates = {key: value for key, value in fields.items() if value is not None}

        if actual_cost_amount is not None:
            if action["actual_cost_amount"] is not None:
                conn.rollback()
                raise ValueError("Actual cost has already been recorded for this action")
            if action["status"] not in {"executed", "execution_failed", "blocked_dangerous"}:
                conn.rollback()
                raise ValueError(
                    "Actual cost can only be recorded after a live terminal execution state"
                )

            cursor.execute(
                """
                SELECT * FROM treasury_reservations
                WHERE source_action_id = ?
                """,
                (action_id,),
            )
            reservation_row = cursor.fetchone()
            reservation = dict(reservation_row) if reservation_row else None
            reserved_amount = 0.0
            if reservation and reservation["status"] == "active":
                if reservation["currency"] != effective_currency:
                    conn.rollback()
                    raise ValueError("Actual spend currency must match the reserved currency")
                reserved_amount = float(reservation["amount"])

            cursor.execute(
                """
                SELECT COALESCE(SUM(
                    CASE
                        WHEN entry_type IN ('funding', 'refund') THEN amount
                        WHEN entry_type = 'spend' THEN -amount
                        ELSE 0
                    END
                ), 0) AS cash_balance
                FROM treasury_entries
                WHERE currency = ?
                """,
                (effective_currency,),
            )
            cash = float(cursor.fetchone()["cash_balance"] or 0)

            cursor.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS reserved
                FROM treasury_reservations
                WHERE currency = ? AND status = 'active'
                """,
                (effective_currency,),
            )
            total_reserved = float(cursor.fetchone()["reserved"] or 0)
            available = cash - total_reserved
            extra_needed = max(0.0, float(actual_cost_amount) - reserved_amount)
            if available + 1e-9 < extra_needed:
                conn.rollback()
                raise ValueError(
                    f"Actual spend exceeds treasury capacity: extra {extra_needed:.2f} "
                    f"{effective_currency} needed, available {available:.2f} {effective_currency}"
                )

            if float(actual_cost_amount) > 0:
                cursor.execute(
                    """
                    INSERT INTO treasury_entries (
                        timestamp, entry_type, amount, currency, note,
                        source_action_id, source_action_sync_uuid,
                        source_decision_id, source_decision_sync_uuid, sync_uuid
                    ) VALUES (?, 'spend', ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        now,
                        float(actual_cost_amount),
                        effective_currency,
                        f"Actual cost for action #{action_id}",
                        action_id,
                        action.get("sync_uuid"),
                        action.get("source_decision_id"),
                        action.get("source_decision_sync_uuid"),
                        str(uuid.uuid4()),
                    ),
                )

            if reservation and reservation["status"] == "active":
                if float(actual_cost_amount) > 0:
                    cursor.execute(
                        """
                        UPDATE treasury_reservations
                        SET status = 'consumed', consumed_at = ?
                        WHERE source_action_id = ? AND status = 'active'
                        """,
                        (now, action_id),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE treasury_reservations
                        SET status = 'released', released_at = ?
                        WHERE source_action_id = ? AND status = 'active'
                        """,
                        (now, action_id),
                    )

        if outcome_status in {"succeeded", "failed", "partial", "inconclusive"}:
            updates["measured_at"] = now
        updates["updated_at"] = now

        if updates:
            assignments = ", ".join(f"{key} = ?" for key in updates)
            values = list(updates.values()) + [action_id]
            cursor.execute(
                f"UPDATE action_outcomes SET {assignments} WHERE action_id = ?",
                values,
            )
            if cursor.rowcount != 1:
                conn.rollback()
                return None

        conn.commit()

    return get_action_outcome(action_id)


def mark_action_outcome_measurement_pending(action_id: int) -> bool:
    """
    Na succesvolle LIVE execution begint pas de businessmeting. Dit zegt
    nadrukkelijk NIET dat het gewenste resultaat al behaald is.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE action_outcomes
            SET outcome_status = 'measurement_pending',
                updated_at = ?
            WHERE action_id = ?
              AND outcome_status = 'not_started'
            """,
            (datetime.datetime.now().isoformat(), action_id),
        )
        conn.commit()
        return cursor.rowcount == 1


def mark_action_outcome_execution_failed(action_id: int, reason: str) -> bool:
    """Legt vast dat het businessdoel niet kon worden bereikt door execution failure."""
    now = datetime.datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE action_outcomes
            SET outcome_status = 'failed',
                actual_outcome = ?,
                measured_at = ?,
                updated_at = ?,
                next_recommendation = COALESCE(
                    next_recommendation,
                    'Review the execution failure before proposing a retry.'
                )
            WHERE action_id = ?
              AND outcome_status IN ('not_started', 'measurement_pending')
            """,
            (reason, now, now, action_id),
        )
        conn.commit()
        return cursor.rowcount == 1


def recover_interrupted_actions() -> int:
    """
    Markeer acties die na een procesherstart nog op 'executing' staan als
    execution_failed. We weten na een crash NIET of het echte effect volledig,
    gedeeltelijk of helemaal niet heeft plaatsgevonden, dus automatisch opnieuw
    uitvoeren zou gevaarlijk zijn. De actie blijft in de audit trail voor
    menselijke beoordeling.
    """
    reviewed_at = datetime.datetime.now().isoformat()
    result_detail = json.dumps({
        "error": (
            "Execution was interrupted by a process shutdown/crash while the "
            "action was marked 'executing'. Real-world outcome is unknown; "
            "manual review is required before proposing any retry."
        )
    })
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM action_queue WHERE status = 'executing'")
        interrupted_ids = [row[0] for row in cursor.fetchall()]
        if not interrupted_ids:
            return 0

        placeholders = ", ".join("?" for _ in interrupted_ids)
        cursor.execute(
            f"""
            UPDATE action_queue
            SET status = 'execution_failed',
                reviewed_at = ?,
                result_detail = ?
            WHERE id IN ({placeholders})
            """,
            (reviewed_at, result_detail, *interrupted_ids),
        )
        recovered_count = cursor.rowcount

        # Een crash betekent dat het echte effect ONBEKEND is. Niet automatisch
        # 'failed' noemen: er kan een gedeeltelijk extern effect zijn geweest.
        cursor.execute(
            f"""
            UPDATE action_outcomes
            SET outcome_status = 'inconclusive',
                actual_outcome = ?,
                measured_at = ?,
                updated_at = ?,
                next_recommendation = COALESCE(
                    next_recommendation,
                    'Manually inspect the real-world state before proposing any retry.'
                )
            WHERE action_id IN ({placeholders})
            """,
            (
                "Execution was interrupted; the real-world business outcome is unknown.",
                reviewed_at,
                reviewed_at,
                *interrupted_ids,
            ),
        )
        conn.commit()
        return recovered_count


def get_action_by_id(action_id: int) -> dict | None:
    """
    Haalt één specifieke actie op uit de action_queue op basis van het ID.
    Retourneert de actie als een dictionary, of None als het ID niet gevonden is.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT q.id, q.timestamp, q.proposed_by, q.action_description, q.action_detail,
                   q.status, q.reviewed_at, q.action_type, q.result_detail, q.sync_uuid,
                   q.source_decision_id, q.source_decision_sync_uuid, q.source_phase,
                   d.topic AS source_decision_topic,
                   d.goal_id AS source_goal_id, g.title AS source_goal_title,
                   o.expected_outcome, o.expected_impact, o.expected_cost_amount, o.currency,
                   o.outcome_status, o.actual_outcome, o.actual_impact, o.actual_cost_amount,
                   o.measured_at, o.next_recommendation, o.notes AS outcome_notes
            FROM action_queue q
            LEFT JOIN decisions d ON d.id = q.source_decision_id
            LEFT JOIN company_goals g ON g.id = d.goal_id
            LEFT JOIN action_outcomes o ON o.action_id = q.id
            WHERE q.id = ?
        """, (action_id,))

        row = cursor.fetchone()
        return dict(row) if row else None


def get_actions_for_decision(decision_id: int) -> list[dict]:
    """Return all actions explicitly linked to one decision, oldest first."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT q.id, q.timestamp, q.proposed_by, q.action_description,
                   q.action_detail, q.status, q.reviewed_at, q.action_type,
                   q.result_detail, q.sync_uuid, q.source_decision_id,
                   q.source_decision_sync_uuid, q.source_phase,
                   d.topic AS source_decision_topic,
                   d.goal_id AS source_goal_id, g.title AS source_goal_title,
                   o.expected_outcome, o.expected_impact, o.expected_cost_amount,
                   o.currency, o.outcome_status, o.actual_outcome, o.actual_impact,
                   o.actual_cost_amount, o.measured_at, o.next_recommendation,
                   o.notes AS outcome_notes
            FROM action_queue q
            LEFT JOIN decisions d ON d.id = q.source_decision_id
            LEFT JOIN company_goals g ON g.id = d.goal_id
            LEFT JOIN action_outcomes o ON o.action_id = q.id
            WHERE q.source_decision_id = ?
            ORDER BY q.timestamp ASC
            """,
            (decision_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_decision_lineage(decision_id: int) -> dict | None:
    """Build the full decision → preparation → actions → outcomes chain."""
    decision = get_decision_by_id(decision_id)
    if decision is None:
        return None
    return {
        "decision": decision,
        "actions": get_actions_for_decision(decision_id),
        "resource_requests": get_resource_requests_for_decision(decision_id),
        "treasury": get_treasury_for_decision(decision_id),
    }


def get_action_history(limit: int = 20, offset: int = 0, status_filter: str | None = None) -> list[dict]:
    """
    Haalt de meest recente acties op UIT ALLE STATUSSEN (pending, approved,
    rejected, executed, executed_dry_run, blocked_dangerous, execution_failed) —
    in tegenstelling tot get_pending_actions(), die alleen nog-actiegevende
    items toont. Dit geeft dezelfde audit-trail-volledigheid als
    get_recent_decisions() al biedt voor beslissingen: eenmaal afgehandeld
    verdwijnt een actie hier nooit, hij blijft zichtbaar in de geschiedenis.

    offset maakt paginering mogelijk; status_filter (optioneel) beperkt het
    resultaat tot één specifieke status (bijv. alleen 'blocked_dangerous'
    om snel te zien wat er geweigerd is).
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        if status_filter:
            cursor.execute("""
                SELECT q.id, q.timestamp, q.proposed_by, q.action_description, q.action_detail,
                       q.status, q.reviewed_at, q.action_type, q.result_detail, q.sync_uuid,
                       q.source_decision_id, q.source_decision_sync_uuid, q.source_phase,
                       d.topic AS source_decision_topic,
                       d.goal_id AS source_goal_id, g.title AS source_goal_title,
                       o.expected_outcome, o.expected_impact, o.expected_cost_amount, o.currency,
                       o.outcome_status, o.actual_outcome, o.actual_impact, o.actual_cost_amount,
                       o.measured_at, o.next_recommendation, o.notes AS outcome_notes
                FROM action_queue q
                LEFT JOIN decisions d ON d.id = q.source_decision_id
                LEFT JOIN company_goals g ON g.id = d.goal_id
                LEFT JOIN action_outcomes o ON o.action_id = q.id
                WHERE q.status = ?
                ORDER BY q.timestamp DESC
                LIMIT ? OFFSET ?
            """, (status_filter, limit, offset))
        else:
            cursor.execute("""
                SELECT q.id, q.timestamp, q.proposed_by, q.action_description, q.action_detail,
                       q.status, q.reviewed_at, q.action_type, q.result_detail, q.sync_uuid,
                       q.source_decision_id, q.source_decision_sync_uuid, q.source_phase,
                       d.topic AS source_decision_topic,
                       d.goal_id AS source_goal_id, g.title AS source_goal_title,
                       o.expected_outcome, o.expected_impact, o.expected_cost_amount, o.currency,
                       o.outcome_status, o.actual_outcome, o.actual_impact, o.actual_cost_amount,
                       o.measured_at, o.next_recommendation, o.notes AS outcome_notes
                FROM action_queue q
                LEFT JOIN decisions d ON d.id = q.source_decision_id
                LEFT JOIN company_goals g ON g.id = d.goal_id
                LEFT JOIN action_outcomes o ON o.action_id = q.id
                ORDER BY q.timestamp DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]


# ===================================================================
# CROSS-MACHINE SYNC (export/import als JSON Lines)
# ===================================================================
# SQLite zelf blijft bewust buiten git (binair, merget niet netjes).
# JSONL export/import blijft beschikbaar als HANDMATIGE data-overdracht, maar
# exports bevatten besluit- en actiegeschiedenis en zijn daarom bewust
# gitignored. Deel/verplaats zo'n bestand alleen via een vertrouwd kanaal en
# verwijder het wanneer de import klaar is. sync_uuid is de stabiele identiteit
# van elke rij over machines heen — de lokale autoincrement 'id' verschilt per
# database en mag NOOIT gebruikt worden om te bepalen of een rij al bestaat.
#
# Gebruik:
#   Export: python -c "from memory.database import export_history_to_jsonl; export_history_to_jsonl('sync/history_export.jsonl')"
#   Verplaats dat bestand via een vertrouwd privé-kanaal naar de andere machine.
#   Import: python -c "from memory.database import import_history_from_jsonl; import_history_from_jsonl('sync/history_export.jsonl')"

def export_history_to_jsonl(export_path: str) -> dict:
    """
    Exporteert ALLE rijen uit decisions en action_queue naar één JSON Lines
    bestand — elke regel is {"table": "decisions"|"action_queue", ...velden...}.
    Retourneert {"decisions": aantal, "actions": aantal} als samenvatting.
    """
    os.makedirs(os.path.dirname(export_path) or ".", exist_ok=True)

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT created_at, updated_at, title, description, success_criteria,
                   priority, target_date, status, completed_at, completion_note,
                   sync_uuid
            FROM company_goals
        """)
        goal_rows = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT created_at, updated_at, event_type, status, severity, reason,
                   fingerprint, goal_sync_uuid, source_action_sync_uuid,
                   source_decision_sync_uuid, generated_decision_sync_uuid,
                   resolved_at, sync_uuid
            FROM followup_events
        """)
        followup_rows = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT created_at, updated_at, executive_key, memory_kind, lesson,
                   supporting_evidence, confidence, is_active,
                   source_goal_sync_uuid, source_decision_sync_uuid,
                   source_action_sync_uuid, fingerprint, sync_uuid
            FROM executive_memories
        """)
        memory_rows = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT timestamp, topic, agents_involved, task_description,
                   decision_outcome, sandbox_mode, sync_uuid, goal_sync_uuid,
                   meeting_type
            FROM decisions
        """)
        decision_rows = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT
                timestamp, proposed_by, action_description, action_detail,
                status, reviewed_at, action_type, result_detail, sync_uuid,
                source_decision_sync_uuid, source_phase
            FROM action_queue
        """)
        action_rows = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT
                action_sync_uuid, expected_outcome, expected_impact,
                expected_cost_amount, currency, outcome_status, actual_outcome,
                actual_impact, actual_cost_amount, measured_at,
                next_recommendation, notes, updated_at, sync_uuid
            FROM action_outcomes
        """)
        outcome_rows = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT timestamp, requested_by, resource_type, resource_name,
                   reason, required_for, amount, currency, status, reviewed_at,
                   fulfilled_at, fulfillment_note, source_decision_sync_uuid,
                   source_phase, sync_uuid
            FROM resource_requests
        """)
        resource_rows = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT timestamp, entry_type, amount, currency, note,
                   source_action_sync_uuid, source_decision_sync_uuid, sync_uuid
            FROM treasury_entries
        """)
        treasury_entry_rows = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT timestamp, amount, currency, status, released_at, consumed_at,
                   source_action_sync_uuid, source_decision_sync_uuid, sync_uuid
            FROM treasury_reservations
        """)
        treasury_reservation_rows = [dict(row) for row in cursor.fetchall()]

    export_dir = os.path.dirname(os.path.abspath(export_path)) or "."
    os.makedirs(export_dir, exist_ok=True)
    try:
        os.chmod(export_dir, 0o700)
    except OSError:
        pass

    with open(export_path, "w", encoding="utf-8") as f:
        for table_name, rows in (
            ("company_goals", goal_rows),
            ("decisions", decision_rows),
            ("action_queue", action_rows),
            ("action_outcomes", outcome_rows),
            ("resource_requests", resource_rows),
            ("treasury_entries", treasury_entry_rows),
            ("treasury_reservations", treasury_reservation_rows),
            ("followup_events", followup_rows),
            ("executive_memories", memory_rows),
        ):
            for source_row in rows:
                record = dict(source_row)
                record["_table"] = table_name
                record["_signature"] = _sync_record_signature(record)
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    try:
        os.chmod(export_path, 0o600)
    except OSError:
        pass

    return {
        "goals": len(goal_rows),
        "followup_events": len(followup_rows),
        "executive_memories": len(memory_rows),
        "decisions": len(decision_rows),
        "actions": len(action_rows),
        "outcomes": len(outcome_rows),
        "resource_requests": len(resource_rows),
        "treasury_entries": len(treasury_entry_rows),
        "treasury_reservations": len(treasury_reservation_rows),
    }


def import_history_from_jsonl(import_path: str) -> dict:
    """
    Leest een export-bestand en voegt elke rij toe WIENS sync_uuid nog niet
    lokaal bestaat — bestaande rijen (zelfde sync_uuid) worden overgeslagen,
    dus dit kan veilig herhaald worden zonder duplicaten te creëren, ongeacht
    hoe vaak je export/import tussen machines heen en weer doet.
    Retourneert {"decisions_imported": ..., "actions_imported": ..., "skipped": ...}.
    """
    if not os.path.exists(import_path):
        return {"error": f"Import file not found: {import_path}"}

    imported_goals = 0
    imported_followup_events = 0
    imported_executive_memories = 0
    imported_decisions = 0
    imported_actions = 0
    imported_outcomes = 0
    imported_resource_requests = 0
    imported_treasury_entries = 0
    imported_treasury_reservations = 0
    skipped = 0

    with get_connection() as conn:
        cursor = conn.cursor()

        with open(import_path, "r", encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    skipped += 1
                    continue

                if not isinstance(row, dict):
                    skipped += 1
                    continue

                # Cross-machine sync carries executable/treasury history.
                # Never trust unsigned/tampered records.
                try:
                    if not _sync_record_signature_valid(row):
                        skipped += 1
                        continue
                except ValueError:
                    skipped += 1
                    continue
                row.pop("_signature", None)

                table = row.pop("_table", None)
                sync_uuid_value = row.get("sync_uuid")

                # Nooit tabel-/kolomnamen uit een JSONL-bestand rechtstreeks in
                # SQL interpoleren. Alleen de twee bekende schemas zijn geldig.
                if table not in _SYNC_TABLE_COLUMNS or not sync_uuid_value:
                    skipped += 1
                    continue

                # Verwijder het lokale 'id' veld uit de import — een nieuwe
                # autoincrement id wordt toegekend door DEZE database.
                row.pop("id", None)

                allowed_columns = _SYNC_TABLE_COLUMNS[table]
                required_columns = {
                    "company_goals": {
                        "created_at", "updated_at", "title", "description",
                        "success_criteria", "priority", "status", "sync_uuid",
                    },
                    "followup_events": {
                        "created_at", "updated_at", "event_type", "status",
                        "severity", "reason", "fingerprint", "sync_uuid",
                    },
                    "executive_memories": {
                        "created_at", "updated_at", "executive_key", "memory_kind",
                        "lesson", "confidence", "is_active", "fingerprint", "sync_uuid",
                    },
                    "decisions": {
                        "timestamp", "topic", "agents_involved", "task_description",
                        "decision_outcome", "sandbox_mode", "sync_uuid",
                    },
                    "action_queue": {
                        "timestamp", "proposed_by", "action_description", "action_detail",
                        "status", "action_type", "sync_uuid",
                    },
                    "action_outcomes": {
                        "action_sync_uuid", "outcome_status", "updated_at", "sync_uuid",
                    },
                    "resource_requests": {
                        "timestamp", "requested_by", "resource_type", "resource_name",
                        "reason", "status", "sync_uuid",
                    },
                    "treasury_entries": {
                        "timestamp", "entry_type", "amount", "currency", "sync_uuid",
                    },
                    "treasury_reservations": {
                        "timestamp", "amount", "currency", "status", "sync_uuid",
                    },
                }[table]

                if (
                    not row
                    or any(column not in allowed_columns for column in row)
                    or not required_columns.issubset(row.keys())
                ):
                    skipped += 1
                    continue

                if table == "company_goals":
                    if row.get("status") not in VALID_GOAL_STATUSES:
                        skipped += 1
                        continue
                    if row.get("priority") not in VALID_GOAL_PRIORITIES:
                        skipped += 1
                        continue
                    try:
                        if row.get("target_date"):
                            _normalize_goal_target_date(row.get("target_date"))
                    except ValueError:
                        skipped += 1
                        continue

                if table == "decisions":
                    if row.get("meeting_type", "strategy") not in VALID_MEETING_TYPES:
                        skipped += 1
                        continue
                    row["meeting_type"] = row.get("meeting_type", "strategy")
                    goal_sync_uuid = row.get("goal_sync_uuid")
                    if goal_sync_uuid:
                        cursor.execute(
                            "SELECT id FROM company_goals WHERE sync_uuid = ?",
                            (goal_sync_uuid,),
                        )
                        goal_row = cursor.fetchone()
                        if not goal_row:
                            skipped += 1
                            continue
                        row["goal_id"] = goal_row["id"]

                if table == "action_queue":
                    if row.get("status") not in VALID_ACTION_STATUSES:
                        skipped += 1
                        continue
                    # Sync transports history, never executable authority.
                    # Remote approved/executing state must be re-approved
                    # locally before this machine may perform a real effect.
                    if row.get("status") in {"approved", "executing"}:
                        row["status"] = "pending"
                        row["reviewed_at"] = None
                        row["result_detail"] = None
                    if row.get("action_type") not in VALID_ACTION_TYPES:
                        skipped += 1
                        continue

                    source_decision_sync_uuid = row.get("source_decision_sync_uuid")
                    if source_decision_sync_uuid:
                        cursor.execute(
                            "SELECT id FROM decisions WHERE sync_uuid = ?",
                            (source_decision_sync_uuid,),
                        )
                        source_decision = cursor.fetchone()
                        if not source_decision:
                            # Never create a provenance link to the wrong local ID.
                            # Import the decision first, then retry this export.
                            skipped += 1
                            continue
                        row["source_decision_id"] = source_decision["id"]
                if table == "resource_requests":
                    if row.get("status") not in VALID_RESOURCE_REQUEST_STATUSES:
                        skipped += 1
                        continue
                    if row.get("resource_type") not in VALID_RESOURCE_TYPES:
                        skipped += 1
                        continue
                    source_decision_sync_uuid = row.get("source_decision_sync_uuid")
                    if source_decision_sync_uuid:
                        cursor.execute(
                            "SELECT id FROM decisions WHERE sync_uuid = ?",
                            (source_decision_sync_uuid,),
                        )
                        source_decision = cursor.fetchone()
                        if not source_decision:
                            skipped += 1
                            continue
                        row["source_decision_id"] = source_decision["id"]
                if table in {"treasury_entries", "treasury_reservations"}:
                    if table == "treasury_entries" and row.get("entry_type") not in VALID_TREASURY_ENTRY_TYPES:
                        skipped += 1
                        continue
                    if table == "treasury_reservations" and row.get("status") not in VALID_TREASURY_RESERVATION_STATUSES:
                        skipped += 1
                        continue
                    if table == "treasury_reservations" and row.get("status") == "active":
                        # A remote reservation represents remote approval.
                        # Preserve the audit row but never import it as local
                        # spending authority.
                        row["status"] = "released"
                        row["released_at"] = datetime.datetime.now().isoformat()

                    action_sync_uuid = row.get("source_action_sync_uuid")
                    if action_sync_uuid:
                        cursor.execute(
                            "SELECT id FROM action_queue WHERE sync_uuid = ?",
                            (action_sync_uuid,),
                        )
                        action_row = cursor.fetchone()
                        if not action_row:
                            skipped += 1
                            continue
                        row["source_action_id"] = action_row["id"]

                    decision_sync_uuid = row.get("source_decision_sync_uuid")
                    if decision_sync_uuid:
                        cursor.execute(
                            "SELECT id FROM decisions WHERE sync_uuid = ?",
                            (decision_sync_uuid,),
                        )
                        decision_row = cursor.fetchone()
                        if not decision_row:
                            skipped += 1
                            continue
                        row["source_decision_id"] = decision_row["id"]

                if table == "action_outcomes":
                    if row.get("outcome_status") not in VALID_OUTCOME_STATUSES:
                        skipped += 1
                        continue
                    cursor.execute(
                        "SELECT id FROM action_queue WHERE sync_uuid = ?",
                        (row.get("action_sync_uuid"),),
                    )
                    action_match = cursor.fetchone()
                    if not action_match:
                        skipped += 1
                        continue

                    # init_db() maakt voor iedere actie al een lege outcome-row.
                    # Bij sync moet echte remote outcome-data die placeholder
                    # BIJWERKEN in plaats van botsen op action_id UNIQUE en stil
                    # worden overgeslagen.
                    local_action_id = action_match["id"]
                    cursor.execute(
                        "SELECT sync_uuid FROM action_outcomes WHERE action_sync_uuid = ?",
                        (row.get("action_sync_uuid"),),
                    )
                    existing_outcome = cursor.fetchone()
                    if existing_outcome:
                        if existing_outcome["sync_uuid"] == sync_uuid_value:
                            skipped += 1
                            continue
                        importable_fields = [
                            key for key in row.keys()
                            if key not in {"action_id", "action_sync_uuid"}
                        ]
                        assignments = ", ".join(f"{key} = ?" for key in importable_fields)
                        cursor.execute(
                            f"""
                            UPDATE action_outcomes
                            SET {assignments}
                            WHERE action_sync_uuid = ?
                            """,
                            tuple(row[key] for key in importable_fields)
                            + (row.get("action_sync_uuid"),),
                        )
                        imported_outcomes += 1
                        continue

                    row["action_id"] = local_action_id

                if table == "followup_events":
                    if row.get("event_type") not in VALID_FOLLOWUP_EVENT_TYPES:
                        skipped += 1
                        continue
                    if row.get("status") not in VALID_FOLLOWUP_STATUSES:
                        skipped += 1
                        continue
                    if row.get("severity") not in VALID_FOLLOWUP_SEVERITIES:
                        skipped += 1
                        continue

                    for uuid_key, table_name, id_key in (
                        ("goal_sync_uuid", "company_goals", "goal_id"),
                        ("source_action_sync_uuid", "action_queue", "source_action_id"),
                        ("source_decision_sync_uuid", "decisions", "source_decision_id"),
                        ("generated_decision_sync_uuid", "decisions", "generated_decision_id"),
                    ):
                        foreign_uuid = row.get(uuid_key)
                        if foreign_uuid:
                            cursor.execute(
                                f"SELECT id FROM {table_name} WHERE sync_uuid = ?",
                                (foreign_uuid,),
                            )
                            foreign_row = cursor.fetchone()
                            if not foreign_row:
                                skipped += 1
                                row = None
                                break
                            row[id_key] = foreign_row["id"]
                    if row is None:
                        continue

                if table == "executive_memories":
                    if row.get("memory_kind") not in VALID_EXECUTIVE_MEMORY_KINDS:
                        skipped += 1
                        continue
                    try:
                        confidence = float(row.get("confidence"))
                    except (TypeError, ValueError):
                        skipped += 1
                        continue
                    if not (0.0 <= confidence <= 1.0):
                        skipped += 1
                        continue
                    if row.get("is_active") not in {0, 1, False, True}:
                        skipped += 1
                        continue

                    for uuid_key, table_name, id_key in (
                        ("source_goal_sync_uuid", "company_goals", "source_goal_id"),
                        ("source_decision_sync_uuid", "decisions", "source_decision_id"),
                        ("source_action_sync_uuid", "action_queue", "source_action_id"),
                    ):
                        foreign_uuid = row.get(uuid_key)
                        if foreign_uuid:
                            cursor.execute(
                                f"SELECT id FROM {table_name} WHERE sync_uuid = ?",
                                (foreign_uuid,),
                            )
                            foreign_row = cursor.fetchone()
                            if not foreign_row:
                                skipped += 1
                                row = None
                                break
                            row[id_key] = foreign_row["id"]
                    if row is None:
                        continue

                cursor.execute(f"SELECT 1 FROM {table} WHERE sync_uuid = ?", (sync_uuid_value,))
                if cursor.fetchone():
                    skipped += 1
                    continue

                # table en columns komen vanaf hier uitsluitend uit vaste
                # whitelists hierboven, niet uit onbetrouwbare input.
                columns = ", ".join(row.keys())
                placeholders = ", ".join(["?"] * len(row))
                try:
                    cursor.execute(
                        f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
                        tuple(row.values())
                    )
                except (sqlite3.IntegrityError, sqlite3.OperationalError):
                    # Eén beschadigde/onvolledige regel mag een volledige
                    # geschiedenis-import niet afbreken.
                    skipped += 1
                    continue

                if table == "company_goals":
                    imported_goals += 1
                elif table == "followup_events":
                    imported_followup_events += 1
                elif table == "executive_memories":
                    imported_executive_memories += 1
                elif table == "decisions":
                    imported_decisions += 1
                    imported_decision_id = cursor.lastrowid
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO decision_approvals (
                            decision_id, status, reviewed_at,
                            preparation_status, prepared_at, preparation_outcome
                        ) VALUES (?, 'pending', NULL, 'not_started', NULL, NULL)
                        """,
                        (imported_decision_id,),
                    )
                elif table == "action_queue":
                    imported_actions += 1
                elif table == "action_outcomes":
                    imported_outcomes += 1
                elif table == "resource_requests":
                    imported_resource_requests += 1
                elif table == "treasury_entries":
                    imported_treasury_entries += 1
                else:
                    imported_treasury_reservations += 1

        conn.commit()

    return {
        "goals_imported": imported_goals,
        "followup_events_imported": imported_followup_events,
        "executive_memories_imported": imported_executive_memories,
        "decisions_imported": imported_decisions,
        "actions_imported": imported_actions,
        "outcomes_imported": imported_outcomes,
        "resource_requests_imported": imported_resource_requests,
        "treasury_entries_imported": imported_treasury_entries,
        "treasury_reservations_imported": imported_treasury_reservations,
        "skipped_existing": skipped,
    }


# ===================================================================
# HANDMATIGE TEST / DIRECTE UITVOERING
# ===================================================================

# ===================================================================
# AUTOMATISCHE BACKUPS
# ===================================================================

def backup_database(backup_dir: str = "backups", keep_last: int = 7) -> str:
    """
    Kopieert het huidige databasebestand naar backup_dir met een tijdstempel
    (microseconde-precisie, om overschrijven bij snel-opeenvolgende aanroepen
    te voorkomen) in de naam, en ruimt oudere backups op zodat er nooit meer
    dan keep_last exemplaren blijven staan. Dit is een APARTE, eenvoudigere
    beveiliging dan de JSONL-export uit Stap 38 (die is voor cross-machine
    sync; dit is puur "een reddingslijn als de database zelf corrupt raakt of
    per ongeluk verwijderd wordt"). Retourneert het pad van de nieuwe backup.
    """
    import datetime as _dt

    os.makedirs(backup_dir, exist_ok=True)
    try:
        os.chmod(backup_dir, 0o700)
    except OSError:
        pass
    timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    db_path = config.DATABASE_PATH
    backup_filename = f"executive_team_backup_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_filename)

    # Gebruik SQLite's eigen online-backup API in plaats van shutil.copy2().
    # Een rauwe bestandscopy kan midden in een actieve write/transactie een
    # inconsistente snapshot opleveren. sqlite3.Connection.backup() neemt een
    # transaction-consistente snapshot terwijl de bron-DB live mag blijven.
    source = sqlite3.connect(db_path, timeout=5.0)
    destination = sqlite3.connect(backup_path, timeout=5.0)
    try:
        source.backup(destination)
        destination.commit()
    finally:
        destination.close()
        source.close()
    try:
        os.chmod(backup_path, 0o600)
    except OSError:
        pass

    existing_backups = sorted(
        [f for f in os.listdir(backup_dir) if f.startswith("executive_team_backup_") and f.endswith(".db")]
    )
    while len(existing_backups) > keep_last:
        oldest = existing_backups.pop(0)
        try:
            os.remove(os.path.join(backup_dir, oldest))
        except OSError:
            pass

    return backup_path


# ===================================================================
# SYSTEEMSTATISTIEKEN
# ===================================================================

def get_system_stats() -> dict:
    """
    Levert de cijfers achter /system/stats: totaal aantal beslissingen en
    acties, een uitsplitsing van acties per status, en het slaagpercentage
    van de dagelijkse research-verificatie (op basis van hoeveel
    'Daily Research Findings' vs 'Daily Research FAILED' topics gelogd zijn).
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as count FROM decisions")
        total_decisions = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM action_queue")
        total_actions = cursor.fetchone()["count"]

        cursor.execute("SELECT status, COUNT(*) as count FROM action_queue GROUP BY status")
        actions_by_status = {row["status"]: row["count"] for row in cursor.fetchall()}

        cursor.execute("SELECT COUNT(*) as count FROM decisions WHERE topic = 'Daily Research Findings'")
        research_success_count = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM decisions WHERE topic LIKE 'Daily Research FAILED%'")
        research_failed_count = cursor.fetchone()["count"]

    total_research_runs = research_success_count + research_failed_count
    research_success_rate = (
        round(research_success_count / total_research_runs * 100, 1) if total_research_runs > 0 else None
    )

    return {
        "total_decisions": total_decisions,
        "total_actions": total_actions,
        "actions_by_status": actions_by_status,
        "daily_research_success_count": research_success_count,
        "daily_research_failed_count": research_failed_count,
        "daily_research_success_rate_percent": research_success_rate,
    }


if __name__ == "__main__":
    init_db()
    abs_path = os.path.abspath(config.DATABASE_PATH)
    print("=" * 60)
    print(f"Database initialized at: {abs_path}")
    print("=" * 60)

    recent = get_recent_decisions()
    print(f"Recente beslissingen ({len(recent)} gevonden):")
    for item in recent:
        print(item)
    print("=" * 60)

    pending = get_pending_actions()
    print(f"In afwachting van goedkeuring ({len(pending)} gevonden):")
    for action in pending:
        print(action)
    print("=" * 60)