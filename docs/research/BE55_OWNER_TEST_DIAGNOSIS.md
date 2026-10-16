# BE-55 — owner-test diagnosis

Dated technical/research record; results and limitations apply to the versions described. Use [the README](../../README.md) for current status and planning.

12 October 2026. Read-only diagnosis on the Sprint 7 planning base. No regenerated answer, model call or product change. Original private samples and disposable database were read without mutation. Private trace metadata: audit-results/sprint7-diagnosis/owner-run-trace.json (ignored, owner-only). No owner business text is copied into this document.

## What was verified

All three first-attempt raw contributions were valid under the current schema. Their parsed JSON exactly matches stored decision contributions. The saved decision text exactly matches the retained private brief; render_brief reproduces that saved text. The dashboard component renders every nonempty line and does not select or hide particular generated fields. This source inspection plus exact backend comparisons supports the conclusion that the requested deliverables were never generated as separate content, rather than lost by the dashboard. No new interactive browser assertion is claimed.

| Symptom | Observed layer | Implication |
|---|---|---|
| No execution steps or draft message | Missing from raw outputs; no corresponding Contribution fields | Extend the contract, not only the prompt or UI |
| Wrong proposed actor | Present in raw final-role next_owner_decision, retained in saved text | Typed actor constraints plus content/semantic review are required |
| Stop count without time window | Present in final raw field; another role supplied a different stopping window | Synthesis chose the final role without evaluating the stronger alternative |
| Near-identical proposals | Raw recommendations similar; later roles receive earlier recommendations/objections | Exposure is verified; copying as its cause remains a hypothesis |
| Only one wording match | render_brief compares exact strings | Normalize punctuation/case/whitespace; do not equate matching words with agreement |
| No objections | Raw lists empty; allowed by schema | Do not fabricate objections; evaluate independent proposal and critique behavior |
| Clarification does not visibly alter plan | Relevant unknown appears but plan does not condition on it | Paired factual variants are needed; one run cannot establish counterfactual sensitivity |

## Exact path, rather than assumed legacy behavior

main.py dispatches structured strategy requests directly to run_structured_decision. It does not run the legacy CrewAI discussion/critique/revision rounds. Roles run sequentially, CEO last, with only earlier recommendations and objections as reasoning context; they do not receive all earlier raw outputs. Canonical role backstories remain in the prompt. Contribution requires bounded quotations, unknowns, assumptions, recommendation, objections, success, stop, pivotal fact, next owner decision and total effort. It lacks step, draft, actor and stop-window fields. extra=forbid prevents introducing new JSON keys; the existing generic strings are not a reliable substitute for those deliverables.

The validator checks shape/nonblank fields, quote membership and selected unsupported claims. It does not establish completeness against all user requirements, correct outreach ownership or decision usefulness. The renderer selects the CEO proposal and criteria; it is an attributed display, not an independently generated synthesis weighing alternatives.

## Transport findings are separate

The temporary launcher originally passed an aliased macOS /var path to a guard that rejects symlink ancestors. Resolving the temporary root fixed that launcher error while preserving the guard. Its proxy also had a short timeout: the browser errored while generation continued, then the decision was saved. The launcher now uses a direct local API connection. Neither local launcher fix is normal ./company startup validation. BE-62 should address normal installation, request identity/status recovery and duplicate prevention; a browser error must not be treated as proof the decision failed.

## Recommended next development checks

Freeze the completeness/authority rubric and new transfer cases before changing production schema or prompts (BE-56). Exercise factual variants for plan sensitivity. Treat this owner run as development data, not held-out evidence. Preserve original raw files and metrics; assess structure and semantic usefulness separately. BE-55 is ready for review, not Done; the owner has not accepted this answer.
