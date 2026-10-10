"""Owner-enabled fictional social records; never business evidence or approval input."""

import datetime
from memory.database import get_connection
from memory.experiments import _text, _date
from memory.character_profiles import character_exists

KINDS = {
    "friendship",
    "dating",
    "marriage",
    "separation",
    "divorce",
    "hobby",
    "milestone",
}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def init_simulation(cursor):
    cursor.execute("""CREATE TABLE IF NOT EXISTS simulation_settings (
        id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL DEFAULT 0,
        version INTEGER NOT NULL DEFAULT 1, note TEXT NOT NULL DEFAULT '')""")
    cursor.execute("INSERT OR IGNORE INTO simulation_settings(id) VALUES(1)")
    cursor.execute("""CREATE TABLE IF NOT EXISTS personal_relationships (
        id INTEGER PRIMARY KEY, left_key TEXT NOT NULL, right_key TEXT NOT NULL,
        state TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
        CHECK(left_key<right_key), UNIQUE(left_key,right_key))""")
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS personal_events (
        id INTEGER PRIMARY KEY, event_key TEXT NOT NULL UNIQUE, kind TEXT NOT NULL,
        character_key TEXT NOT NULL, partner_key TEXT, narrative TEXT NOT NULL,
        simulated_at TEXT NOT NULL, recorded_at TEXT NOT NULL,
        expected_relationship_version INTEGER NOT NULL,
        relationship_id INTEGER, resulting_state TEXT, fictional INTEGER NOT NULL DEFAULT 1 CHECK(fictional=1))"""
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS personal_character ON personal_events(character_key,partner_key,id)"
    )
    for operation in ("UPDATE", "DELETE"):
        cursor.execute(
            f"CREATE TRIGGER IF NOT EXISTS personal_event_no_{operation.lower()} BEFORE {operation} ON personal_events BEGIN SELECT RAISE(ABORT,'Fictional history is retained'); END"
        )  # nosec B608 # Literal operations.


def settings():
    with get_connection() as conn:
        row = dict(
            conn.execute("SELECT * FROM simulation_settings WHERE id=1").fetchone()
        )
    return {
        **row,
        "enabled": bool(row["enabled"]),
        "scope": "Fictional only; no business evidence, budget or authority effects",
    }


def set_enabled(expected_version, enabled, note):
    if type(enabled) is not bool or type(expected_version) is not int:
        raise ValueError("Invalid simulation settings")
    note = _text(note, "simulation policy note", 2000)
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT version FROM simulation_settings WHERE id=1"
        ).fetchone()
        if row["version"] != expected_version:
            raise RuntimeError("Simulation settings changed; refresh")
        conn.execute(
            "UPDATE simulation_settings SET enabled=?,note=?,version=version+1 WHERE id=1",
            (int(enabled), note),
        )
        conn.commit()
    return settings()


def relationship(left, right):
    if not isinstance(left, str) or not isinstance(right, str) or left == right:
        raise ValueError("Choose two distinct adult fictional characters")
    left, right = sorted((left, right))
    with get_connection() as conn:
        if not character_exists(conn.cursor(), left) or not character_exists(
            conn.cursor(), right
        ):
            raise LookupError("Character not found")
        row = conn.execute(
            "SELECT * FROM personal_relationships WHERE left_key=? AND right_key=?",
            (left, right),
        ).fetchone()
    return (
        {**dict(row), "fictional": True}
        if row
        else dict(
            left_key=left, right_key=right, state="none", version=0, fictional=True
        )
    )


def record_personal_event(
    *,
    event_key,
    kind,
    character_key,
    partner_key=None,
    narrative,
    simulated_at,
    expected_relationship_version=0,
):
    event_key = _text(event_key, "personal event key", 80)
    narrative = _text(narrative, "fictional narrative", 2000)
    simulated_at = _date(simulated_at, "simulated time")
    if (
        type(expected_relationship_version) is not int
        or expected_relationship_version < 0
    ):
        raise ValueError("Invalid relationship version")
    if not isinstance(kind, str) or kind not in KINDS:
        raise ValueError("Invalid fictional event type")
    relational = kind in {"friendship", "dating", "marriage", "separation", "divorce"}
    if relational and (
        not isinstance(partner_key, str) or partner_key == character_key
    ):
        raise ValueError("Relationship events need a distinct adult fictional partner")
    if not relational and (
        partner_key is not None or expected_relationship_version != 0
    ):
        raise ValueError("Personal milestones/hobbies concern one character")
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if not character_exists(conn.cursor(), character_key):
            raise LookupError("Character not found")
        if partner_key is not None and not character_exists(conn.cursor(), partner_key):
            raise LookupError("Partner not found")
        original = conn.execute(
            "SELECT * FROM personal_events WHERE event_key=?", (event_key,)
        ).fetchone()
        fields = dict(
            kind=kind,
            character_key=character_key,
            partner_key=partner_key,
            narrative=narrative,
            simulated_at=simulated_at,
            expected_relationship_version=expected_relationship_version,
        )
        if original:
            if any(original[k] != v for k, v in fields.items()):
                raise RuntimeError("Event key reused with different fictional inputs")
            return dict(original)
        if not conn.execute(
            "SELECT enabled FROM simulation_settings WHERE id=1"
        ).fetchone()[0]:
            raise ValueError(
                "Enable fictional personal simulation before recording events"
            )
        # Retired/suspended characters retain history but cannot receive new simulated events.
        if not character_exists(conn.cursor(), character_key, True) or (
            partner_key and not character_exists(conn.cursor(), partner_key, True)
        ):
            raise ValueError(
                "Only active fictional characters participate in new events"
            )
        relationship_id = None
        new_state = None
        if relational:
            left, right = sorted((character_key, partner_key))
            row = conn.execute(
                "SELECT * FROM personal_relationships WHERE left_key=? AND right_key=?",
                (left, right),
            ).fetchone()
            version = row["version"] if row else 0
            state = row["state"] if row else "none"
            if version != expected_relationship_version:
                raise RuntimeError("Relationship changed; refresh")
            if row:
                previous = conn.execute(
                    "SELECT simulated_at FROM personal_events WHERE relationship_id=? ORDER BY id DESC LIMIT 1",
                    (row["id"],),
                ).fetchone()
                if previous and datetime.datetime.fromisoformat(
                    simulated_at.replace("Z", "+00:00")
                ) < datetime.datetime.fromisoformat(
                    previous["simulated_at"].replace("Z", "+00:00")
                ):
                    raise ValueError(
                        "Relationship events must follow the existing fictional chronology"
                    )
            allowed = {
                "friendship": {"none", "dating", "divorced"},
                "dating": {"none", "friends", "divorced"},
                "marriage": {"dating"},
                "separation": {"married"},
                "divorce": {"married", "separated"},
            }
            if state not in allowed[kind]:
                raise ValueError("Invalid fictional relationship transition")
            if kind == "marriage":
                if conn.execute(
                    "SELECT 1 FROM personal_relationships WHERE state IN ('married','separated') AND (left_key IN (?,?) OR right_key IN (?,?))",
                    (left, right, left, right),
                ).fetchone():
                    raise ValueError(
                        "Resolve the existing marriage before another fictional marriage"
                    )
            new_state = {
                "friendship": "friends",
                "dating": "dating",
                "marriage": "married",
                "separation": "separated",
                "divorce": "divorced",
            }[kind]
            if row:
                relationship_id = row["id"]
                conn.execute(
                    "UPDATE personal_relationships SET state=?,version=version+1 WHERE id=?",
                    (new_state, relationship_id),
                )
            else:
                relationship_id = conn.execute(
                    "INSERT INTO personal_relationships(left_key,right_key,state) VALUES(?,?,?)",
                    (left, right, new_state),
                ).lastrowid
        ident = conn.execute(
            "INSERT INTO personal_events(event_key,kind,character_key,partner_key,narrative,simulated_at,recorded_at,expected_relationship_version,relationship_id,resulting_state) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                event_key,
                kind,
                character_key,
                partner_key,
                narrative,
                simulated_at,
                now(),
                expected_relationship_version,
                relationship_id,
                new_state,
            ),
        ).lastrowid
        result = dict(
            conn.execute(
                "SELECT * FROM personal_events WHERE id=?", (ident,)
            ).fetchone()
        )
        conn.commit()
    return result


def events(limit=50, offset=0):
    if (
        type(limit) is not int
        or not 1 <= limit <= 100
        or type(offset) is not int
        or offset < 0
    ):
        raise ValueError("Invalid pagination")
    with get_connection() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM personal_events ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        ]
