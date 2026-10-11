# BE-48 — general evidence checks

11 October 2026. Ready for review; final audit pending.

The shared checker now uses labels extracted from supplied records or a caller's explicit known-field contract. It contains no list of original benchmark field names. Word boundaries avoid confusing a field with a longer unrelated word; explicit unknown values do not become known facts. Structured contributions use exact source-ID/quotation membership checks and bounded typed fields. These checks do not establish semantic entailment or source truth.

Policy version is 3; the existing fictional benchmark now labels its changed checker `fictional-json-contract-shared-v3`. Original v1 fixtures and historical 24/30 and 30/30 results remain unchanged. Original checker code is frozen under docs/evaluation/sprint6. Hash and rubric gates prevent silently comparing the changed measurement with old scores.

Ten output-quality regressions and six benchmark/replay regressions passed. They include arbitrary field labels, explicit contracts, supplied/unknown values, substring false positives, fabricated source IDs, altered quotations, short fragments, consent and causal overreach. Development generations use only the declared development split. Held-out results are for the later assessment, never repair input.

Limits: labels/regex/quote membership are bounded warnings, not general reasoning verification. A valid quote does not validate the recommendation attached to it. Human grounding and usefulness remain separate axes.
