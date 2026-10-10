"""One exclusion policy for current executive context and its owner explanation.

These predicates use the literal executive_memories table name. Callers bind all
user values; no owner/model input becomes an SQL identifier or expression.
"""

BLOCKS = {
    "inactive": "executive_memories.is_active!=1",
    "lifecycle_withheld": "EXISTS (SELECT 1 FROM memory_lifecycle l WHERE l.memory_id=executive_memories.id AND l.state!='active')",
    "expired": "EXISTS (SELECT 1 FROM memory_lifecycle l WHERE l.memory_id=executive_memories.id AND l.expires_at IS NOT NULL AND (julianday(l.expires_at) IS NULL OR julianday(l.expires_at)<=julianday('now')))",
    "source_missing": "EXISTS (SELECT 1 FROM memory_lifecycle l,json_each(l.source_ids) j LEFT JOIN evidence_sources e ON e.id=j.value WHERE l.memory_id=executive_memories.id AND e.id IS NULL)",
    "source_disputed": "EXISTS (SELECT 1 FROM memory_lifecycle l JOIN evidence_sources e ON e.id IN (SELECT value FROM json_each(l.source_ids)) WHERE l.memory_id=executive_memories.id AND e.verification='disputed')",
    "source_expired": "EXISTS (SELECT 1 FROM memory_lifecycle l JOIN evidence_sources e ON e.id IN (SELECT value FROM json_each(l.source_ids)) WHERE l.memory_id=executive_memories.id AND e.expires_at IS NOT NULL AND (julianday(e.expires_at) IS NULL OR julianday(e.expires_at)<=julianday('now')))",
    "conflicting_claim": "EXISTS (SELECT 1 FROM memory_lifecycle l WHERE l.memory_id=executive_memories.id AND l.claim_key!='' AND l.claim_key IN (SELECT x.claim_key FROM memory_lifecycle x JOIN executive_memories m ON m.id=x.memory_id WHERE x.state IN ('active','conflicted') AND m.is_active=1 GROUP BY x.claim_key HAVING COUNT(DISTINCT m.lesson)>1))",
}
CURRENT_WHERE = " AND ".join(f"NOT ({expression})" for expression in BLOCKS.values())
FLAGS_SELECT = ",".join(
    f"({expression}) AS {name}" for name, expression in BLOCKS.items()
)


def explanation(cursor, ident):
    row = cursor.execute(
        f"SELECT {FLAGS_SELECT} FROM executive_memories WHERE id=?",  # nosec B608 # Only fixed internal schema/policy fragments; all owner values bound.
        (ident,),
    ).fetchone()
    if not row:
        raise LookupError("Memory not found")
    reasons = [name for name in BLOCKS if row[name]]
    return dict(
        eligible=not reasons,
        reasons=reasons,
        scope="Eligibility is for advisory memory context, not factual verification or permission.",
    )
