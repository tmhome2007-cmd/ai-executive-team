"""Proposed public URLs stay separate from fetched evidence and owner classifications."""

import datetime
import ipaddress
from urllib.parse import urlsplit, urlunsplit
from memory.database import get_connection
from memory.experiments import _text
from memory.evidence import register_source

CATEGORIES = {"unknown", "buyer", "demand", "platform", "constraint", "contradiction"}


def public_url(value):
    """Static URL checks never fetch or resolve a proposal; reader rechecks DNS."""
    value = _text(value, "public URL", 1000)
    try:
        parsed = urlsplit(value)
        port = parsed.port
        host = parsed.hostname
    except ValueError:
        raise ValueError("Invalid public URL") from None
    if (
        parsed.scheme not in {"http", "https"}
        or not host
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or port not in {None, 80, 443}
        or any(ord(c) < 33 for c in value)
    ):
        raise ValueError(
            "Use a public HTTP(S) URL without credentials, query or fragment"
        )
    host = host.lower().rstrip(".")
    if (
        "." not in host
        or host.endswith(
            (".local", ".localhost", ".internal", ".example", ".invalid", ".test")
        )
        or host in {"example.com", "example.org", "example.net"}
    ):
        raise ValueError(
            "Use an actual public source, not a private or placeholder host"
        )
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Private IP sources are forbidden")
    return urlunsplit(
        (parsed.scheme, parsed.netloc.lower(), parsed.path or "/", "", "")
    )


def init_queue(cursor):
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS research_source_queue (
        id INTEGER PRIMARY KEY,url TEXT NOT NULL,purpose TEXT NOT NULL,proposed_category TEXT NOT NULL,
        origin_brief_id INTEGER,state TEXT NOT NULL DEFAULT 'proposed',version INTEGER NOT NULL DEFAULT 1,
        source_id INTEGER,checkpoint_step TEXT,error_category TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,updated_at TEXT NOT NULL)"""
    )
    cursor.execute(
        """CREATE TRIGGER IF NOT EXISTS source_queue_identity_no_rewrite BEFORE UPDATE ON research_source_queue
        WHEN OLD.url IS NOT NEW.url OR OLD.purpose IS NOT NEW.purpose OR OLD.proposed_category IS NOT NEW.proposed_category OR OLD.origin_brief_id IS NOT NEW.origin_brief_id
        BEGIN SELECT RAISE(ABORT,'Source proposal identity is immutable'); END"""
    )
    cursor.execute(
        "CREATE TRIGGER IF NOT EXISTS source_queue_no_delete BEFORE DELETE ON research_source_queue BEGIN SELECT RAISE(ABORT,'Source proposal history is retained'); END"
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS active_source_proposal_url ON research_source_queue(url) WHERE state IN ('proposed','fetching','needs_review','failed')"
    )


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _get(cursor, ident):
    row = cursor.execute(
        "SELECT * FROM research_source_queue WHERE id=?", (ident,)
    ).fetchone()
    if not row:
        raise LookupError("Source proposal not found")
    result = dict(row)
    result["counts_as_evidence"] = (
        result["state"] == "fetched" and result["source_id"] is not None
    )
    from memory.business_evidence import annotation

    result["source_category"] = (
        annotation(cursor, result["source_id"])["category"]
        if result["source_id"] is not None
        else None
    )
    result["scope"] = (
        "Proposed category is a hypothesis; fetched source still needs owner classification and is unverified."
    )
    return result


def get_proposal(ident):
    with get_connection() as conn:
        return _get(conn.cursor(), ident)


def list_proposals(limit=50, offset=0):
    with get_connection() as conn:
        ids = [
            r[0]
            for r in conn.execute(
                "SELECT id FROM research_source_queue ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        ]
        return [_get(conn.cursor(), i) for i in ids]


def propose_source(
    url, purpose, proposed_category="unknown", origin_brief_id=None, new_snapshot=False
):
    url = public_url(url)
    purpose = _text(purpose, "research purpose", 1000)
    if proposed_category not in CATEGORIES:
        raise ValueError("Invalid proposed evidence category")
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if (
            origin_brief_id is not None
            and not conn.execute(
                "SELECT id FROM business_discovery WHERE id=?", (origin_brief_id,)
            ).fetchone()
        ):
            raise LookupError("Origin brief not found")
        existing = conn.execute(
            "SELECT id FROM research_source_queue WHERE url=? AND (?=0 OR state!='fetched') ORDER BY id DESC LIMIT 1",
            (url, int(new_snapshot)),
        ).fetchone()
        if existing:
            return _get(conn.cursor(), existing[0])
        now = _now()
        row = conn.execute(
            "INSERT INTO research_source_queue(url,purpose,proposed_category,origin_brief_id,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (url, purpose, proposed_category, origin_brief_id, now, now),
        )
        ident = row.lastrowid
        conn.commit()
    return get_proposal(ident)


def claim_read(ident, expected_version):
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = _get(conn.cursor(), ident)
        if row["state"] == "fetched":
            return row
        if row["version"] != expected_version or row["state"] not in {
            "proposed",
            "failed",
            "needs_review",
        }:
            raise RuntimeError(
                "Source read already started or proposal changed; refresh"
            )
        step = f"read:{expected_version+1}"
        conn.execute(
            "UPDATE research_source_queue SET state='fetching',version=version+1,checkpoint_step=?,error_category='',updated_at=? WHERE id=?",
            (step, _now(), ident),
        )
        conn.commit()
    result = get_proposal(ident)
    result["previous_checkpoint_step"] = row["checkpoint_step"]
    return result


def finish_read(ident, claimed_version, payload=None):
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = _get(conn.cursor(), ident)
        if row["version"] != claimed_version or row["state"] != "fetching":
            raise RuntimeError("Source read ownership changed; refresh")
        if payload is None:
            conn.execute(
                "UPDATE research_source_queue SET state='failed',error_category='read_failed',version=version+1,updated_at=? WHERE id=?",
                (_now(), ident),
            )
        else:
            if not isinstance(payload, dict) or payload.get("reference") != row["url"]:
                raise ValueError("Fetched source does not match queued URL")
            fields = dict(payload)
            fields["source_key"] = f"research-queue:{ident}"
            source_id = register_source(conn.cursor(), **fields)
            conn.execute(
                "UPDATE research_source_queue SET state='fetched',source_id=?,version=version+1,updated_at=?,error_category='' WHERE id=?",
                (source_id, _now(), ident),
            )
        conn.commit()
    return get_proposal(ident)


def recover_queue():
    with get_connection() as conn:
        conn.execute(
            "UPDATE research_source_queue SET state='needs_review',version=version+1,error_category='interrupted',updated_at=? WHERE state='fetching'",
            (_now(),),
        )
        conn.commit()
