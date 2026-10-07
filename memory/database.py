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

_SYNC_TABLE_COLUMNS = {
    "decisions": {
        "timestamp", "topic", "agents_involved", "task_description",
        "decision_outcome", "sandbox_mode", "sync_uuid",
    },
    "action_queue": {
        "timestamp", "proposed_by", "action_description", "action_detail",
        "status", "reviewed_at", "action_type", "result_detail", "sync_uuid",
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
        
        conn.commit()
        return cursor.lastrowid


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
            SELECT id, timestamp, topic, agents_involved, task_description, decision_outcome, sandbox_mode, sync_uuid
            FROM decisions
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


# ===================================================================
# FUNCTIES VOOR ACTIEVOORSTELLEN (ACTION QUEUE)
# ===================================================================

def propose_action(
    proposed_by: str, action_description: str, action_detail: str, action_type: str = "shell"
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
        
        conn.commit()
        return cursor.lastrowid


def get_pending_actions() -> list[dict]:
    """
    Haalt alle acties op met status 'pending', meest recente eerst.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, proposed_by, action_description, action_detail, status, reviewed_at, action_type, result_detail, sync_uuid
            FROM action_queue
            WHERE status IN ('pending', 'approved')
            ORDER BY timestamp DESC
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

def get_action_by_id(action_id: int) -> dict | None:
    """
    Haalt één specifieke actie op uit de action_queue op basis van het ID.
    Retourneert de actie als een dictionary, of None als het ID niet gevonden is.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, proposed_by, action_description, action_detail, status, reviewed_at, action_type, result_detail, sync_uuid
            FROM action_queue
            WHERE id = ?
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
                SELECT id, timestamp, proposed_by, action_description, action_detail, status, reviewed_at, action_type, result_detail, sync_uuid
                FROM action_queue
                WHERE status = ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            """, (status_filter, limit, offset))
        else:
            cursor.execute("""
                SELECT id, timestamp, proposed_by, action_description, action_detail, status, reviewed_at, action_type, result_detail, sync_uuid
                FROM action_queue
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]


# ===================================================================
# CROSS-MACHINE SYNC (export/import als JSON Lines)
# ===================================================================
# SQLite zelf blijft bewust buiten git (binair, merget niet netjes). In
# plaats daarvan: exporteer beide tabellen als JSON Lines (één JSON-object
# per regel — merget WEL netjes via git, want elke regel is onafhankelijk)
# naar een git-getrackt bestand. sync_uuid is de stabiele identiteit van elke
# rij over machines heen — de lokale autoincrement 'id' verschilt per
# database en mag NOOIT gebruikt worden om te bepalen of een rij al bestaat.
#
# Gebruik (handmatig, bewust geen automatische git push):
#   Op laptop A: python -c "from memory.database import export_history_to_jsonl; export_history_to_jsonl('sync/history_export.jsonl')"
#                git add sync/history_export.jsonl && git commit -m "Sync export" && git push
#   Op laptop B: git pull
#                python -c "from memory.database import import_history_from_jsonl; import_history_from_jsonl('sync/history_export.jsonl')"

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

    with open(export_path, "w", encoding="utf-8") as f:
        for row in decision_rows:
            row["_table"] = "decisions"
            f.write(json.dumps(row) + "\n")
        for row in action_rows:
            row["_table"] = "action_queue"
            f.write(json.dumps(row) + "\n")

    return {"decisions": len(decision_rows), "actions": len(action_rows)}


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
    skipped = 0

    with get_connection() as conn:
        cursor = conn.cursor()

        with open(import_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
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
                if not row or any(column not in allowed_columns for column in row):
                    skipped += 1
                    continue

                if table == "action_queue":
                    if row.get("status") not in VALID_ACTION_STATUSES:
                        skipped += 1
                        continue
                    if row.get("action_type") not in VALID_ACTION_TYPES:
                        skipped += 1
                        continue

                cursor.execute(f"SELECT 1 FROM {table} WHERE sync_uuid = ?", (sync_uuid_value,))
                if cursor.fetchone():
                    skipped += 1
                    continue

                # table en columns komen vanaf hier uitsluitend uit vaste
                # whitelists hierboven, niet uit onbetrouwbare input.
                columns = ", ".join(row.keys())
                placeholders = ", ".join(["?"] * len(row))
                cursor.execute(
                    f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
                    tuple(row.values())
                )

                if table == "decisions":
                    imported_decisions += 1
                else:
                    imported_actions += 1

        conn.commit()

    return {
        "decisions_imported": imported_decisions,
        "actions_imported": imported_actions,
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