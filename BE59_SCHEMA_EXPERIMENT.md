# Small actionable-schema experiment

12 October 2026. Owner explicitly requested a small schema on a branch, a three-variant local-model test, and merging only if outputs improve. Branch: codex/sprint-7-actionable-schema. No dependency, cloud model or action executor is added. This experiment is separate from the production structured meeting path until its usefulness gate passes.

## Contract and comparison

workflows/actionable_plan.py defines two to four owner-only steps with estimated minutes, an explicit not_sent draft for outreach, a proposed stopping window, rationale, source quotations, unknowns, assumptions, success, pivotal fact and the next owner choice. Context validates summed effort against the confirmed owner limit. Quotes and existing unsupported-claim guards still apply. Structural validity is not semantic correctness.

scripts/sprint7_schema_experiment.py freezes the supplied private question, two hypothetical contact variants, exact code hashes, installed model digest, options, canonical CEO persona and rubric before inference. The original owner example and variants are development cases, not held-out cases. Baseline uses the unchanged structured Contribution schema. Candidate uses OwnerPlan. Both are isolated canonical CEO generations without previous speeches: this controls the schema/prompt comparison and does not assess the full three-role team or short-request intake.

Three repetitions per case per variant: nine baseline and nine candidate samples, eighteen total. Identical installed llama3.1 model, temperature 0, seed 47, num_ctx 4096, num_predict 1200, local transport timeout 120 seconds, no repairs. Alternate order by repetition. Same-setting repetitions are not independent statistical variance estimates. All scheduled slots, raw failures, errors, timing and incomplete runs are retained privately. Compare provider identity before and after. No prompt tuning after seeing this frozen run.

## Predeclared usefulness gate

Report schema validity and quote/claim validation separately. All nine candidate outputs must validate without repairs. There must be no critical authority or factual failure. At least six of nine candidate answers, including at least two per contact variant, must satisfy all semantic axes below; matched baseline completeness must improve. Recently responsive versus silent conditions must differ in all three pairs. A conditional merge authorization is not permission to weaken this gate. Analyst assessment is labelled; owner usefulness acceptance remains separate.

Semantic axes: concrete steps and effort breakdown; usable unsent draft if outreach appropriate; tool availability check before inviting use; correct owner responsibility without invented facts; stopping window without repeated-pressure plan; own live-case eligibility and structured feedback; contact clarification changes route/conditions. Fields present but vague or irrelevant fail the axis. A new draft is not evidence of sent outreach or customer use.

## Limits and evidence

No migration of historical contributions, production request changes, team critique changes, normal launcher repair, new held-out transfer score or full Sprint 7 completion is claimed. Six contract regressions cover actor and status authority, confirmed time/sum, conditional drafts, stop-window shape, fabricated quotes/permission, blank steps and JSON roundtrip. The subsequent run and semantic review will be appended here; a failed gate leaves the branch unmerged and retains failures.

## Completed comparison and decision

Frozen implementation: 81559e7. Exact digest/options/code hashes and private report hashes are in [verification metadata](docs/planning/be59-schema-verification.json). Eighteen scheduled generations completed, with zero repairs, errors or identity drift. No source assets changed during inference.

| Contact variant | Baseline schema / validated | Candidate schema / validated | Candidate complete usefulness |
|---|---|---|---|
| A · original unknown relationship | 3/3 · 3/3 | 3/3 · 3/3 | 0/3 |
| B · different founder recently replied | 3/3 · 3/3 | 3/3 · 3/3 | 0/3 |
| C · same founder silent after offer | 3/3 · 3/3 | 3/3 · 3/3 | 0/3 |

Both variants validated **9/9 (100%)**. Full semantic rubric: baseline 0/9, candidate 0/9, assessed by Codex rather than the owner or an automated keyword checker. Each case/variant had one byte-identical output across three repetitions: six unique answers represent eighteen scheduled samples. These counts are not nine independent trials per variant or a population reliability estimate. Median observed request duration: baseline 47.43 seconds, candidate 67.43 seconds; workload ordering/hardware are not controlled enough to attribute this difference to schema alone.

The candidate adds owner actor fields, estimated minutes and explicitly unsent drafts. The responsive-contact draft genuinely asks about a current live case. These are partial improvements, not complete usefulness passes. All candidate answers omit a current tool check before invitation and fail to give a usable testing/structured-feedback process. They use desired agreement/confirmation as the stopping condition. Steps mostly repeat drafting and checking a hypothetical reply instead of spelling out the proposed owner workflow. Unknown identity in A is not a route prerequisite. Silence/date in C are not weighed as a risk or explicit contingency; it still assumes continuing interest and recontacts that lead. Wording/eligibility emphasis changes between B/C, but useful sensitivity to prior silence is not established.

The baseline silent-case answer does supply a bounded effort stop; that partial merit is retained in the semantic review. No forced diversity, rewording requirement or blanket zero-quality claim is used. Each original output and per-axis rationale remains in ignored owner-only storage. No regenerated success replaces the failed candidate.

**Decision: do not merge.** The frozen minimum of six complete candidate passes, including two per case, is unmet. The conditional owner merge authorization therefore does not activate. The prototype remains isolated on its branch; the normal app still uses its existing structured path. No push, PR, main merge, production enablement or owner acceptance is recorded.

Validation: six new contract tests, three frozen-run integrity tests and ten existing structured-decision tests passed. Black, targeted Bandit medium/high and generated catalog checks passed. No full Sprint 7 audit or production-browser acceptance is claimed for this isolated prototype. New raw experiment artifacts are subject to the existing owner-private 30-day policy; production integration must include their retention selector rather than assuming the Sprint 6 selector already covers them.

## Next focused change

Keep this failed run as development evidence. Before another generation, freeze a revised candidate and a new evaluation record; do not overwrite this freeze or treat these contact variants as untouched tests. A next prototype should separate source-backed intake/prerequisites from plan generation, use a stopping trigger that cannot be confused with success, and require concrete live-case/feedback deliverables. Unknown contact identity and previous silence need explicit plan conditions. Those are proposed next changes, not silently implemented prompt repairs. Short-request intake, independent-role discussions and reserved transfer assessment remain later Sprint 7 scope.
