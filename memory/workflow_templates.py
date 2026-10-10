"""Reviewed immutable workflow patterns; existing practice gates retain authority."""

import datetime
import hashlib
import json
import re
from memory.database import get_connection
from memory.experiments import _text

KINDS = {
    "select_evidence": dict(
        inputs=["dated_source_records"],
        outputs=["research_brief"],
        gate="owner_select_records",
        capability="owner_input",
        predecessor=None,
    ),
    "compare_options": dict(
        inputs=["research_brief"],
        outputs=["unverified_comparison"],
        gate="owner_run_generation",
        capability="local_text",
        predecessor="select_evidence",
    ),
    "approve_practice": dict(
        inputs=["unverified_comparison"],
        outputs=["frozen_practice_specification"],
        gate="owner_approve_practice",
        capability="owner_input",
        predecessor="compare_options",
    ),
    "generate_sample": dict(
        inputs=["frozen_practice_specification"],
        outputs=["private_sample"],
        gate="owner_run_generation",
        capability="local_text",
        predecessor="approve_practice",
    ),
    "review_sample": dict(
        inputs=["private_sample"],
        outputs=["owner_assessment"],
        gate="owner_assess_sample",
        capability="owner_input",
        predecessor="generate_sample",
    ),
}
PRESET = [
    dict(
        id=kind,
        kind=kind,
        depends_on=[] if values["predecessor"] is None else [values["predecessor"]],
    )
    for kind, values in KINDS.items()
]


def validate_steps(steps):
    """Reject cycles, missing typed producers and any executable/unsupported node."""
    if not isinstance(steps, list) or len(steps) != 5:
        raise ValueError("Use exactly the five evidence-to-private-practice steps")
    ids = {}
    kinds = {}
    for node in steps:
        if not isinstance(node, dict) or set(node) - {
            "id",
            "kind",
            "depends_on",
            "capability",
            "gate",
        }:
            raise ValueError(
                "Unsupported step fields; custom code and capabilities are forbidden"
            )
        ident = node.get("id")
        kind = node.get("kind")
        deps = node.get("depends_on")
        if (
            not isinstance(ident, str)
            or not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", ident)
            or ident in ids
        ):
            raise ValueError("Unique safe step identifiers required")
        if not isinstance(kind, str) or kind not in KINDS or kind in kinds:
            raise ValueError("Unsupported or repeated workflow capability")
        if (
            not isinstance(deps, list)
            or len(deps) > 5
            or any(not isinstance(d, str) for d in deps)
            or len(set(deps)) != len(deps)
        ):
            raise ValueError("Invalid dependencies")
        contract = KINDS[kind]
        if (
            node.get("capability", contract["capability"]) != contract["capability"]
            or node.get("gate", contract["gate"]) != contract["gate"]
        ):
            raise ValueError("Unsupported capability or missing owner gate")
        ids[ident] = node
        kinds[kind] = ident
    visited = set()
    active = set()
    ordered = []

    def visit(ident):
        if ident in active:
            raise ValueError("Workflow dependencies contain a cycle")
        if ident in visited:
            return
        if ident not in ids:
            raise ValueError("Dependency references an unknown step")
        active.add(ident)
        for dependency in ids[ident]["depends_on"]:
            visit(dependency)
        active.remove(ident)
        visited.add(ident)
        ordered.append(ident)

    for ident in ids:
        visit(ident)
    result = []
    for ident in ordered:
        node = ids[ident]
        contract = KINDS[node["kind"]]
        parent = contract["predecessor"]
        if parent and kinds[parent] not in node["depends_on"]:
            raise ValueError("Step is missing its typed input producer")
        result.append(
            dict(
                id=ident,
                kind=node["kind"],
                depends_on=node["depends_on"],
                **{k: v for k, v in contract.items() if k != "predecessor"},
            )
        )
    return result


def init_templates(cursor):
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS workflow_template_versions (
        id INTEGER PRIMARY KEY,template_key TEXT NOT NULL,version INTEGER NOT NULL,name TEXT NOT NULL,
        definition_json TEXT NOT NULL,digest TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(template_key,version))"""
    )
    cursor.execute("""CREATE TABLE IF NOT EXISTS workflow_template_reviews (
        id INTEGER PRIMARY KEY,template_id INTEGER NOT NULL,version INTEGER NOT NULL,state TEXT NOT NULL,
        note TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(template_id,version))""")
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS business_workflow_bindings (
        brief_id INTEGER PRIMARY KEY,template_id INTEGER NOT NULL,created_at TEXT NOT NULL)"""
    )
    for table in (
        "workflow_template_versions",
        "workflow_template_reviews",
        "business_workflow_bindings",
    ):
        for operation in ("UPDATE", "DELETE"):
            cursor.execute(
                f"CREATE TRIGGER IF NOT EXISTS {table}_no_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'Workflow provenance is immutable'); END"
            )  # nosec B608 # Literal table identifiers/operations.
    existing = cursor.execute(
        "SELECT id FROM workflow_template_versions WHERE template_key=?",
        ("evidence-to-private-practice",),
    ).fetchone()
    if not existing:
        _insert(
            cursor,
            "evidence-to-private-practice",
            "Evidence to private practice",
            PRESET,
        )


def _insert(cursor, key, name, steps):
    if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,79}", key):
        raise ValueError("Invalid template key")
    name = _text(name, "template name", 200)
    definition = json.dumps(
        validate_steps(steps), sort_keys=True, separators=(",", ":")
    )
    version = cursor.execute(
        "SELECT COALESCE(MAX(version),0)+1 FROM workflow_template_versions WHERE template_key=?",
        (key,),
    ).fetchone()[0]
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    row = cursor.execute(
        "INSERT INTO workflow_template_versions(template_key,version,name,definition_json,digest,created_at) VALUES(?,?,?,?,?,?)",
        (
            key,
            version,
            name,
            definition,
            hashlib.sha256(definition.encode()).hexdigest(),
            now,
        ),
    )
    ident = row.lastrowid
    cursor.execute(
        "INSERT INTO workflow_template_reviews(template_id,version,state,note,created_at) VALUES(?,1,?,?,?)",
        (
            ident,
            "proposed",
            "Review pattern only; no practice or launch approval",
            now,
        ),
    )
    return ident


def _get(cursor, ident):
    row = cursor.execute(
        "SELECT * FROM workflow_template_versions WHERE id=?", (ident,)
    ).fetchone()
    if not row:
        raise LookupError("Workflow version not found")
    value = dict(row)
    value["steps"] = json.loads(value.pop("definition_json"))
    review = cursor.execute(
        "SELECT * FROM workflow_template_reviews WHERE template_id=? ORDER BY version DESC LIMIT 1",
        (ident,),
    ).fetchone()
    value.update(
        state=review["state"],
        review_version=review["version"],
        usable=review["state"] == "reviewed",
        scope="Workflow pattern review only; each existing owner practice/run/assessment gate remains required",
    )
    value["reviews"] = [
        dict(r)
        for r in cursor.execute(
            "SELECT * FROM workflow_template_reviews WHERE template_id=? ORDER BY version",
            (ident,),
        )
    ]
    return value


def get_template(ident):
    with get_connection() as conn:
        return _get(conn.cursor(), ident)


def list_templates(limit=50, offset=0):
    with get_connection() as conn:
        ids = [
            r[0]
            for r in conn.execute(
                "SELECT id FROM workflow_template_versions ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        ]
        return [_get(conn.cursor(), ident) for ident in ids]


def create_template(key, name, steps):
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        ident = _insert(conn.cursor(), key, name, steps)
        conn.commit()
    return get_template(ident)


def review_template(ident, expected_version, state, note):
    if state not in {"reviewed", "withdrawn"}:
        raise ValueError("Invalid workflow review state")
    note = _text(note, "workflow review note", 2000)
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        current = _get(conn.cursor(), ident)
        if (
            current["review_version"] != expected_version
            or current["state"] == "withdrawn"
            or current["state"] == state
        ):
            raise RuntimeError("Workflow review changed or version withdrawn; refresh")
        conn.execute(
            "INSERT INTO workflow_template_reviews(template_id,version,state,note,created_at) VALUES(?,?,?,?,?)",
            (
                ident,
                expected_version + 1,
                state,
                note,
                datetime.datetime.now(datetime.timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    return get_template(ident)


def bind_template(cursor, brief_id, template_id):
    template = _get(cursor, template_id)
    if not template["usable"]:
        raise ValueError("Review this workflow version before using it")
    cursor.execute(
        "INSERT INTO business_workflow_bindings VALUES(?,?,?)",
        (
            brief_id,
            template_id,
            datetime.datetime.now(datetime.timezone.utc).isoformat(),
        ),
    )


def template_context(cursor, brief_id, require_reviewed=True):
    row = cursor.execute(
        "SELECT template_id FROM business_workflow_bindings WHERE brief_id=?",
        (brief_id,),
    ).fetchone()
    if not row:
        return None
    template = _get(cursor, row["template_id"])
    if require_reviewed and not template["usable"]:
        raise ValueError(
            "Bound workflow version was withdrawn; use a new reviewed version and brief"
        )
    return template
