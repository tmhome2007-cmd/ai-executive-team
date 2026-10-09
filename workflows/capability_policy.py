"""
workflows/capability_policy.py

Deterministic executive capability policy.

LLM prompts/tool assignment are not authorization. New executable proposals
must also pass this server-side policy before they reach durable storage.
"""

ROLE_ALIASES = {
    "ceo": "ceo",
    "chief executive officer": "ceo",
    "cfo": "cfo",
    "chief financial officer": "cfo",
    "coo": "coo",
    "chief operating officer": "coo",
    "cso": "cso",
    "chief strategy officer": "cso",
    "cmo": "cmo",
    "chief marketing officer": "cmo",
    "cto": "cto",
    "chief technology officer": "cto",
    "cpo": "cpo",
    "chief product officer": "cpo",
    "chro": "chro",
    "chief human resources officer": "chro",
    "general counsel": "general_counsel",
    "board director": "board_director",
    "cco": "cco",
    "chief compliance & operations officer": "cco",
    "chief compliance and operations officer": "cco",
}

EXECUTABLE_CAPABILITIES = {
    "shell": frozenset({"coo", "cto"}),
    "file_operation": frozenset({"coo", "cto", "cfo", "general_counsel"}),
    "browser_action": frozenset({"coo"}),
}


def normalize_executive_role(role: str) -> str | None:
    normalized = " ".join((role or "").strip().lower().replace("_", " ").split())
    return ROLE_ALIASES.get(normalized)


def require_action_capability(proposed_by: str, action_type: str) -> str:
    allowed_roles = EXECUTABLE_CAPABILITIES.get(action_type)
    if allowed_roles is None:
        raise ValueError(f"Unsupported executable capability: {action_type}")

    canonical_role = normalize_executive_role(proposed_by)
    if canonical_role is None:
        raise ValueError(
            "Unknown executive identity cannot create executable action proposals"
        )
    if canonical_role not in allowed_roles:
        raise ValueError(
            f"Executive role '{canonical_role}' is not authorized for "
            f"executable capability '{action_type}'"
        )
    return canonical_role
