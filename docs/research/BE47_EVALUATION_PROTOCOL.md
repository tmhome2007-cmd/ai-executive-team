# BE-47 — frozen evaluation protocol

Dated technical/research record; results and limitations apply to the versions described. Use [the README](../../README.md) for current status and planning.

11 October 2026. Ready for review, not Done or merged. No model outputs or usefulness results have been generated.

## Frozen inputs

[Assets](../evaluation/sprint6/freeze.json) freeze eight development cases and eight held-out cases, independent of the earlier ten-fixture benchmark. They cover cross-domain tasks, missing facts, conflicting observations, unsupported counts and consent, unknown interfaces, causal overreach and instructions embedded in evidence. Each case supplies source IDs, preservation obligations, unknowns and prohibited claims.

The cases were authored and inspected by the implementer. They are held out from generation and repair, **not blind external validation**. They use related failure categories intentionally; passing them cannot establish unseen real-world competence. The separate private real-project brief is not part of either fictional split.

The frozen baseline prompt, rubric and exact file bytes are SHA-256 bound. Copies of the existing shared checker and benchmark code preserve their original interpretation before BE-48 changes. The original fixture, 24/30 and 30/30 reports are unchanged. New scores use a different rubric and denominator and cannot be presented as directly comparable gains.

The installed local `llama3.1:latest` digest was read through `/api/tags`:
`46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e`.
No inference, download or remote call occurred. Planned explicit request options: temperature 0, num_predict 1200, num_ctx 4096, seed 47; timeout 120 seconds, stream false, keep_alive 0, JSON baseline format. Remaining Ollama defaults are disclosed; this is not a deterministic guarantee or a claim that application-wide settings match this protocol.

## Assessment and run procedure

1. Tune BE-48 checks and BE-49 prompts only on development cases. Before any held-out generation, freeze candidate prompt, typed schema, adapter/checker code, complete request configuration and run Git SHA in a separate immutable candidate/run manifest. This baseline freeze does not authorize an incomplete candidate assessment.
2. Validate frozen input hashes, case separation and model digest. Re-resolve the model before and after generation. Stop on changed identity or assets; retain incomplete results. The current offline validator checks inputs only; runtime and contamination gates must be connected by the BE-49 runner, and are not claimed implemented here.
3. Run ascending case IDs, three repetitions each, baseline then candidate per slot. Each variant has 24 scheduled samples per split. Send the frozen prompt plus serialized question/source records/allowed next step; never send rubric obligations or expected answers. No tools, retrieval, business memory or external action.
4. Retain raw responses, failed attempts, repair attempts, safe error types, timings and slot IDs privately. No silently replacing failed slots. Initial and final repaired outcomes are separate; use the same declared repair allowance for comparable variants. Freeze that allowance in the candidate/run manifest before assessment.
5. Score four separate axes: schema validity, grounding, unsupported claims and usefulness. Semantic grounding requires manual review against actual source text and obligations, not token membership. Report automated warnings separately. Human usefulness stays unscored until a person reviews it; owner usefulness requires owner feedback. Report errors, incomplete slots and unscored denominators visibly.
6. Record generation access and repair use in an append-only private ledger. Any held-out case used for repair becomes development data. Do not edit this freeze or rerun and advertise the repaired result as untouched evaluation. Create a disclosed successor with new cases before another assessment. Private bytes follow existing 30-day retention; durable hashes, provenance and aggregate counts remain.

No second model is assumed or downloaded. A later comparison requires an already installed suitable model, its own frozen identity and disclosed configuration differences. No cloud or spending is authorized.

## Verification

Run from V2CHAT:

```sh
.venv/bin/python scripts/evaluation_protocol.py
./company test --pattern test_evaluation_protocol.py
```

Offline verification passed with freeze hash `76fa4d899057396f6fb57411ab3a91bd024d78fb9db7fd2ffae440ea49cd5d10`. Six regression tests passed: changed assets, overlap despite updated asset hash, incomplete contracts, duplicate IDs, arbitrary paths/symlinks, and rubric exclusion from generation input. These are protocol checks, not six successful model decisions.

Next: BE-48 develops general evidence checks on the development split; BE-49 freezes its actual structured candidate and connects runtime assessment gates. Final integration audit and owner acceptance remain pending.
