# BE-49 — one structured strategy path

11 October 2026. Implementation ready for review; real evaluation and final audit recorded separately.

The existing authenticated POST /decisions/trigger accepts output_mode=structured for strategy meetings with one to four distinct canonical executive roles. Legacy is the default; other meeting paths and historical text remain readable. No preparation, execution or approval gate is removed. The structured path uses the installed loopback Ollama model directly, passing the Pydantic JSON schema in `format` and validating the returned object locally. [Ollama's documented schema interface](https://github.com/ollama/ollama/blob/main/docs/capabilities/structured-outputs.mdx) informs the transport; actual installed behavior is assessed by the local runs, not assumed from documentation.

Each role retains its canonical backstory, produces its own source quotations, unknowns, assumptions, proposal, objections, success/stop criteria, pivotal fact and next owner decision. Trusted code assigns role identity; the CEO is last. Prior proposals are context, never new evidence. No tool or company-memory retrieval runs. All output remains a proposal for separate owner review.

Invalid schema, blank fields, fabricated references/quotations, detected unsupported claims, transport errors or changed local model identity prevent publication. Two attempts maximum; failed samples and safe error types remain owner-private. No legacy fallback, remote provider fallback, model downloads or automatic action proposals exist. Request settings and model identity are recorded. Full interpretation still requires review; schema and quotations cannot prove usefulness or rule out every misleading sentence.

The readable brief and JSON role contributions use existing decision/contribution persistence and authenticated reads; the new decision starts pending. Generated samples under WORKSPACE_ROOT/structured-decisions expire through existing artifact retention, preserving non-sensitive provenance. Caller failures use safe event/type logging and controlled responses.

Ten structured regressions and four evaluation/retention regressions passed, covering repair retention, malformed/provider failures, attribution, identity drift, authenticated persistence, failed publication, pending approval, private headers, contamination and expired bytes. Initial fixture errors remain documented privately.

The independent evaluator freezes candidate prompt/schema/persona/adapter/checker/options before held-out generation and blocks a second untouched held-out claim. It preserves 48 scheduled slots (24 per variant), errors, incomplete slots and first-attempt versus repaired outcomes. Semantic and owner scores stay unscored until the required review. The one-role benchmark is not a score for the whole multi-role meeting.
