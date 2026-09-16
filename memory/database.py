"""
memory/database.py

SQLite-opslaglaag voor het opslaan en ophalen van beslissingen 
en actievoorstellen van het AI Executive Team.
"""

import os
import sqlite3
import datetime
import sys
from pathlib import Path
from contextlib import contextmanager

# Zorg ervoor dat de hoofdmap van het project bereikbaar is voor imports
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from config import config


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
            sandbox_mode INTEGER NOT NULL
        )
    """)

    # Tabel 2: Action Approval Queue
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS action_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            proposed_by TEXT NOT NULL,
            action_description TEXT NOT NULL,
            action_detail TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            reviewed_at TEXT
        )
    """)
    
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

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO decisions (
                timestamp, topic, agents_involved, task_description, decision_outcome, sandbox_mode
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (timestamp, topic, agents_str, task_description, decision_outcome, sandbox_flag))
        
        conn.commit()
        return cursor.lastrowid


def get_recent_decisions(limit: int = 10) -> list[dict]:
    """
    Haalt de meest recente beslissingen op, gesorteerd op datum (nieuwste eerst).
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, topic, agents_involved, task_description, decision_outcome, sandbox_mode
            FROM decisions
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


# ===================================================================
# FUNCTIES VOOR ACTIEVOORSTELLEN (ACTION QUEUE)
# ===================================================================

def propose_action(proposed_by: str, action_description: str, action_detail: str) -> int:
    """
    Voegt een voorgestelde actie toe aan de action_queue met de status 'pending'.
    Retourneert het gegenereerde rij-ID.
    """
    timestamp = datetime.datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO action_queue (timestamp, proposed_by, action_description, action_detail, status)
            VALUES (?, ?, ?, ?, 'pending')
        """, (timestamp, proposed_by, action_description, action_detail))
        
        conn.commit()
        return cursor.lastrowid


def get_pending_actions() -> list[dict]:
    """
    Haalt alle acties op met status 'pending', meest recente eerst.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, proposed_by, action_description, action_detail, status, reviewed_at
            FROM action_queue
            WHERE status = 'pending'
            ORDER BY timestamp DESC
        """)
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def update_action_status(action_id: int, new_status: str) -> bool:
    """
    Werkt de status van een actie bij (bijv. 'approved', 'rejected', 'executed')
    en zet reviewed_at op het huidige tijdstip.
    Retourneert True als de rij succesvol is bijgewerkt, anders False.
    """
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

def get_action_by_id(action_id: int) -> dict | None:
    """
    Haalt één specifieke actie op uit de action_queue op basis van het ID.
    Retourneert de actie als een dictionary, of None als het ID niet gevonden is.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, proposed_by, action_description, action_detail, status, reviewed_at
            FROM action_queue
            WHERE id = ?
        """, (action_id,))
        
        row = cursor.fetchone()
        return dict(row) if row else None


# ===================================================================
# HANDMATIGE TEST / DIRECTE UITVOERING
# ===================================================================

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