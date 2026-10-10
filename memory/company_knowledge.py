"""Read-only, source-explained navigation over existing company SQLite records.

No inferred graph or second truth/permission ledger is created. All SQL fragments
below are fixed internal contracts; search, identities and paging are bound values.
"""

import datetime
import json
from memory.database import get_connection
from memory.context_policy import CURRENT_WHERE, explanation

# Only explicitly selected fields are returned. Commands, seals, secrets, raw
# prompts, result blobs and executable paths never appear in this metadata view.
RECORDS = {
    "goal": dict(
        table="company_goals",
        identity="id",
        title="title",
        summary="description",
        timestamp="updated_at",
        status="status",
        fields=["description", "success_criteria", "completion_note"],
    ),
    "decision": dict(
        table="decisions",
        identity="id",
        title="topic",
        summary="decision_outcome",
        timestamp="timestamp",
        status="'recommendation; owner approval separate'",
        fields=["decision_outcome", "meeting_type"],
    ),
    "action": dict(
        table="action_queue",
        identity="id",
        title="action_description",
        summary="action_description",
        timestamp="timestamp",
        status="status",
        fields=["action_description", "proposed_by", "action_type", "source_phase"],
    ),
    "outcome": dict(
        table="action_outcomes",
        identity="action_id",
        title="COALESCE(expected_outcome,'Unspecified expected outcome')",
        summary="COALESCE(actual_outcome,'Outcome not measured')",
        timestamp="updated_at",
        status="outcome_status",
        fields=[
            "expected_outcome",
            "actual_outcome",
            "measured_at",
            "next_recommendation",
            "expected_cost_amount",
            "actual_cost_amount",
            "currency",
        ],
    ),
    "lesson": dict(
        table="executive_memories",
        identity="id",
        title="executive_key || ' · ' || memory_kind",
        summary="lesson",
        timestamp="updated_at",
        status="CASE WHEN is_active=1 THEN 'advisory memory' ELSE 'withheld memory' END",
        fields=["lesson", "executive_key", "memory_kind"],
    ),
    "skill": dict(
        table="executive_skill_versions",
        identity="id",
        title="name",
        summary="limitations",
        timestamp="created_at",
        status="'versioned procedure; review required'",
        fields=["name", "version", "prerequisites", "limitations", "rubric_digest"],
    ),
    "evidence": dict(
        table="evidence_sources",
        identity="id",
        title="title",
        summary="summary",
        timestamp="observed_at",
        status="verification",
        fields=[
            "title",
            "summary",
            "reference",
            "observed_at",
            "expires_at",
            "verification",
            "source_kind",
        ],
    ),
    "brief": dict(
        table="business_discovery",
        identity="id",
        title="title",
        summary="constraints",
        timestamp="created_at",
        status="state",
        fields=["title", "constraints", "state"],
    ),
    "sample": dict(
        table="business_practice_samples",
        identity="id",
        title="'Private sample ' || attempt",
        summary="sample",
        timestamp="created_at",
        status="'generated; owner assessment separate'",
        fields=["attempt", "sample"],
    ),
    "review": dict(
        table="business_practice_reviews",
        identity="id",
        title="'Owner practice review ' || id",
        summary="'Assessment of the linked exact sample'",
        timestamp="json_extract(review_json,'$.observed_at')",
        status="'owner assessment'",
        fields=[],
    ),
}
KINDS = tuple(RECORDS)


def _identity(ident):
    if type(ident) is not int or not 1 <= ident <= 9223372036854775807:
        raise ValueError("Invalid record identity")


def _contract(kind):
    if kind not in RECORDS:
        raise ValueError("Unsupported knowledge record kind")
    return RECORDS[kind]


def _select(kind):
    c = _contract(kind)
    return f"SELECT '{kind}' kind,{c['identity']} id,{c['title']} title,substr({c['summary']},1,300) excerpt,{c['timestamp']} recorded_at,{c['status']} status FROM {c['table']}"  # nosec B608 # Only fixed internal schema/policy fragments; all owner values bound.


def _node(cursor, kind, ident):
    c = _contract(kind)
    row = cursor.execute(
        f"{_select(kind)} WHERE {c['identity']}=?", (ident,)
    ).fetchone()
    if not row:
        raise LookupError("Knowledge record not found")
    node = dict(row)
    node["title"] = str(node["title"] or "Untitled")[:200]
    node["excerpt"] = str(node["excerpt"] or "")
    node["warnings"] = []
    node["context"] = None
    if kind == "lesson":
        node["context"] = explanation(cursor, ident)
        state = cursor.execute(
            "SELECT * FROM memory_lifecycle WHERE memory_id=?", (ident,)
        ).fetchone()
        if state:
            node["status"] = state["state"]
        node["warnings"] += node["context"]["reasons"]
        if not state or not json.loads(state["source_ids"]):
            node["warnings"].append(
                "No registered review sources; legacy advisory context is unverified"
            )
    elif kind == "evidence":
        state = cursor.execute(
            "SELECT verification,expires_at,CASE WHEN expires_at IS NOT NULL AND (julianday(expires_at) IS NULL OR julianday(expires_at)<=julianday('now')) THEN 1 ELSE 0 END expired FROM evidence_sources WHERE id=?",
            (ident,),
        ).fetchone()
        if state["verification"] != "owner_confirmed":
            node["warnings"].append(state["verification"])
        if state["expired"]:
            node["warnings"].append("expired")
        from memory.business_evidence import annotation

        node["category"] = annotation(cursor, ident)["category"]
        node["warnings"].append("Owner confirmation is not independent verification")
    elif kind == "skill":
        from memory.executive_skills import _get

        state = _get(cursor, ident)
        node["status"] = state["state"]
        if not state["usable"]:
            node["warnings"].append(state["unavailable_reason"])
        node["warnings"].append(
            "Procedure acceptance is not general competence or tool authority"
        )
    elif kind == "decision":
        state = cursor.execute(
            "SELECT status FROM decision_approvals WHERE decision_id=?", (ident,)
        ).fetchone()
        node["approval_status"] = state["status"] if state else "pending"
        node["warnings"].append(
            "Generated recommendation; approval is recorded separately"
        )
    elif kind == "review":
        row = cursor.execute(
            "SELECT review_json FROM business_practice_reviews WHERE id=?", (ident,)
        ).fetchone()
        value = json.loads(row[0])
        node["status"] = value.get("assessment", "unknown")
        if cursor.execute(
            "SELECT 1 FROM business_practice_reviews WHERE supersedes_review_id=?",
            (ident,),
        ).fetchone():
            node["warnings"].append("superseded assessment")
        node["warnings"].append(
            "Time is the owner-supplied observation time; a separate review creation timestamp was not stored"
        )
    elif kind == "sample":
        node["warnings"].append("Generated text is unverified; inspect owner reviews")
    return node


def search_knowledge(query="", kind="all", mode="history", limit=30, offset=0):
    if (
        not isinstance(query, str)
        or len(query) > 200
        or any(ord(c) < 32 for c in query)
    ):
        raise ValueError("Use a short plain search query")
    if mode not in {"history", "current"}:
        raise ValueError("Invalid knowledge mode")
    if (
        type(limit) is not int
        or not 1 <= limit <= 50
        or type(offset) is not int
        or not 0 <= offset <= 9223372036854775807
    ):
        raise ValueError("Invalid knowledge page")
    kinds = KINDS if kind == "all" else (kind,)
    if kind != "all":
        _contract(kind)
    parts = []
    for k in kinds:
        sql = _select(k)
        if k == "lesson" and mode == "current":
            sql += " WHERE " + CURRENT_WHERE
        parts.append(sql)
    sql = " UNION ALL ".join(parts)
    with get_connection() as conn:
        conn.execute("BEGIN")
        rows = conn.execute(
            f"SELECT kind,id FROM ({sql}) WHERE instr(lower(COALESCE(title,'') || ' ' || COALESCE(excerpt,'')),lower(?))>0 ORDER BY recorded_at DESC,kind,id DESC LIMIT ? OFFSET ?",  # nosec B608 # Only fixed internal schema/policy fragments; all owner values bound.
            (query.strip(), limit + 1, offset),
        ).fetchall()
        items = [_node(conn.cursor(), r["kind"], r["id"]) for r in rows[:limit]]
    return dict(
        items=items,
        has_more=len(rows) > limit,
        offset=offset,
        mode=mode,
        query=query.strip(),
        retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        scope="Recorded links and advisory text only. Current mode excludes withheld lessons; other record types are historical context, not agent instructions. Search matches titles and the first 300 characters; it is not semantic or exhaustive retrieval.",
    )


def knowledge_record(kind, ident, link_offset=0):
    c = _contract(kind)
    _identity(ident)
    if type(link_offset) is not int or not 0 <= link_offset <= 9223372036854775807:
        raise ValueError("Invalid link page")
    with get_connection() as conn:
        conn.execute("BEGIN")
        cursor = conn.cursor()
        node = _node(cursor, kind, ident)
        raw = dict(
            cursor.execute(
                f"SELECT * FROM {c['table']} WHERE {c['identity']}=?",  # nosec B608 # Only fixed internal schema/policy fragments; all owner values bound.
                (ident,),
            ).fetchone()
        )
        details = {
            key: (raw[key][:12000] if isinstance(raw[key], str) else raw[key])
            for key in c["fields"]
        }
        truncated_fields = [
            key
            for key in c["fields"]
            if isinstance(raw[key], str) and len(raw[key]) > 12000
        ]
        links = []

        def link(
            target_kind,
            target_id,
            relation,
            origin,
            recorded_at=None,
            expected_uuid=None,
            claim="",
        ):
            if not target_id:
                return
            try:
                target = _node(cursor, target_kind, target_id)
                if expected_uuid:
                    schema = _contract(target_kind)
                    actual = cursor.execute(
                        f"SELECT sync_uuid FROM {schema['table']} WHERE {schema['identity']}=?",  # nosec B608 # Only fixed internal schema/policy fragments; all owner values bound.
                        (target_id,),
                    ).fetchone()[0]
                    if actual != expected_uuid:
                        raise LookupError("Stable identity mismatch")
                links.append(
                    dict(
                        target=target,
                        relation=relation,
                        origin=origin,
                        recorded_at=recorded_at,
                        claim=claim[:2000],
                        verification="recorded link; claim not independently verified",
                        available=True,
                    )
                )
            except LookupError:
                links.append(
                    dict(
                        target=dict(
                            kind=target_kind,
                            id=target_id,
                            title="Missing or mismatched record",
                        ),
                        relation=relation,
                        origin=origin,
                        recorded_at=recorded_at,
                        claim=claim[:2000],
                        verification="unresolved provenance",
                        available=False,
                    )
                )

        def incoming(query, params, target, relation, origin):
            # Each query is literal below. Pagination happens over the bounded,
            # deterministic links list; oversize sets report their omitted count.
            rows = cursor.execute(query, params).fetchmany(201)
            if len(rows) > 200:
                overflow.append(origin)
            for row in rows[:200]:
                if (
                    "parent_uuid" in row.keys()
                    and row["parent_uuid"]
                    and row["parent_uuid"] != raw.get("sync_uuid")
                ):
                    links.append(
                        dict(
                            target=dict(
                                kind=target,
                                id=row["id"],
                                title="Stable parent identity mismatch",
                            ),
                            relation=relation,
                            origin=origin,
                            recorded_at=row["at"],
                            claim="",
                            verification="unresolved provenance",
                            available=False,
                        )
                    )
                else:
                    link(
                        target,
                        row["id"],
                        row["relation"] if "relation" in row.keys() else relation,
                        origin,
                        row["at"],
                        claim=row["claim"] if "claim" in row.keys() else "",
                    )

        overflow = []
        if kind in {"decision", "action", "lesson"}:
            for field, target in [
                ("goal_id", "goal"),
                ("source_goal_id", "goal"),
                ("source_decision_id", "decision"),
                ("source_action_id", "action"),
            ]:
                if raw.get(field):
                    link(
                        target,
                        raw[field],
                        "recorded provenance",
                        f'{c["table"]}.{field}',
                        raw.get(c["timestamp"]),
                        raw.get(field.replace("_id", "_sync_uuid")),
                    )
        if kind == "goal":
            incoming(
                "SELECT id,timestamp at,goal_sync_uuid parent_uuid FROM decisions WHERE goal_id=? ORDER BY id",
                (ident,),
                "decision",
                "decision for goal",
                "decisions.goal_id",
            )
            incoming(
                "SELECT id,updated_at at,source_goal_sync_uuid parent_uuid FROM executive_memories WHERE source_goal_id=? ORDER BY id",
                (ident,),
                "lesson",
                "memory from goal",
                "executive_memories.source_goal_id",
            )
        if kind == "decision":
            incoming(
                "SELECT id,timestamp at,source_decision_sync_uuid parent_uuid FROM action_queue WHERE source_decision_id=? ORDER BY id",
                (ident,),
                "action",
                "action proposed from decision",
                "action_queue.source_decision_id",
            )
            incoming(
                "SELECT id,updated_at at,source_decision_sync_uuid parent_uuid FROM executive_memories WHERE source_decision_id=? ORDER BY id",
                (ident,),
                "lesson",
                "memory from decision",
                "executive_memories.source_decision_id",
            )
            evidence_rows = cursor.execute(
                "SELECT source_id,relation,claim,created_at FROM evidence_links WHERE entity_kind='decision' AND entity_id=? ORDER BY id LIMIT 201",
                (ident,),
            ).fetchall()
            if len(evidence_rows) > 200:
                overflow.append("evidence_links")
            for row in evidence_rows[:200]:
                link(
                    "evidence",
                    row["source_id"],
                    row["relation"],
                    "evidence_links",
                    row["created_at"],
                    claim=row["claim"],
                )
        if kind == "action":
            incoming(
                "SELECT action_id id,updated_at at,action_sync_uuid parent_uuid FROM action_outcomes WHERE action_id=?",
                (ident,),
                "outcome",
                "outcome measurement",
                "action_outcomes.action_id",
            )
            incoming(
                "SELECT id,updated_at at,source_action_sync_uuid parent_uuid FROM executive_memories WHERE source_action_id=? ORDER BY id",
                (ident,),
                "lesson",
                "memory from action",
                "executive_memories.source_action_id",
            )
        if kind == "outcome":
            link(
                "action",
                ident,
                "measurement of action",
                "action_outcomes.action_id",
                raw["updated_at"],
                raw["action_sync_uuid"],
            )
        if kind == "lesson":
            lifecycle = cursor.execute(
                "SELECT * FROM memory_lifecycle WHERE memory_id=?", (ident,)
            ).fetchone()
            if lifecycle:
                for source_id in json.loads(lifecycle["source_ids"]):
                    link(
                        "evidence",
                        source_id,
                        "review source",
                        "memory_lifecycle.source_ids",
                    )
                if lifecycle["superseded_by"]:
                    link(
                        "lesson",
                        lifecycle["superseded_by"],
                        "corrected by",
                        "memory_lifecycle.superseded_by",
                    )
                incoming(
                    "SELECT memory_id id,NULL at FROM memory_lifecycle WHERE superseded_by=? ORDER BY memory_id",
                    (ident,),
                    "lesson",
                    "corrects earlier memory",
                    "memory_lifecycle.superseded_by",
                )
            revisions = cursor.execute(
                "SELECT version,operation,source_ids,note,created_at,replacement_id FROM memory_revisions WHERE memory_id=? ORDER BY version DESC LIMIT 51",
                (ident,),
            ).fetchall()
            details["revisions"] = [
                dict(r, source_ids=json.loads(r["source_ids"])) for r in revisions[:50]
            ]
            details["more_revisions"] = len(revisions) > 50
        if kind == "skill":
            for record in json.loads(raw["evidence_json"]):
                link(
                    "review",
                    record["review_id"],
                    "procedure based on owner assessment",
                    "executive_skill_versions.evidence_json",
                )
                link(
                    "sample",
                    record["sample_id"],
                    "procedure based on sample",
                    "executive_skill_versions.evidence_json",
                )
            incoming(
                "SELECT b.id,b.created_at at FROM practice_skill_bindings p JOIN business_discovery b ON b.id=p.brief_id WHERE p.skill_id=? ORDER BY b.id",
                (ident,),
                "brief",
                "used by private practice",
                "practice_skill_bindings",
            )
        if kind == "brief":
            for source_id in json.loads(raw["source_ids_json"]):
                link(
                    "evidence",
                    source_id,
                    "selected source",
                    "business_discovery.source_ids_json",
                    raw["created_at"],
                )
            incoming(
                "SELECT id,created_at at FROM business_practice_samples WHERE brief_id=? ORDER BY id",
                (ident,),
                "sample",
                "generated private sample",
                "business_practice_samples.brief_id",
            )
            row = cursor.execute(
                "SELECT skill_id FROM practice_skill_bindings WHERE brief_id=?",
                (ident,),
            ).fetchone()
            if row:
                link("skill", row[0], "bound skill version", "practice_skill_bindings")
        if kind == "sample":
            link(
                "brief",
                raw["brief_id"],
                "sample for brief",
                "business_practice_samples.brief_id",
                raw["created_at"],
            )
            link(
                "sample",
                raw["parent_sample_id"],
                "revises earlier sample",
                "business_practice_samples.parent_sample_id",
                raw["created_at"],
            )
            link(
                "review",
                raw["feedback_review_id"],
                "uses exact feedback",
                "business_practice_samples.feedback_review_id",
                raw["created_at"],
            )
            incoming(
                "SELECT id,json_extract(review_json,'$.observed_at') at FROM business_practice_reviews WHERE sample_id=? ORDER BY id",
                (ident,),
                "review",
                "owner assessment of sample",
                "business_practice_reviews.sample_id",
            )
        if kind == "review":
            link(
                "sample",
                raw["sample_id"],
                "assesses exact sample",
                "business_practice_reviews.sample_id",
            )
            link(
                "review",
                raw["supersedes_review_id"],
                "corrects earlier assessment",
                "business_practice_reviews.supersedes_review_id",
            )
            details["assessment"] = json.loads(raw["review_json"])
        if kind == "evidence":
            incoming(
                "SELECT entity_id id,created_at at,relation,claim FROM evidence_links WHERE source_id=? AND entity_kind='decision' ORDER BY id",
                (ident,),
                "decision",
                "linked evidence",
                "evidence_links",
            )
            incoming(
                "SELECT memory_id id,NULL at FROM memory_lifecycle WHERE EXISTS (SELECT 1 FROM json_each(source_ids) WHERE value=?) ORDER BY memory_id",
                (ident,),
                "lesson",
                "memory reviewed with source",
                "memory_lifecycle.source_ids",
            )
        if kind == "evidence":
            incoming(
                "SELECT id,created_at at FROM business_discovery WHERE EXISTS(SELECT 1 FROM json_each(source_ids_json) WHERE value=?) ORDER BY id",
                (ident,),
                "brief",
                "selected for research brief",
                "business_discovery.source_ids_json",
            )
        if kind == "review":
            incoming(
                "SELECT id,created_at at FROM executive_skill_versions WHERE EXISTS(SELECT 1 FROM json_each(evidence_json) WHERE json_extract(value,'$.review_id')=?) ORDER BY id",
                (ident,),
                "skill",
                "assessment supports procedure version",
                "executive_skill_versions.evidence_json",
            )
        page = links[link_offset : link_offset + 30]
    return dict(
        node=node,
        details=details,
        truncated_fields=truncated_fields,
        links=page,
        link_offset=link_offset,
        has_more_links=len(links) > link_offset + 30,
        omitted_link_groups=overflow,
        retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        scope="Relationships are read from named database fields, not generated by AI. A recorded supports/contradicts claim remains unverified. Missing timestamps are unknown; existing source content and approvals remain authoritative.",
    )
