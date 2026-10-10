"""Meeting contracts: participants, evidence expectations and output sections.

Central meeting-type policy. Meeting types shape reasoning and output, never
execution authority. All real-world effects remain behind the existing owner,
resource, treasury, and execution gates.
"""

MEETING_TYPES = {
    "strategy": {
        "label": "Strategy",
        "default_agents": ["cso", "cfo", "ceo"],
        "required_agents": ["ceo"],
        "evidence_focus": (
            "Strategic fit, alternatives, assumptions, opportunity cost, and what "
            "must be validated before committing."
        ),
        "output_contract": (
            "Strategic options; tradeoffs/risks; recommendation; validation plan; approval gate."
        ),
        "response_structure": (
            "Strategic Options; Tradeoffs / Risks; Recommendation; Validation Plan; Approval Gate."
        ),
        "approval_posture": (
            "Recommend a direction only. Owner approval is required before preparation."
        ),
    },
    "operating_review": {
        "label": "Operating Review",
        "default_agents": ["coo", "cfo", "cto", "ceo"],
        "required_agents": ["coo", "ceo"],
        "evidence_focus": (
            "Actual operating performance, blockers, variance from plan, ownership, "
            "and measurable next checkpoints."
        ),
        "output_contract": (
            "Operating status; blockers/variance; accountable next steps; evidence gaps; approval gate."
        ),
        "response_structure": (
            "Operating Status; Blockers / Variance; Accountable Next Steps; Evidence Gaps; Approval Gate."
        ),
        "approval_posture": (
            "May recommend operational changes, but no new action executes without existing gates."
        ),
    },
    "incident": {
        "label": "Incident / Emergency",
        "default_agents": ["coo", "cto", "general_counsel", "ceo"],
        "required_agents": ["ceo"],
        "evidence_focus": (
            "Verified incident facts, blast radius, immediate containment options, "
            "unknowns, reversibility, legal/security implications."
        ),
        "output_contract": (
            "Known facts; impact/unknowns; containment recommendation; recovery path; escalation/approval gate."
        ),
        "response_structure": (
            "Known Facts; Impact / Unknowns; Containment Recommendation; Recovery Path; Approval Gate."
        ),
        "evidence_section_rule": (
            "Known Facts must contain ONLY established facts from the current task/evidence. "
            "Move every hypothesis, possibility, cannot-rule-out statement, or speculative cause "
            "to Impact / Unknowns."
        ),
        "approval_posture": (
            "Urgency never bypasses authority. Tool-free reasoning may recommend containment; "
            "real effects still require the normal owner/action gates."
        ),
    },
    "capital_allocation": {
        "label": "Capital Allocation",
        "default_agents": ["cfo", "cso", "ceo"],
        "required_agents": ["cfo", "ceo"],
        "evidence_focus": (
            "Available treasury by currency, expected cost, downside, alternatives, "
            "measurement plan, and capital at risk."
        ),
        "output_contract": (
            "Capital request; alternatives; downside/uncertainty; expected measurable outcome; approval gate."
        ),
        "response_structure": (
            "Current Capital Evidence; Capital Request / Recommendation; Alternatives; "
            "Downside / Uncertainty; Expected Measurable Outcome; Approval Gate."
        ),
        "approval_posture": (
            "A meeting can recommend capital allocation only. Treasury reservation/spend remains separate."
        ),
    },
    "retrospective": {
        "label": "Retrospective",
        "default_agents": ["coo", "cso", "ceo"],
        "required_agents": ["ceo"],
        "evidence_focus": (
            "Measured outcomes versus expectations, what worked, what failed, causal uncertainty, "
            "and reusable lessons."
        ),
        "output_contract": (
            "Expected vs actual; lessons; mistakes/unknowns; what to repeat/stop/change; owner acknowledgement pending owner review."
        ),
        "response_structure": (
            "Expected vs Actual; What Worked; What Failed / Unknown; Reusable Lessons; "
            "What to Repeat / Stop / Change; Owner Acknowledgement."
        ),
        "evidence_section_rule": (
            "Expected vs Actual, What Worked and What Failed require observed outcomes from current evidence. "
            "When outcomes are not supplied, say Unknown — evidence required. Never invent team discussions, "
            "effective formats, implemented changes, market assumptions or company history. "
            "Label general advice as recommendations, not observed lessons. Owner acknowledgement stays pending."
        ),
        "approval_posture": (
            "Retrospectives do not authorize new execution. Any new direction becomes a separate pending decision."
        ),
    },
    "planning": {
        "label": "Planning",
        "default_agents": ["coo", "cso", "cfo", "ceo"],
        "required_agents": ["coo", "ceo"],
        "evidence_focus": (
            "Objective, sequencing, dependencies, capacity, resources, milestones, and explicit unknowns."
        ),
        "output_contract": (
            "Plan objective; workstreams/dependencies; milestones; resource gaps; risks; approval gate."
        ),
        "response_structure": (
            "Plan Objective; Workstreams / Dependencies; Milestones; Resource Gaps; Risks; Approval Gate."
        ),
        "approval_posture": (
            "Planning produces an owner-reviewable direction. Preparation and execution remain separate."
        ),
    },
}

VALID_MEETING_TYPES = set(MEETING_TYPES)


def get_meeting_type_profile(meeting_type: str) -> dict:
    if meeting_type not in MEETING_TYPES:
        raise ValueError(f"Unsupported meeting type: {meeting_type}")
    return MEETING_TYPES[meeting_type]


def resolve_meeting_agents(
    meeting_type: str, agent_keys: list[str] | None
) -> list[str]:
    profile = get_meeting_type_profile(meeting_type)
    resolved = (
        list(agent_keys) if agent_keys is not None else list(profile["default_agents"])
    )
    if not resolved:
        raise ValueError("Meeting must include at least one executive")
    missing_required = [
        key for key in profile["required_agents"] if key not in resolved
    ]
    if missing_required:
        raise ValueError(
            f"Meeting type '{meeting_type}' requires executive role(s): {missing_required}"
        )
    return resolved


def meeting_type_prompt(meeting_type: str) -> str:
    profile = get_meeting_type_profile(meeting_type)
    return (
        f"MEETING TYPE: {meeting_type} — {profile['label']}\n"
        f"Evidence focus: {profile['evidence_focus']}\n"
        f"Required output contract: {profile['output_contract']}\n"
        f"Required response structure: {profile['response_structure']}\n"
        + (
            f"Evidence-section rule: {profile['evidence_section_rule']}\n"
            if profile.get("evidence_section_rule")
            else ""
        )
        + f"Authority posture: {profile['approval_posture']}\n"
        "The meeting type changes reasoning structure only. It never expands tool, "
        "approval, resource, treasury, or execution authority."
    )
