"""One bounded local greeting; native generate never installs a missing model."""

import json
from pathlib import Path
import sys
from types import SimpleNamespace
from urllib.request import ProxyHandler, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workflows.local_model_identity import NoRedirect, resolve_model


def greeting():
    llm = SimpleNamespace(
        provider="ollama", model="llama3.1", base_url="http://localhost:11434"
    )
    identity = resolve_model(llm)
    request = Request(
        "http://localhost:11434/api/generate",
        data=json.dumps(
            {
                "model": identity["configuration"]["resolved_tag"],
                "prompt": "Synthetic test only. Reply with one short greeting.",
                "stream": False,
                "options": {"temperature": 0, "num_predict": 32},
            }
        ).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with build_opener(ProxyHandler({}), NoRedirect()).open(
        request, timeout=180
    ) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise RuntimeError("Local model response exceeded the audit limit")
    result = json.loads(raw)
    if (
        not result.get("done")
        or not isinstance(result.get("response"), str)
        or not result["response"].strip()
    ):
        raise RuntimeError("Local model did not finish a nonempty greeting")
    if resolve_model(llm)["digest"] != identity["digest"]:
        raise RuntimeError("Local model identity changed during the audit greeting")
    print(
        json.dumps(
            {
                "scope": "Real local tool-free greeting; no usefulness assessment",
                "digest": identity["digest"],
                "response": result["response"],
            }
        )
    )


if __name__ == "__main__":
    greeting()
