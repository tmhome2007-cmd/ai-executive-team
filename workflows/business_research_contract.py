"""Bounded service hypotheses and source-exact quotes; no inferred market facts."""

import json
import re
from memory.experiments import _text

SERVICES = {
    "documentation": "Documentation service: draft setup guides and FAQs",
    "editing": "Editing service: improve owner-supplied text",
    "support_drafts": "Support drafting service: draft replies from supplied policies",
}
VERSION = 3


def research_instruction():
    return (
        "Compare these service hypotheses only: "
        + json.dumps(SERVICES)
        + ". They are candidate deliverables, not verified opportunities. "
        "Cloudflare and GitHub are hosting/tools; Fiverr is a marketplace, never a deliverable. Do not infer a restriction on one platform applies to others. "
        'Return JSON only: {"options":[{"key":"documentation","skills":["..."],"exercise":"...","checks":["...","..."]}, ...],'
        '"practice_choice":"documentation", "claims":[{"source_id":1,"service":"documentation","quote":"exact supplied text","relation":"supports"}], "next_sources":[]}. '
        "Include exactly all three keys. Use 2–5 observable checks per option. Exercises must produce private text samples without new access or spending. "
        "practice_choice selects a useful learning exercise only, never the best business or a demand finding. Claims must quote an exact substring from a supplied source and identify its source ID. A quote proves attribution only, not truth or demand. Omit unsupported claims. Leave next_sources empty unless you know a specific relevant public URL; never invent URLs or use example domains. Propose at most five plain public HTTP(S) URLs for missing buyer evidence; never read them or claim their contents are known. The server attaches registered source excerpts separately. "
        "No claims about commercial permission, demand, prices, earnings, existing skills or achievements. Missing evidence stays unknown; no prose outside JSON.\n"
    )


def render_research(raw, sources):
    try:
        payload = json.loads(
            raw.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
    except (ValueError, AttributeError):
        raise ValueError(
            "Research failed the structured comparison check; no practice plan is ready"
        ) from None
    if (
        not isinstance(payload, dict)
        or not {"options", "practice_choice"} <= set(payload)
        or set(payload) - {"options", "practice_choice", "claims", "next_sources"}
    ):
        raise ValueError(
            "Research must separate service comparisons from exact source excerpts"
        )
    options = payload["options"]
    if (
        not isinstance(options, list)
        or len(options) != 3
        or any(not isinstance(o, dict) for o in options)
    ):
        raise ValueError("Research must compare three deliverable services")
    if any(set(o) != {"key", "skills", "exercise", "checks"} for o in options):
        raise ValueError("Research option fields are incomplete")
    if any(not isinstance(o["key"], str) for o in options) or {
        o["key"] for o in options
    } != set(SERVICES):
        raise ValueError(
            "Hosting platforms and marketplaces are tools, not business options"
        )
    if (
        not isinstance(payload["practice_choice"], str)
        or payload["practice_choice"] not in SERVICES
    ):
        raise ValueError("Invalid practice choice")
    for option in options:
        option["exercise"] = _text(option["exercise"], "practice exercise", 2000)
        for field in ("skills", "checks"):
            values = option[field]
            minimum = 2 if field == "checks" else 1
            if not isinstance(values, list) or not minimum <= len(values) <= 5:
                raise ValueError(
                    "Every service needs skills and observable practice checks"
                )
            option[field] = [_text(v, field, 500) for v in values]
        text = json.dumps(option)
        if re.search(
            r"(?:not (?:intended|allowed|permitted|suitable) for commercial|(?:prohibit|ban|forbid)\w* commercial|commercial use (?:is )?(?:prohibited|forbidden|banned))",
            text,
            re.I,
        ):
            raise ValueError(
                "Unsupported commercial-use claims withheld; quote source restrictions separately"
            )
    evidence_lines = evidence_comparison(
        payload.get("claims", []), payload.get("next_sources", []), sources
    )
    lines = [
        "**Findings**",
        "Three proposed services were compared as learning hypotheses. None is a verified business opportunity.",
        "**Unknowns**",
        "Customer demand, market size, pricing, contingent fees, commercial eligibility and agent competence remain unknown.",
        "The supplied platform/hosting records alone do not establish buyer demand. No best business can be selected from these records alone.",
        "**Next action**",
        "Choose a prepared private exercise below, review its supplied facts and checks, set a future review date, then approve the practice plan. Suggested service: "
        + SERVICES[payload["practice_choice"]]
        + ". This does not approve a business launch.",
        "**Service comparisons — proposed practice, not demonstrated skills**",
    ]
    for option in options:
        lines.extend(
            [
                "\n" + SERVICES[option["key"]],
                "Required skills — unproven: " + "; ".join(option["skills"]),
                "Private practice deliverable: " + option["exercise"],
                "Model-suggested checks — refine vague criteria before owner approval:",
            ]
        )
        lines.extend("- " + check for check in option["checks"])
        controls = {
            "documentation": [
                "Every described feature matches the supplied or explicitly fictional brief",
                "Missing feature details are labelled unknown",
                "A reader can follow the stated steps without invented credentials or accounts",
            ],
            "editing": [
                "The original supplied facts are preserved",
                "Identified spelling/grammar errors are corrected",
                "No new promises, performance claims or facts are introduced",
            ],
            "support_drafts": [
                "Every proposed answer matches the supplied or explicitly fictional policy",
                "Missing policy details are escalated for owner review",
                "The draft never claims a refund, approval or other action has happened",
            ],
        }
        lines.append("Minimum review controls:")
        lines.extend("- " + check for check in controls[option["key"]])
        lines.extend(
            [
                "Practice input: supply a short brief/text/policy, or use a clearly labelled fictional fixture.",
                "Access: no external account is needed for private text practice. Real delivery access has not been assessed.",
                "Owner responsibilities: choose the exercise and review its sample; professional skills are not assumed.",
                "Authorized spending/loss: €0. Execution, delivery and future costs are not established.",
            ]
        )
    lines.extend(evidence_lines)
    lines.append(
        "\n**Source excerpts — apply only to their own source; not independent verification**"
    )
    for source in sources:
        # The excerpt comes from the immutable record, never a model attribution.
        excerpt = source["summary"][:400]
        lines.append(
            f"Source #{source['id']} — {source['title']} — {source['reference']} — observed {source['observed_at']} — {source['freshness']} / {source['verification']}\nOpening excerpt (may be incomplete): {excerpt}"
        )
    return "\n\n".join(lines)


def evidence_comparison(claims, proposals, sources):
    from urllib.parse import urlsplit
    import datetime

    if (
        not isinstance(claims, list)
        or len(claims) > 20
        or not isinstance(proposals, list)
        or len(proposals) > 5
    ):
        raise ValueError("Bound research claims and proposed sources")
    registered = {s["id"]: s for s in sources}
    support = {key: set() for key in SERVICES}
    contradictions = {
        service
        for source in sources
        if source.get("business_context", {}).get("category") == "contradiction"
        for service in source["business_context"].get("services", [])
        if service in SERVICES
    }
    unresolved_claims = set()
    lines = [
        "**Evidence coverage — attribution is not verification**",
        "Source status and owner classifications below are the frozen generation-time snapshot; later changes require a new brief. Coverage is a research heuristic, not a buyer-demand verdict. Subdomains count once using conservative offline domain grouping; different sites do not prove independent publishers.",
    ]
    for value in claims:
        claim = ResearchClaim.model_validate(value).model_dump()
        source = registered.get(claim["source_id"])
        quote = _text(claim["quote"], "source quotation", 700)
        if not source or len(quote) < 12 or quote not in source["summary"]:
            unresolved_claims.add(claim["service"])
            lines.append(
                f"Withheld unsupported quotation for source #{claim['source_id']} / {claim['service']}: attribution did not match a selected immutable record; no evidence credit."
            )
            continue
        context = source.get("business_context", {})
        date = context.get("publication_date")
        eligible = bool(
            date
            and source["verification"] == "owner_confirmed"
            and source["freshness"] == "current"
            and claim["service"] in context.get("services", [])
            and context.get("category") in {"demand", "buyer"}
        )
        if date:
            try:
                eligible = (
                    eligible
                    and 0
                    <= (
                        datetime.datetime.now(datetime.timezone.utc).date()
                        - datetime.date.fromisoformat(date)
                    ).days
                    <= 365
                )
            except ValueError:
                eligible = False
        publisher = urlsplit(source["reference"]).hostname
        if (
            claim["relation"] == "contradicts"
            or context.get("category") == "contradiction"
        ):
            contradictions.add(claim["service"])
        elif eligible and publisher:
            # Conservative offline grouping: subdomains never add coverage.
            # Public-suffix exceptions can undercount; this is not publisher verification.
            from ipaddress import ip_address

            try:
                ip_address(publisher)
            except ValueError:
                parts = publisher.lower().rstrip(".").split(".")
                if len(parts) >= 2:
                    support[claim["service"]].add(".".join(parts[-2:]))
        lines.append(
            f"Source #{source['id']} v{source['version']}, classification v{context.get('version',0)} — {claim['service']} / {claim['relation']} / {context.get('category','unknown')} / published {date or 'unknown'}: {quote}"
        )
    if not claims:
        lines.append(
            "No source-linked buyer claims were supplied; evidence coverage is missing."
        )
    candidates = [
        key
        for key in SERVICES
        if len(support[key]) >= 2
        and key not in contradictions
        and key not in unresolved_claims
    ]
    for key in SERVICES:
        lines.append(
            f"{SERVICES[key]}: {len(support[key])} distinct source-site groups with dated, current, owner-confirmed buyer/demand quotations; contradictions: {'yes' if key in contradictions else 'none quoted (absence is not proof)'}. Unresolved attributions: {'yes' if key in unresolved_claims else 'none withheld'}. Costs and competence remain unknown."
        )
    lines.append("**Business selection**")
    if candidates:
        strongest = sorted(candidates, key=lambda k: (-len(support[k]), k))
        if len(strongest) > 1 and len(support[strongest[0]]) == len(
            support[strongest[1]]
        ):
            lines.append(
                "Selection blocked: evidence coverage is tied. Investigate costs, counterevidence and sample quality before choosing."
            )
        else:
            lines.append(
                "Research candidate with greatest qualifying source coverage: "
                + SERVICES[strongest[0]]
                + ". This is a research priority only; buyer demand, profit and delivery competence are not established."
            )
    else:
        lines.append(
            "Selection blocked: collect exact buyer/problem quotations for a service from at least two different source-site groups, record publication dates and freshness, review accuracy, and investigate contradictions. Platform limits alone cannot satisfy this rule."
        )
    lines.append("**Next research step**")
    lines.append(
        "Find recent public buyer requests or documented buyer problems for documentation, editing or support drafting. Classify the selected records and create a new brief; existing reports retain their original evidence snapshot."
    )
    for value in proposals:
        proposal = ProposedSource.model_validate(value)
        url = _text(proposal.url, "proposed public URL", 1000)
        parsed = urlsplit(url)
        try:
            port = parsed.port
        except ValueError:
            raise ValueError("Invalid proposed URL port") from None
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or port not in {None, 80, 443}
        ):
            raise ValueError(
                "Propose plain public HTTP(S) URLs without credentials, query or fragment"
            )
        from ipaddress import ip_address

        hostname = parsed.hostname.lower()
        if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
            raise ValueError("Proposed source must be public")
        try:
            address = ip_address(hostname)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError("Proposed source must be public")
        if hostname.rstrip(".") in {"example.org", "example.com", "example.net"} or any(
            hostname.rstrip(".").endswith("." + domain)
            for domain in (
                "example.org",
                "example.com",
                "example.net",
                "example",
                "invalid",
                "test",
            )
        ):
            lines.append(
                "Withheld placeholder source URL; no real buyer source was identified. Use the next research step above; this suggestion adds no evidence."
            )
            continue
        lines.append(
            "Proposed public source (not read): "
            + url
            + " — "
            + _text(proposal.purpose, "research purpose", 500)
        )
    return lines


from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class ResearchOption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: Literal["documentation", "editing", "support_drafts"]
    skills: list[str] = Field(min_length=1, max_length=5)
    exercise: str
    checks: list[str] = Field(min_length=2, max_length=5)


class ResearchComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")
    options: list[ResearchOption] = Field(min_length=3, max_length=3)
    practice_choice: Literal["documentation", "editing", "support_drafts"]
    claims: list["ResearchClaim"] = Field(default_factory=list, max_length=20)
    next_sources: list["ProposedSource"] = Field(default_factory=list, max_length=5)


class ResearchClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: int = Field(strict=True, ge=1)
    service: Literal["documentation", "editing", "support_drafts"]
    quote: str
    relation: Literal["supports", "contradicts"]


class ProposedSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    purpose: str


ResearchComparison.model_rebuild()
