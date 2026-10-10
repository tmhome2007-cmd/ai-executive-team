"""Shared, bounded checks on published AI text. These checks do not certify truth."""

import re

POLICY_VERSION = 2
QUALITY_POLICY = """AI output quality policy:
Write for a busy owner: keep each section to at most three concise bullets unless the task
requires a longer exact source quotation or safety prerequisite. Avoid repeating the same point.
When no fixed report contract is required, use Findings, Unknowns, and Next action headings.
Keep uncertainty, blocking prerequisites and source references visible; brevity never permits omission.
Use only supplied records for facts; separate observations, hypotheses and recommendations.
Prior agent speech and historical memory are not new evidence. Cite actual supplied records.
Do not say supplied details are missing; quote the relevant record before requesting it again.
Never infer the cause or health of a component merely from an observed or hypothetical pass.
Describe pass/fail as observations, not causal conclusions. Define controls and all possible results.
Quote a published claim before challenging it; no change needed is a valid conclusion.
Never invent owner consent, completed work, costs, customers or successful tests.
Preserve your role and personality, while keeping claims precise and uncertainty explicit.
No filler, duplicated analysis, placeholder text or promises of money. Recommendations need
an observable next step, missing prerequisites and the separate owner approval boundary.
"""


def assess_output(body, evidence=""):
    warnings = []
    if not isinstance(body, str) or not body.strip():
        return ["Empty AI output"]
    if body.startswith("AI QUALITY REVIEW REQUIRED"):
        warnings.append("Unresolved issues remain after the bounded quality check")
    if len(body) > 100000:
        warnings.append("AI output exceeds the publication size limit")
    if re.search(r"\b(?:TODO|lorem ipsum|insert (?:text|evidence) here)\b", body, re.I):
        warnings.append("Unfinished placeholder text")
    for sentence in re.split(r"[.!?\n]", body):
        if re.search(
            r"\b(?:owner|human|user)\s+(?:has\s+)?(?:approved|agreed|authorized|consented)\b",
            sentence,
            re.I,
        ) and not re.search(r"\b(?:not|no|never|cannot)\b", sentence, re.I):
            warnings.append("AI cannot establish owner consent")
        if re.search(
            r"\b(?:proves?|confirms?|establish(?:es)?|indicat(?:es|ing)|suggests?)\b.{0,65}\b(?:cause|caused|healthy|working correctly|issue is (?:not )?related)\b",
            sentence,
            re.I,
        ) and not re.search(
            r"\b(?:cannot|hypothesis|unproven|alone|doesn.t|does not)\b", sentence, re.I
        ):
            warnings.append(
                "Causal/component-health conclusion requires independent evidence"
            )
    # Detect explicit contradictions for the fixture and labelled source records.
    fields = (
        "original reproduction steps",
        "reminder due time",
        "build",
        "observation channel",
    )
    for field in fields:
        supplied = re.search(re.escape(field) + r"\s*:\s*([^\n.]+)", evidence, re.I)
        if supplied and not re.search(
            r"\b(?:unknown|missing|not supplied|not provided)\b", supplied[1], re.I
        ):
            if any(
                field in sentence.lower()
                and re.search(
                    r"\b(?:unknown|not explicitly stated|not supplied|not provided|does not (?:provide|specify|include))\b",
                    sentence,
                    re.I,
                )
                for sentence in re.split(r"[.!?\n]", body)
            ):
                warnings.append(
                    "Supplied detail incorrectly described as missing: " + field
                )
    return list(dict.fromkeys(warnings))[:20]


def review_notice(body, warnings):
    if not warnings or body.startswith("AI QUALITY REVIEW REQUIRED"):
        return body
    return (
        "AI QUALITY REVIEW REQUIRED — Automated checks found unresolved issues; "
        "this is an unverified draft, not an approved result.\n"
        + "\n".join("- " + warning for warning in warnings)
        + "\n\n"
        + body
    )


def verify_source_quotes(body, sources, required=None):
    """Membership/coverage checks only; quotations do not prove interpretation."""
    citations = re.findall(
        r"(?im)^\s*Source quote:\s*(https?://[^\s|]+)\s*\|\s*(.+?)\s*$",
        body.replace("**", ""),
    )
    normalize = lambda text: " ".join(text.split())
    if not citations or any(
        len(quote.strip()) < 12
        or url not in sources
        or normalize(quote) not in normalize(sources[url])
        for url, quote in citations
    ):
        return ["Missing or invalid retrieved-source quotation"]
    if not set(required or sources) <= {url for url, _ in citations}:
        return ["Not every required source has a verified quotation"]
    return []
