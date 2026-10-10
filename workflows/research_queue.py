"""Explicit owner public reads with durable payload recovery and atomic evidence linking."""

import hashlib
import json
from memory.research_queue import claim_read, finish_read
from workflows.business_discovery import fetch_public_source
from workflows.step_checkpoints import run_json_step, get_step, init_step_checkpoints


def read_proposal(ident, expected_version):
    init_step_checkpoints()
    row = claim_read(ident, expected_version)
    if row["state"] == "fetched":
        return row
    digest = hashlib.sha256(row["url"].encode()).hexdigest()
    try:
        previous = (
            get_step(f"source-queue:{ident}", row["previous_checkpoint_step"])
            if row["previous_checkpoint_step"]
            else None
        )
        cached = None
        if (
            previous
            and previous["status"] == "succeeded"
            and previous["input_digest"] == digest
            and previous["result_json"] is not None
        ):
            cached = json.loads(previous["result_json"])
        payload = run_json_step(
            f"source-queue:{ident}",
            row["checkpoint_step"],
            digest,
            lambda: cached if cached is not None else fetch_public_source(row["url"]),
        )
        return finish_read(ident, row["version"], payload)
    except BaseException:
        try:
            finish_read(ident, row["version"])
        except RuntimeError:
            pass
        raise
