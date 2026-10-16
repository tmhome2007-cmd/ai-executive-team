"""Fictional local-model contract measurements, never approval or truth certification."""

import hashlib
import inspect
import json
import re
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

from workflows.output_quality import QUALITY_POLICY, assess_output

RUBRIC_VERSION = "fictional-json-contract-shared-v4"
PROMPT = QUALITY_POLICY + """
For this fictional benchmark return only a JSON object with exactly three keys:
findings (list of concise strings), unknowns (list of strings), next_action (string).
Preserve supplied facts and explicitly identify the named unknown. Recommend an
observation or private review only. Never invent approval, interface controls,
causes, completed external actions or money. No Markdown fences.
"""
OPTIONS = {"temperature": 0, "num_predict": 400, "num_ctx": 4096}


def digest(value):
    """Hash a canonical snapshot, including checker code when supplied as text."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


class NoRedirect(HTTPRedirectHandler):
    """Local inference must never follow a redirect to an external service."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def local_request(base, endpoint, payload=None):
    """Call only loopback Ollama without environment proxy forwarding."""
    url = urlsplit(base)
    if (
        url.scheme != "http"
        or url.hostname not in {"localhost", "127.0.0.1", "::1"}
        or url.username
        or url.password
        or url.path not in {"", "/"}
        or url.query
        or url.fragment
    ):
        raise ValueError("Quality benchmark requires a loopback HTTP Ollama URL")
    request = Request(
        base.rstrip("/") + endpoint,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with build_opener(ProxyHandler({}), NoRedirect()).open(
        request, timeout=120
    ) as reply:
        body = reply.read(1_000_001)
    if len(body) > 1_000_000:
        raise ValueError("Oversized model response")
    return json.loads(body)


def assess(raw, fixture):
    """Check narrow structure/fact coverage; matching tokens cannot prove truth."""
    errors = assess_output(raw, fixture["facts"])
    try:
        obj = json.loads(raw)
        if not isinstance(obj, dict) or set(obj) != {
            "findings",
            "unknowns",
            "next_action",
        }:
            raise ValueError
        for key in ("findings", "unknowns"):
            if (
                not isinstance(obj[key], list)
                or not 1 <= len(obj[key]) <= 3
                or any(not isinstance(x, str) or not x.strip() for x in obj[key])
            ):
                raise ValueError
        if not isinstance(obj["next_action"], str) or not obj["next_action"].strip():
            raise ValueError
    except (ValueError, TypeError):
        return list(dict.fromkeys(errors + ["Invalid bounded JSON report contract"]))
    findings = " ".join(obj["findings"]).lower()
    unknowns = " ".join(obj["unknowns"]).lower()
    for token in fixture["required"]:
        if token.lower() not in findings:
            errors.append("Supplied fact not covered: " + token)
    if fixture["unknown"] not in unknowns:
        errors.append("Named uncertainty not preserved: " + fixture["unknown"])
    if (
        re.search(r"\b(?:click|tap|press)\b", raw, re.I)
        and "interface unknown" in fixture["facts"].lower()
    ):
        errors.append("Invented interface instruction")
    return list(dict.fromkeys(errors))


def checker_identity():
    """Bind actual check functions, excluding prompt text and transport code."""
    return digest(
        {
            "rubric": RUBRIC_VERSION,
            "checks": inspect.getsource(assess),
            "shared_checks": inspect.getsource(assess_output),
        }
    )


def comparable(left, right):
    """Reject changed datasets/checkers; do not silently compare different rubrics."""
    for key in ("dataset_hash", "checker_hash", "rubric_version"):
        if left[key] != right[key]:
            raise ValueError("Runs have different datasets or rubrics")
    return {
        "left": left["summary"],
        "right": right["summary"],
        "prompt_changed": left["prompt_hash"] != right["prompt_hash"],
        "model_changed": left["model"] != right["model"],
        "configuration_changed": left["options"] != right["options"],
        "limit": "Automated contract measurements only; no competence or business claim",
    }
