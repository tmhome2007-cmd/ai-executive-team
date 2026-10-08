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
from pathlib import Path
from contextlib import contextmanager

# Zorg ervoor dat de hoofdmap van het project bereikbaar is voor imports
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from config import config


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
VALID_OUTCOME_STATUSES = {
    "not_started",
    "measurement_pending",
    "succeeded",
    "failed",
    "partial",
    "inconclusive",
}

_SYNC_TABLE_COLUMNS = {
    "decisions": {
        "timestamp", "topic", "agents_involved", "task_description",
        "decision_outcome", "sandbox_mode", "sync_uuid",
    },
    "action_queue": {
        "timestamp", "proposed_by", "action_description", "action_detail",
        "status", "reviewed_at", "action_type", "result_detail", "sync_uuid",
    },
    "action_outcomes": {
        "action_sync_uuid", "expected_outcome", "expected_impact",
        "expected_cost_amount", "currency", "outcome_status", "actual_outcome",
        "actual_impact", "actual_cost_amount", "measured_at",
        "next_recommendation", "notes", "updated_at", "sync_uuid",
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
            sync_uuid TEXT
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
            result_detail TEXT
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
# FUNCTIES VOOR BESTUURSBESLUITEN (DECISIONS)
# ===================================================================

def log_decision(
    topic: str,
    agents_involved: list[str],
    task_description: str,
    decision_outcome: str,
    sandbox_mode: bool = True
) -> int:
    """
    Slaat een nieuwe beslissing op in de database en geeft de nieuwe rij-ID terug.
    """
    timestamp = datetime.datetime.now().isoformat()
    agents_str = ",".join(agents_involved)
    sandbox_flag = 1 if sandbox_mode else 0
    new_sync_uuid = str(uuid.uuid4())

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO decisions (
                timestamp, topic, agents_involved, task_description, decision_outcome, sandbox_mode, sync_uuid
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (timestamp, topic, agents_str, task_description, decision_outcome, sandbox_flag, new_sync_uuid))
        
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
                d.sync_uuid,
                COALESCE(a.status, 'pending') AS approval_status,
                a.reviewed_at AS approval_reviewed_at,
                COALESCE(a.preparation_status, 'not_started') AS preparation_status,
                a.prepared_at,
                a.preparation_outcome
            FROM decisions d
            LEFT JOIN decision_approvals a ON a.decision_id = d.id
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
                COALESCE(a.status, 'pending') AS approval_status,
                a.reviewed_at AS approval_reviewed_at,
                COALESCE(a.preparation_status, 'not_started') AS preparation_status,
                a.prepared_at,
                a.preparation_outcome
            FROM decisions d
            LEFT JOIN decision_approvals a ON a.decision_id = d.id
            ORDER BY d.timestamp DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


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

    timestamp = datetime.datetime.now().isoformat()
    new_sync_uuid = str(uuid.uuid4())
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO action_queue (timestamp, proposed_by, action_description, action_detail, status, action_type, sync_uuid)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
        """, (timestamp, proposed_by, action_description, action_detail, action_type, new_sync_uuid))
        
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
                   o.expected_outcome, o.expected_impact, o.expected_cost_amount, o.currency,
                   o.outcome_status, o.actual_outcome, o.actual_impact, o.actual_cost_amount,
                   o.measured_at, o.next_recommendation, o.notes AS outcome_notes
            FROM action_queue q
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
                   o.expected_outcome, o.expected_impact, o.expected_cost_amount, o.currency,
                   o.outcome_status, o.actual_outcome, o.actual_impact, o.actual_cost_amount,
                   o.measured_at, o.next_recommendation, o.notes AS outcome_notes
            FROM action_queue q
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
        cursor.execute(
            """
            UPDATE action_queue
            SET status = 'execution_failed',
                reviewed_at = ?,
                result_detail = ?
            WHERE status = 'executing'
            """,
            (reviewed_at, result_detail),
        )
        conn.commit()
        return cursor.rowcount


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
                   o.expected_outcome, o.expected_impact, o.expected_cost_amount, o.currency,
                   o.outcome_status, o.actual_outcome, o.actual_impact, o.actual_cost_amount,
                   o.measured_at, o.next_recommendation, o.notes AS outcome_notes
            FROM action_queue q
            LEFT JOIN action_outcomes o ON o.action_id = q.id
            WHERE q.id = ?
        """, (action_id,))

        row = cursor.fetchone()
        return dict(row) if row else None


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
                       o.expected_outcome, o.expected_impact, o.expected_cost_amount, o.currency,
                       o.outcome_status, o.actual_outcome, o.actual_impact, o.actual_cost_amount,
                       o.measured_at, o.next_recommendation, o.notes AS outcome_notes
                FROM action_queue q
                LEFT JOIN action_outcomes o ON o.action_id = q.id
                WHERE q.status = ?
                ORDER BY q.timestamp DESC
                LIMIT ? OFFSET ?
            """, (status_filter, limit, offset))
        else:
            cursor.execute("""
                SELECT q.id, q.timestamp, q.proposed_by, q.action_description, q.action_detail,
                       q.status, q.reviewed_at, q.action_type, q.result_detail, q.sync_uuid,
                       o.expected_outcome, o.expected_impact, o.expected_cost_amount, o.currency,
                       o.outcome_status, o.actual_outcome, o.actual_impact, o.actual_cost_amount,
                       o.measured_at, o.next_recommendation, o.notes AS outcome_notes
                FROM action_queue q
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

        cursor.execute("SELECT * FROM decisions")
        decision_rows = [dict(row) for row in cursor.fetchall()]

        cursor.execute("SELECT * FROM action_queue")
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

    with open(export_path, "w", encoding="utf-8") as f:
        for row in decision_rows:
            row["_table"] = "decisions"
            f.write(json.dumps(row) + "\n")
        for row in action_rows:
            row["_table"] = "action_queue"
            f.write(json.dumps(row) + "\n")
        for row in outcome_rows:
            row["_table"] = "action_outcomes"
            f.write(json.dumps(row) + "\n")

    return {
        "decisions": len(decision_rows),
        "actions": len(action_rows),
        "outcomes": len(outcome_rows),
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

    imported_decisions = 0
    imported_actions = 0
    imported_outcomes = 0
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
                }[table]

                if (
                    not row
                    or any(column not in allowed_columns for column in row)
                    or not required_columns.issubset(row.keys())
                ):
                    skipped += 1
                    continue

                if table == "action_queue":
                    if row.get("status") not in VALID_ACTION_STATUSES:
                        skipped += 1
                        continue
                    if row.get("action_type") not in VALID_ACTION_TYPES:
                        skipped += 1
                        continue
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
                        "SELECT 1 FROM action_outcomes WHERE action_sync_uuid = ?",
                        (row.get("action_sync_uuid"),),
                    )
                    if cursor.fetchone():
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

                if table == "decisions":
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
                else:
                    imported_outcomes += 1

        conn.commit()

    return {
        "decisions_imported": imported_decisions,
        "actions_imported": imported_actions,
        "outcomes_imported": imported_outcomes,
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