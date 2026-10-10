"""Versioned private text procedures grounded in owner reviews, never tool authority."""

import datetime
import json
import re
from memory.database import get_connection
from memory.experiments import _text

SCOPE = "Reviewed private text procedure only; no tool, spending, publication or launch authority. Not model training or general competence."


def init_skills(cursor):
    """Add immutable definitions/bindings and append-only owner state decisions."""
    cursor.execute("""CREATE TABLE IF NOT EXISTS executive_skill_versions (
        id INTEGER PRIMARY KEY, skill_key TEXT NOT NULL, version INTEGER NOT NULL,
        name TEXT NOT NULL, procedure TEXT NOT NULL, prerequisites TEXT NOT NULL,
        limitations TEXT NOT NULL, evidence_json TEXT NOT NULL, rubric_digest TEXT NOT NULL,
        service_key TEXT NOT NULL, deliverable_kind TEXT NOT NULL, checks_json TEXT NOT NULL,
        created_at TEXT NOT NULL, UNIQUE(skill_key,version))""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS executive_skill_decisions (
        id INTEGER PRIMARY KEY, skill_id INTEGER NOT NULL, version INTEGER NOT NULL,
        state TEXT NOT NULL, note TEXT NOT NULL, recorded_at TEXT NOT NULL,
        UNIQUE(skill_id,version))""")
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS practice_skill_bindings (
        brief_id INTEGER PRIMARY KEY, skill_id INTEGER NOT NULL, created_at TEXT NOT NULL)"""
    )
    for table in (
        "executive_skill_versions",
        "executive_skill_decisions",
        "practice_skill_bindings",
    ):
        for op in ("UPDATE", "DELETE"):
            cursor.execute(
                f"CREATE TRIGGER IF NOT EXISTS {table}_no_{op.lower()} BEFORE {op} ON {table} BEGIN SELECT RAISE(ABORT,'Skill records are append-only'); END"
            )  # nosec B608 # Literal identifiers only.


def _review(cursor, review_id):
    """Require the latest assessment bound to this exact structured sample."""
    row = cursor.execute(
        """SELECT r.id review_id,r.sample_id,r.review_json,s.brief_id,s.sample,
        p.rubric_digest,p.specification_json,p.structured,b.title
        FROM business_practice_reviews r JOIN business_practice_samples s ON s.id=r.sample_id
        JOIN practice_sample_specifications ps ON ps.sample_id=s.id
        JOIN practice_review_specifications pr ON pr.review_id=r.id AND pr.specification_id=ps.specification_id
        JOIN practice_specifications p ON p.id=ps.specification_id
        JOIN business_discovery b ON b.id=s.brief_id WHERE r.id=?""",
        (review_id,),
    ).fetchone()
    if not row or not row["structured"]:
        raise ValueError("Use reviews bound to structured practice samples")
    latest = cursor.execute(
        "SELECT MAX(id) FROM business_practice_reviews WHERE sample_id=?",
        (row["sample_id"],),
    ).fetchone()[0]
    review = json.loads(row["review_json"])
    spec = json.loads(row["specification_json"])
    results = review.get("results")
    if (
        latest != review_id
        or not isinstance(results, list)
        or len(results) != len(spec["checks"])
        or not 2 <= len(results) <= 10
        or any(type(x) is not bool or not x for x in results)
        or review.get("assessment") != "practice_passed"
    ):
        raise ValueError(
            "Evidence requires the latest passing owner review for every check"
        )
    return dict(row, specification=spec)


def _evidence(cursor, review_ids):
    if (
        not isinstance(review_ids, list)
        or len(review_ids) != 2
        or any(
            type(x) is not int or not 1 <= x <= 9223372036854775807 for x in review_ids
        )
        or len(set(review_ids)) != 2
    ):
        raise ValueError("Select two distinct passing review records")
    rows = [_review(cursor, ident) for ident in review_ids]
    if (
        rows[0]["brief_id"] == rows[1]["brief_id"]
        or rows[0]["rubric_digest"] != rows[1]["rubric_digest"]
    ):
        raise ValueError("Use two separate exercises assessed with the same rubric")
    facts = [
        " ".join(row["specification"]["supplied_facts"].split()).casefold()
        for row in rows
    ]
    if facts[0] == facts[1]:
        raise ValueError(
            "Use different supplied facts, not repeated copies of one exercise"
        )
    return rows


def create_skill(skill_key, name, procedure, prerequisites, limitations, review_ids):
    """Propose a new immutable version; no automatic acceptance."""
    if not isinstance(skill_key, str) or not re.fullmatch(
        r"[a-z][a-z0-9-]{0,79}", skill_key
    ):
        raise ValueError("Use a short lowercase skill key")
    fields = [
        _text(name, "skill name", 200),
        _text(procedure, "procedure", 8000),
        _text(prerequisites, "prerequisites", 2000),
        _text(limitations, "limitations", 2000),
    ]
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        rows = _evidence(conn.cursor(), review_ids)
        version = conn.execute(
            "SELECT COALESCE(MAX(version),0)+1 FROM executive_skill_versions WHERE skill_key=?",
            (skill_key,),
        ).fetchone()[0]
        if (
            version > 20
            or conn.execute("SELECT COUNT(*) FROM executive_skill_versions").fetchone()[
                0
            ]
            >= 1000
        ):
            raise ValueError("Skill library size limit reached")
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        evidence = [
            {
                "review_id": row["review_id"],
                "sample_id": row["sample_id"],
                "brief_id": row["brief_id"],
            }
            for row in rows
        ]
        spec = rows[0]["specification"]
        ident = conn.execute(
            """INSERT INTO executive_skill_versions(skill_key,version,name,procedure,prerequisites,limitations,evidence_json,rubric_digest,service_key,deliverable_kind,checks_json,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                skill_key,
                version,
                *fields,
                json.dumps(evidence),
                rows[0]["rubric_digest"],
                spec["service_key"],
                spec["deliverable_kind"],
                json.dumps(spec["checks"]),
                now,
            ),
        ).lastrowid
        conn.execute(
            "INSERT INTO executive_skill_decisions(skill_id,version,state,note,recorded_at) VALUES(?,1,'proposed','Procedure awaiting owner acceptance',?)",
            (ident, now),
        )
        conn.commit()
    return get_skill(ident)


def _get(cursor, ident):
    if type(ident) is not int or not 1 <= ident <= 9223372036854775807:
        raise ValueError("Invalid skill identity")
    row = cursor.execute(
        "SELECT * FROM executive_skill_versions WHERE id=?", (ident,)
    ).fetchone()
    if not row:
        raise LookupError("Skill version not found")
    item = dict(row)
    item["evidence"] = json.loads(item.pop("evidence_json"))
    item["checks"] = json.loads(item.pop("checks_json"))
    decision = cursor.execute(
        "SELECT * FROM executive_skill_decisions WHERE skill_id=? ORDER BY version DESC LIMIT 1",
        (ident,),
    ).fetchone()
    item.update(
        state=decision["state"],
        state_version=decision["version"],
        decision_note=decision["note"],
        scope=SCOPE,
    )
    item["usable"] = False
    item["unavailable_reason"] = (
        "Owner acceptance required"
        if item["state"] == "proposed"
        else "Skill version revoked"
    )
    if item["state"] == "accepted":
        try:
            _evidence(cursor, [x["review_id"] for x in item["evidence"]])
            item.update(usable=True, unavailable_reason="")
        except ValueError:
            item["unavailable_reason"] = (
                "Source assessments changed; propose and review a new version"
            )
    uses = cursor.execute(
        "SELECT b.brief_id,d.state,d.review_json FROM practice_skill_bindings b JOIN business_discovery d ON d.id=b.brief_id WHERE b.skill_id=? ORDER BY b.brief_id DESC LIMIT 100",
        (ident,),
    ).fetchall()
    item["uses"] = [
        {
            "brief_id": use["brief_id"],
            "state": use["state"],
            "owner_assessment": (
                json.loads(use["review_json"]).get("assessment")
                if use["review_json"]
                else "not_assessed"
            ),
        }
        for use in uses
    ]
    return item


def get_skill(ident):
    with get_connection() as conn:
        conn.execute("BEGIN")
        return _get(conn.cursor(), ident)


def list_skills(limit=50, offset=0):
    if (
        type(limit) is not int
        or not 1 <= limit <= 100
        or type(offset) is not int
        or not 0 <= offset <= 9223372036854775807
    ):
        raise ValueError("Invalid skill page")
    with get_connection() as conn:
        conn.execute("BEGIN")
        ids = conn.execute(
            "SELECT id FROM executive_skill_versions ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [_get(conn.cursor(), row[0]) for row in ids]


def decide_skill(ident, expected_version, state, note):
    """Record owner acceptance or irreversible revocation with stale-update checks."""
    if (
        type(expected_version) is not int
        or expected_version < 1
        or state not in {"accepted", "revoked"}
    ):
        raise ValueError("Invalid skill decision")
    note = _text(note, "decision note", 2000)
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        skill = _get(conn.cursor(), ident)
        if (
            skill["state_version"] != expected_version
            or skill["state"] == "revoked"
            or (state == "accepted" and skill["state"] != "proposed")
        ):
            raise RuntimeError("Refresh; skill state changed or version is revoked")
        if state == "accepted":
            _evidence(conn.cursor(), [x["review_id"] for x in skill["evidence"]])
        conn.execute(
            "INSERT INTO executive_skill_decisions(skill_id,version,state,note,recorded_at) VALUES(?,?,?,?,?)",
            (
                ident,
                expected_version + 1,
                state,
                note,
                datetime.datetime.now(datetime.timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    return get_skill(ident)


def bind_skill(cursor, brief_id, skill_id):
    """Freeze a compatible accepted procedure into a third, distinct exercise."""
    from memory.practice_quality import specification

    skill = _get(cursor, skill_id)
    if not skill["usable"]:
        raise ValueError(skill["unavailable_reason"])
    spec = specification(cursor, brief_id)
    rows = _evidence(cursor, [x["review_id"] for x in skill["evidence"]])
    if (
        not spec
        or not spec["structured"]
        or spec["rubric_digest"] != skill["rubric_digest"]
    ):
        raise ValueError(
            "Reuse must preserve the accepted service, format and exact rubric"
        )
    facts = " ".join(spec["specification"]["supplied_facts"].split()).casefold()
    if brief_id in {x["brief_id"] for x in rows} or facts in {
        " ".join(x["specification"]["supplied_facts"].split()).casefold() for x in rows
    }:
        raise ValueError("Reuse requires a new exercise with different supplied facts")
    cursor.execute(
        "INSERT INTO practice_skill_bindings VALUES(?,?,?)",
        (brief_id, skill_id, datetime.datetime.now(datetime.timezone.utc).isoformat()),
    )


def skill_context(cursor, brief_id, require_usable=True):
    """Recheck revocation/corrected evidence at claims and publication boundaries."""
    row = cursor.execute(
        "SELECT skill_id FROM practice_skill_bindings WHERE brief_id=?", (brief_id,)
    ).fetchone()
    if not row:
        return None
    skill = _get(cursor, row[0])
    if require_usable and not skill["usable"]:
        raise ValueError(skill["unavailable_reason"])
    return skill


def eligible_reviews():
    """List recent passing bound evidence; raw samples stay in existing history."""
    with get_connection() as conn:
        conn.execute("BEGIN")
        ids = conn.execute(
            "SELECT id FROM business_practice_reviews ORDER BY id DESC LIMIT 200"
        ).fetchall()
        result = []
        for row in ids:
            try:
                item = _review(conn.cursor(), row[0])
            except ValueError:
                continue
            result.append(
                {
                    key: item[key]
                    for key in (
                        "review_id",
                        "sample_id",
                        "brief_id",
                        "rubric_digest",
                        "title",
                    )
                }
            )
        return result
