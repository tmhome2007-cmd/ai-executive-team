"""Owner classifications and frozen research contexts. Neither verifies demand."""

import datetime
import json
from memory.database import get_connection
from memory.experiments import _text

CATEGORIES = {"unknown", "demand", "buyer", "platform", "constraint", "contradiction"}
SERVICES = {"documentation", "editing", "support_drafts"}


def init_business_evidence(cursor):
    cursor.execute("""CREATE TABLE IF NOT EXISTS business_source_annotations (
        id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL, version INTEGER NOT NULL,
        category TEXT NOT NULL, services_json TEXT NOT NULL, publication_date TEXT,
        note TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(source_id,version))""")
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS business_research_contexts (
        brief_id INTEGER PRIMARY KEY, context_json TEXT NOT NULL, created_at TEXT NOT NULL)"""
    )
    for table in ("business_source_annotations", "business_research_contexts"):
        for op in ("UPDATE", "DELETE"):
            cursor.execute(
                f"CREATE TRIGGER IF NOT EXISTS {table}_no_{op.lower()} BEFORE {op} ON {table} BEGIN SELECT RAISE(ABORT,'Research provenance is retained'); END"
            )  # nosec B608 # Fixed literal identifiers.


def annotation(cursor, source_id):
    row = cursor.execute(
        "SELECT * FROM business_source_annotations WHERE source_id=? ORDER BY version DESC LIMIT 1",
        (source_id,),
    ).fetchone()
    if not row:
        return dict(
            source_id=source_id,
            version=0,
            category="unknown",
            services=[],
            publication_date=None,
            note="",
        )
    value = dict(row)
    value["services"] = json.loads(value.pop("services_json"))
    return value


def publication_age(value, now=None):
    """Age of a date-only publication, allowing today's calendar date worldwide.

    A publication date has no time or timezone. UTC+14 can already be tomorrow;
    accepting that date avoids rejecting genuine local-day records around midnight.
    This is a calendar bound, never independent verification of the source.
    """
    try:
        date = datetime.date.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    now = now or datetime.datetime.now(datetime.timezone.utc)
    now = now.astimezone(datetime.timezone.utc)
    latest_calendar_date = (now + datetime.timedelta(hours=14)).date()
    if date > latest_calendar_date:
        return None
    return max(0, (now.date() - date).days)


def classify_source(
    source_id, expected_version, category, services, publication_date=None, note=""
):
    if (
        type(expected_version) is not int
        or not 0 <= expected_version < 9223372036854775807
    ):
        raise ValueError("Invalid classification version")
    if (
        category not in CATEGORIES
        or not isinstance(services, list)
        or len(services) > 3
        or any(s not in SERVICES for s in services)
        or len(set(services)) != len(services)
    ):
        raise ValueError("Invalid source classification")
    if publication_date:
        try:
            date = datetime.date.fromisoformat(publication_date)
        except (ValueError, TypeError):
            raise ValueError("Publication date must be YYYY-MM-DD") from None
        if publication_age(date.isoformat()) is None:
            raise ValueError("Publication date cannot be in the future")
        publication_date = date.isoformat()
    note = _text(note, "classification note", 1000, False)
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if not conn.execute(
            "SELECT id FROM evidence_sources WHERE id=?", (source_id,)
        ).fetchone():
            raise LookupError("Source not found")
        if annotation(conn.cursor(), source_id)["version"] != expected_version:
            raise RuntimeError("Classification changed; refresh")
        conn.execute(
            """INSERT INTO business_source_annotations(source_id,version,category,services_json,publication_date,note,created_at)
            VALUES(?,?,?,?,?,?,?)""",
            (
                source_id,
                expected_version + 1,
                category,
                json.dumps(services),
                publication_date,
                note,
                datetime.datetime.now(datetime.timezone.utc).isoformat(),
            ),
        )
        result = annotation(conn.cursor(), source_id)
        conn.commit()
    return result


def business_sources(source_ids):
    from memory.evidence import get_source

    values = [get_source(i) for i in source_ids]
    if any(s is None for s in values):
        raise LookupError("Source not found")
    with get_connection() as conn:
        for source in values:
            source["business_context"] = annotation(conn.cursor(), source["id"])
    return values


def freeze_context(cursor, brief_id, source_ids):
    from memory.evidence import _source

    values = []
    for ident in source_ids:
        row = cursor.execute(
            "SELECT * FROM evidence_sources WHERE id=?", (ident,)
        ).fetchone()
        if not row:
            raise LookupError("Source not found")
        source = _source(row)
        source["business_context"] = annotation(cursor, ident)
        values.append(source)
    cursor.execute(
        "INSERT INTO business_research_contexts VALUES(?,?,?)",
        (
            brief_id,
            json.dumps(values),
            datetime.datetime.now(datetime.timezone.utc).isoformat(),
        ),
    )


def research_context(cursor, brief_id):
    row = cursor.execute(
        "SELECT context_json FROM business_research_contexts WHERE brief_id=?",
        (brief_id,),
    ).fetchone()
    return json.loads(row[0]) if row else []
