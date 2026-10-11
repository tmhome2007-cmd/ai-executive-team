"""Read-only, bounded local Ollama identity resolution; no pull or fallback."""

import json
import math
import re
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def resolve_model(llm, mode=False):
    """Resolve the configured tag using Ollama GET /api/tags only."""
    message = "Local model identity unavailable; restore the installed local model and retry. No model is downloaded."
    try:
        base = urlsplit(str(llm.base_url))
        provider = getattr(llm, "provider", None)
        model = str(llm.model)
        if provider != "ollama" and not (not provider and model.startswith("ollama/")):
            raise ValueError()
        tag = model.removeprefix("ollama/")
        if (
            base.scheme != "http"
            or base.hostname not in {"localhost", "127.0.0.1", "::1"}
            or base.username
            or base.password
            or base.query
            or base.fragment
            or base.path.rstrip("/") not in {"", "/v1"}
            or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,120}", tag)
        ):
            raise ValueError()
        canonical = tag if ":" in tag.rsplit("/", 1)[-1] else tag + ":latest"
        url = base._replace(path="/api/tags").geturl()
        opener = build_opener(ProxyHandler({}), NoRedirect())
        with opener.open(
            url, timeout=5
        ) as response:  # nosec B310 # Validated loopback HTTP; redirects disabled.
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError()
        models = json.loads(raw)["models"]
        matches = [m for m in models if m.get("name") in {tag, canonical}]
        if len(matches) != 1 or not re.fullmatch(
            r"(?:sha256:)?[0-9a-f]{64}", str(matches[0].get("digest", ""))
        ):
            raise ValueError()
        # Only these inference settings are recorded, never arbitrary SDK kwargs.
        settings = {
            key: getattr(llm, key, None)
            for key in ("temperature", "max_tokens", "timeout")
        }
        if mode in {"revision", "task_guide"}:
            settings.update(temperature=0.0, max_tokens=2000, timeout=120)
        for value in settings.values():
            if value is not None and (
                type(value) not in {int, float} or not math.isfinite(value)
            ):
                raise ValueError()
        settings.update(
            provider="ollama",
            tag=tag,
            resolved_tag=matches[0]["name"],
            endpoint=base.geturl().rstrip("/"),
            response_mode=str(mode),
            other_options="SDK and Ollama defaults; not a deterministic generation guarantee",
        )
        return dict(
            digest=matches[0]["digest"].removeprefix("sha256:"), configuration=settings
        )
    except Exception:
        raise RuntimeError(message) from None


def assert_identity(previous, current):
    """Legacy rows cannot acquire identity retroactively or reuse saved output."""
    if not previous.get("model_digest") or not previous.get("model_config_json"):
        raise RuntimeError(
            "Earlier model identity is unknown; create a new owner-reviewed exercise. Existing output is retained."
        )
    if (
        previous["model_digest"] != current["digest"]
        or json.loads(previous["model_config_json"]) != current["configuration"]
    ):
        raise RuntimeError(
            "Local model identity or configuration changed; create a new owner-reviewed exercise. Existing output is retained."
        )
