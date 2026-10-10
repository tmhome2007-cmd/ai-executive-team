"""Dated source provenance. Registration or owner confirmation is not independent verification."""

import datetime
from urllib.parse import urlsplit
from memory.database import get_connection
from memory.experiments import _text, _date


def init_evidence(cursor):
    cursor.execute("""CREATE TABLE IF NOT EXISTS evidence_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_key TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL, reference TEXT NOT NULL, summary TEXT NOT NULL,
        observed_at TEXT NOT NULL, expires_at TEXT, source_kind TEXT NOT NULL,
        verification TEXT NOT NULL DEFAULT 'unverified', created_at TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS evidence_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_id INTEGER NOT NULL,
        entity_kind TEXT NOT NULL, entity_id INTEGER NOT NULL, relation TEXT NOT NULL,
        claim TEXT NOT NULL, created_at TEXT NOT NULL,
        UNIQUE(source_id, entity_kind, entity_id, relation, claim)
    )""")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS evidence_entity ON evidence_links(entity_kind, entity_id)"
    )
    cursor.execute(
        """CREATE TRIGGER IF NOT EXISTS evidence_no_rewrite BEFORE UPDATE ON evidence_sources
        WHEN OLD.source_key IS NOT NEW.source_key OR OLD.title IS NOT NEW.title OR
        OLD.reference IS NOT NEW.reference OR OLD.summary IS NOT NEW.summary OR
        OLD.observed_at IS NOT NEW.observed_at OR OLD.expires_at IS NOT NEW.expires_at OR
        OLD.source_kind IS NOT NEW.source_kind
        BEGIN SELECT RAISE(ABORT, 'Source contents are immutable; register a correction'); END"""
    )
    cursor.execute(
        """CREATE TRIGGER IF NOT EXISTS evidence_no_delete BEFORE DELETE ON evidence_sources
        BEGIN SELECT RAISE(ABORT, 'Source provenance is retained'); END"""
    )
    for operation in ("UPDATE", "DELETE"):
        cursor.execute(
            f"CREATE TRIGGER IF NOT EXISTS evidence_link_no_{operation.lower()} BEFORE {operation} ON evidence_links BEGIN SELECT RAISE(ABORT, 'Evidence links are retained'); END"
        )  # nosec B608 # Literal UPDATE/DELETE only.


def register_source(
    cursor,
    *,
    source_key,
    title,
    reference,
    summary,
    observed_at,
    expires_at=None,
    source_kind="owner_record",
):
    source_key = _text(source_key, "source key", 120)
    title = _text(title, "source title", 200)
    reference = _text(reference, "source reference", 1000)
    summary = _text(summary, "source summary", 12000)
    if "://" in reference:
        parsed = urlsplit(reference)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "Source URL must use HTTP(S) without credentials, query or fragment; URLs are never fetched"
            )
    if source_kind not in {
        "owner_record",
        "owner_context",
        "observation",
        "document",
        "external_reference",
    }:
        raise ValueError("Invalid source kind")
    observed_at = _date(observed_at, "observed_at")
    now = datetime.datetime.now(datetime.timezone.utc)
    if datetime.datetime.fromisoformat(
        observed_at.replace("Z", "+00:00")
    ) > now + datetime.timedelta(seconds=60):
        raise ValueError("Source observation cannot be in the future")
    if expires_at is not None:
        expires_at = _date(expires_at, "expires_at")
        if datetime.datetime.fromisoformat(
            expires_at.replace("Z", "+00:00")
        ) < datetime.datetime.fromisoformat(observed_at.replace("Z", "+00:00")):
            raise ValueError("Source expiry predates its observation")
    expected = dict(
        title=title,
        reference=reference,
        summary=summary,
        observed_at=observed_at,
        expires_at=expires_at,
        source_kind=source_kind,
    )
    row = cursor.execute(
        "SELECT * FROM evidence_sources WHERE source_key = ?", (source_key,)
    ).fetchone()
    if row:
        if any(row[k] != v for k, v in expected.items()):
            raise RuntimeError("Source key reused with different contents")
        return row["id"]
    cursor.execute(
        """INSERT INTO evidence_sources(source_key, title, reference, summary, observed_at, expires_at, source_kind, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            source_key,
            title,
            reference,
            summary,
            observed_at,
            expires_at,
            source_kind,
            now.isoformat(),
        ),
    )
    return cursor.lastrowid


def create_source(**fields):
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        ident = register_source(conn.cursor(), **fields)
        conn.commit()
    return get_source(ident)


def _source(row):
    item = dict(row)
    now = datetime.datetime.now(datetime.timezone.utc)
    item["freshness"] = (
        "unknown"
        if item["expires_at"] is None
        else (
            "stale"
            if datetime.datetime.fromisoformat(
                item["expires_at"].replace("Z", "+00:00")
            )
            <= now
            else "current"
        )
    )
    item["provenance_scope"] = (
        "Registered source; owner confirmation is not independent verification"
    )
    return item


def get_source(ident):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM evidence_sources WHERE id = ?", (ident,)
        ).fetchone()
        return _source(row) if row else None


def list_sources(limit=50, offset=0):
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError("Invalid evidence pagination")
    with get_connection() as conn:
        return [
            _source(r)
            for r in conn.execute(
                "SELECT * FROM evidence_sources ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        ]


def review_source(ident, expected_version, verification):
    if verification not in {"unverified", "owner_confirmed", "disputed"}:
        raise ValueError("Invalid source verification state")
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM evidence_sources WHERE id = ?", (ident,)
        ).fetchone()
        if not row:
            raise LookupError("Source not found")
        if row["version"] != expected_version:
            raise RuntimeError("Source changed; refresh before review")
        conn.execute(
            "UPDATE evidence_sources SET verification = ?, version = version + 1 WHERE id = ? AND version = ?",
            (verification, ident, expected_version),
        )
        conn.commit()
    return get_source(ident)


def link_source(
    cursor, source_id, entity_kind, entity_id, relation="context", claim=""
):
    if relation not in {"context", "supports", "contradicts"}:
        raise ValueError("Invalid evidence relation")
    claim = _text(claim, "claim", 2000, required=False)
    if not cursor.execute(
        "SELECT id FROM evidence_sources WHERE id = ?", (source_id,)
    ).fetchone():
        raise LookupError("Source not found")
    queries = {
        "decision": "SELECT id FROM decisions WHERE id = ?",
        "observation": "SELECT id FROM experiment_observations WHERE id = ?",
        "discussion": "SELECT id FROM discussion_messages WHERE id = ?",
    }
    if (
        entity_kind not in queries
        or not cursor.execute(queries[entity_kind], (entity_id,)).fetchone()
    ):
        raise ValueError("Evidence target not found")
    cursor.execute(
        """INSERT OR IGNORE INTO evidence_links(source_id, entity_kind, entity_id, relation, claim, created_at)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (
            source_id,
            entity_kind,
            entity_id,
            relation,
            claim,
            datetime.datetime.now(datetime.timezone.utc).isoformat(),
        ),
    )


def add_evidence_link(**fields):
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        link_source(conn.cursor(), **fields)
        conn.commit()
    return entity_evidence(fields["entity_kind"], fields["entity_id"])


def entity_evidence(entity_kind, entity_id):
    queries = {
        "decision": "SELECT id FROM decisions WHERE id = ?",
        "observation": "SELECT id FROM experiment_observations WHERE id = ?",
        "discussion": "SELECT id FROM discussion_messages WHERE id = ?",
    }
    if entity_kind not in queries:
        raise ValueError("Invalid evidence target")
    with get_connection() as conn:
        if not conn.execute(queries[entity_kind], (entity_id,)).fetchone():
            raise LookupError("Evidence target not found")
        rows = conn.execute(
            """SELECT s.*, l.relation, l.claim FROM evidence_links l JOIN evidence_sources s ON s.id = l.source_id
            WHERE l.entity_kind = ? AND l.entity_id = ? ORDER BY l.id LIMIT 101""",
            (entity_kind, entity_id),
        ).fetchall()
        counts = conn.execute(
            """SELECT COUNT(*) AS total, SUM(CASE WHEN relation = 'contradicts' THEN 1 ELSE 0 END) AS conflicts, SUM(CASE WHEN relation = 'supports' THEN 1 ELSE 0 END) AS supporting
            FROM evidence_links WHERE entity_kind = ? AND entity_id = ?""",
            (entity_kind, entity_id),
        ).fetchone()
    items = [_source(r) for r in rows[:100]]
    return {
        "items": items,
        "missing": counts["total"] == 0,
        "conflicting": bool(counts["conflicts"]),
        "no_supporting_evidence": not counts["supporting"],
        "truncated": len(rows) > 100,
        "scope": "Owner-linked evidence; no automatic corroboration or source fetching",
    }


def source_context(source_ids):
    if (
        not isinstance(source_ids, list)
        or len(source_ids) > 20
        or any(type(i) is not int or i < 1 for i in source_ids)
        or len(set(source_ids)) != len(source_ids)
    ):
        raise ValueError("Invalid source IDs")
    sources = [get_source(i) for i in source_ids]
    if any(s is None for s in sources):
        raise LookupError("Source not found")
    return "\n".join(
        f"Source #{s['id']}: {s['title']} · observed {s['observed_at']} · {s['freshness']} · {s['verification']}\n{s['summary']}"
        for s in sources
    )
