"""Deterministic owner next steps; UI guidance never grants execution authority."""

import json
from memory.evidence import _source
from memory.practice_quality import assert_specification

LABELS = {
    "draft": "Research not started",
    "research_running": "Comparing research",
    "research_ready": "Choose a private exercise",
    "practice_ready": "Ready to draft",
    "practice_running": "Drafting privately",
    "revision_running": "Revising privately",
    "sample_ready": "Your review is needed",
    "reviewed": "Assessment recorded",
    "needs_review": "Work needs attention",
}


def guidance(cursor, row, skill, workflow):
    """Read current bindings/source status in the brief's existing read transaction."""
    state = row["state"]

    def step(action, label, explanation, blocked=False):
        return dict(
            state_label=LABELS.get(state, "Refresh this record"),
            action=action,
            label=label,
            explanation=explanation,
            blocked=blocked,
        )

    if state.endswith("_running"):
        return step(
            "inspect_runs",
            "Check the current run",
            "Open Run inspector for progress and stop controls. Waiting or refreshing never starts another attempt.",
        )
    if state == "sample_ready":
        return step(
            "review_sample",
            "Review this sample",
            "Read Full sample, choose Passed or Failed for each approved check, then describe what you observed. Nothing is pre-approved.",
        )
    # Assessment and historical files remain available even after permissions change.
    if state in {
        "draft",
        "research_ready",
        "practice_ready",
        "reviewed",
        "needs_review",
    }:
        if workflow and not workflow["usable"]:
            return step(
                "new_brief",
                "Prepare a new research brief",
                "The bound workflow was withdrawn. Review a new workflow version before binding it to a new brief; earlier work stays in history.",
                True,
            )
        if (
            state in {"practice_ready", "reviewed", "needs_review"}
            and skill
            and not skill["usable"]
        ):
            return step(
                "new_brief",
                "Prepare a new private exercise",
                "The bound skill was revoked or its supporting assessments changed. Review a new skill version before using it in a new exercise.",
                True,
            )
    if state in {"draft", "practice_ready", "reviewed", "needs_review"}:
        for ident in json.loads(row["source_ids_json"]):
            source = cursor.execute(
                "SELECT * FROM evidence_sources WHERE id=?", (ident,)
            ).fetchone()
            if (
                not source
                or _source(source)["freshness"] == "stale"
                or source["verification"] == "disputed"
            ):
                return step(
                    "review_sources",
                    "Review the source records",
                    "A source is missing, disputed or expired. Resolve disputed records or register fresh evidence and select it for a new brief before generating work.",
                    True,
                )
    if state == "draft":
        return step(
            "research",
            "Compare options with local AI",
            "The selected records will be frozen for this comparison. A comparison does not verify customer demand.",
        )
    if state == "research_ready":
        if row["research_contract_version"] not in {2, 3}:
            return step(
                "new_brief",
                "Prepare a new research brief",
                "This older comparison has not passed the current source/service contract. Its text remains available; create a new reviewed exercise.",
                True,
            )
        return step(
            "choose_practice",
            "Choose a private practice exercise",
            "Use the form below to supply the audience, facts and exact checks. Missing buyer evidence blocks a business choice, but private practice remains available.",
        )
    if state in {"practice_ready", "reviewed", "needs_review"} and row["exercise"]:
        try:
            assert_specification(cursor, row["id"])
        except (ValueError, RuntimeError, LookupError):
            return step(
                "new_brief",
                "Prepare a new private exercise",
                "The approved facts or rubric cannot be validated. Preserve this record and prepare a new owner-reviewed exercise.",
                True,
            )
    if state == "practice_ready":
        return step(
            "practice",
            "Generate private practice sample",
            "The local AI drafts text using the approved facts and checks. Model identity is verified when you start; you assess usefulness afterwards.",
        )
    review = json.loads(row["review_json"]) if row["review_json"] else None
    if state in {"reviewed", "needs_review"} and row["sample"] and review:
        if state == "reviewed" and review.get("assessment") == "practice_passed":
            return step(
                "read_sample",
                "Read the sample for usefulness",
                "The recorded checks passed. Read the full text and decide whether it helps its intended reader. Passing checks is not proof of usefulness or launch approval.",
            )
        count = cursor.execute(
            "SELECT COUNT(*) FROM business_practice_samples WHERE brief_id=?",
            (row["id"],),
        ).fetchone()[0]
        if not 1 <= count < 10:
            return step(
                "new_brief",
                "Prepare another private exercise",
                "This exercise has reached its sample-history limit. Previous samples and reviews remain available.",
                True,
            )
        return step(
            "revise",
            "Revise using the recorded feedback",
            "At least one check failed or a revision was interrupted. The earlier sample and feedback stay saved; review the new draft under the same rubric.",
        )
    if state == "needs_review":
        return step(
            "inspect_runs",
            "Check recovery in Run inspector",
            "Generation failed or was interrupted. Run inspector explains whether this private attempt can continue. Earlier evidence stays unchanged.",
        )
    return step(
        "refresh",
        "Refresh this record",
        "Read the current record before choosing another action.",
        True,
    )
