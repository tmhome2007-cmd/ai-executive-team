# BE-49 — one structured strategy path

Dated technical/research record; results and limitations apply to the versions described. Use [the README](../../README.md) for current status and planning.

11 October 2026. Implementation ready for review; real evaluation and final audit recorded separately.

The existing authenticated POST /decisions/trigger accepts output_mode=structured for strategy meetings with one to four distinct canonical executive roles. Legacy is the default; other meeting paths and historical text remain readable. No preparation, execution or approval gate is removed. The structured path uses the installed loopback Ollama model directly, passing the Pydantic JSON schema in `format` and validating the returned object locally. [Ollama's documented schema interface](https://github.com/ollama/ollama/blob/main/docs/capabilities/structured-outputs.mdx) informs the transport; actual installed behavior is assessed by the local runs, not assumed from documentation.

Each role retains its canonical backstory, produces its own source quotations, unknowns, assumptions, proposal, objections, success/stop criteria, pivotal fact and next owner decision. Trusted code assigns role identity; the CEO is last. Prior proposals are context, never new evidence. No tool or company-memory retrieval runs. All output remains a proposal for separate owner review.

Invalid schema, blank fields, fabricated references/quotations, detected unsupported claims, transport errors or changed local model identity prevent publication. Two attempts maximum; failed samples and safe error types remain owner-private. No legacy fallback, remote provider fallback, model downloads or automatic action proposals exist. Request settings and model identity are recorded. Full interpretation still requires review; schema and quotations cannot prove usefulness or rule out every misleading sentence.

The readable brief and JSON role contributions use existing decision/contribution persistence and authenticated reads; the new decision starts pending. Generated samples under WORKSPACE_ROOT/structured-decisions expire through existing artifact retention, preserving non-sensitive provenance. Caller failures use safe event/type logging and controlled responses.

Ten structured regressions and six evaluation/retention regressions passed, covering repair retention, malformed/provider failures, attribution, identity drift, authenticated persistence, failed publication, pending approval, private headers, contamination and expired bytes. Initial fixture errors remain documented privately.

The independent evaluator freezes candidate prompt/schema/persona/adapter/checker/options before held-out generation and blocks a second untouched held-out claim. It preserves 48 scheduled slots (24 per variant), errors, incomplete slots and first-attempt versus repaired outcomes. Semantic and owner scores stay unscored until the required review. The one-role benchmark is not a score for the whole multi-role meeting.

## Independent assessment finding

The original eight-case assessment on 74d0a5e had 24/24 valid schemas and response contracts per variant, but qualitative review found a candidate following an embedded instruction to assume permissions. Formal success did not establish authority safety or usefulness. The final guard rejects that preserved answer. held-08 is now development data; the original freeze and reports were not rewritten. [Case-status overlay](../evaluation/sprint6/case-status.json) and [original measurements](../planning/be49-held-out-verification.json) record this distinction.

A separately frozen replacement scenario ran three samples per variant without repairs after the fix; both had 3/3 valid schemas/contracts. [Replacement measurements](../planning/be49-replacement-verification.json) are a one-case check, not a fresh full benchmark or directly comparable score. Semantic grounding and owner usefulness remain unscored; vague criteria still occur. No further tuning used that replacement.
