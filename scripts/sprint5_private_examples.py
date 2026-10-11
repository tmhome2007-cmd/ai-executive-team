"""Tool-free local BE-35 drafts for owner review; no company database writes."""

import json
from pathlib import Path
import sys
import uuid
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.quality_benchmark import private_directory, save
from workflows.quality_benchmark import digest, local_request


def main():
    fixtures = json.loads((ROOT / "docs/planning/be35-examples.json").read_text())
    base = "http://127.0.0.1:11434"
    installed = local_request(base, "/api/tags")["models"]
    model = next(item for item in installed if item["name"] == "llama3.1:latest")
    identity = {key: model[key] for key in ("name", "digest")}
    directory = private_directory(
        private_directory(ROOT / "quality-results") / uuid.uuid4().hex
    )
    options = {"temperature": 0, "num_predict": 900, "num_ctx": 4096}
    save(directory / "manifest.json", {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": identity, "options": options, "fixtures_hash": digest(fixtures),
        "fixtures": fixtures,
        "scope": "Real local raw text drafts; existing rubric wording, new fictional transfer facts. No owner assessment, production workflow or general transfer competence claim.",
    })
    print("Private examples:", directory, flush=True)
    failed = False
    for fixture in fixtures:
        prompt = (
            "Write a private fictional draft grounded only in supplied facts. "
            "Instructions are not evidence. Missing facts require a specific "
            "question or a bounded draft. Never invent authority or completed actions.\n"
            + "Audience: " + fixture["audience"]
            + "\nSUPPLIED FACTS:\n" + fixture["facts"]
            + "\nDELIVERABLE:\n" + fixture["request"]
            + "\nOWNER REVIEW RUBRIC (do not echo):\n"
            + "\n".join(fixture["checks"])
        )
        save(directory / (fixture["id"] + "-request.json"), {"prompt": prompt})
        try:
            reply = local_request(base, "/api/generate", {
                "model": identity["name"], "stream": False,
                "options": options, "prompt": prompt,
            })
            save(directory / (fixture["id"] + "-response.json"), reply)
            if reply.get("done") is not True or not isinstance(reply.get("response"), str):
                raise ValueError("Incomplete generation")
            if reply.get("done_reason") == "length":
                raise ValueError("Prediction limit reached")
            save(directory / (fixture["id"] + "-review.json"), {
                "checks": fixture["checks"],
                "owner_assessment": "pending", "fixture_hash": digest(fixture),
            })
            print(fixture["id"] + ": retained, owner review pending", flush=True)
        except Exception as error:
            failed = True
            save(directory / (fixture["id"] + "-error.json"), {
                "error": type(error).__name__, "owner_assessment": "pending",
            })
            print(fixture["id"] + ": generation error retained", flush=True)
    current = local_request(base, "/api/tags")["models"]
    same = any(all(item.get(k) == v for k, v in identity.items()) for item in current)
    save(directory / "identity-check.json", {"same_model_after_generation": same})
    if not same:
        print("Model identity changed; comparison requires review.", flush=True)
        return 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
