# BE-38 — private recovery guidance

Dated technical/research record; results and limitations apply to the versions described. Use [the README](../../README.md) for current status and planning.

Current status: owner accepted the documented bounded Sprint 5 scope on 11 October
2026; merged via [PR #50](https://github.com/tmhome2007-cmd/ai-executive-team/pull/50). Earlier pending/
not-merged entries below describe their original evidence stage. See
[closure record](../../README.md#development-status); known security/model-quality limits remain.

Implemented for owner review on 11 October 2026; not Done or merged.

The run inspector now provides a fixed recovery code and an explicit next step:
wait for a stopped worker, continue eligible private work, review saved output,
inspect a newer run, or create a newly reviewed exercise after a skill revocation,
workflow withdrawal or correction to the skill's supporting owner assessments.
Earlier samples, assessments, frozen research and artifact retention remain intact.
These corrections refer to owner assessments supporting a skill, not automatic
reclassification of frozen external research sources.

Continuation eligibility uses structured binding state and fixed messages instead
of raw exception text. The retained BE-37 implementation failed the new synthetic
exception-sanitization test; the corrected implementation passes. Rejected controls
refresh dashboard eligibility before another click. Existing transactional claims
and publication checks remain authoritative if a displayed button becomes stale.
No new acceptance, action authority, automatic replay or model inference is granted.
Uncertain external outcomes retain reconciliation guidance and no replay controls.

## Verification

- 25 targeted backend tests passed, including all three permission changes between
  inspection and claim and during generation; earlier sample/review history stays
  intact. Two concurrent continuation claims have exactly one winner, and neither
  claim alone publishes a sample.
- Existing stop/restart, cached private output, atomic publication, artifact-byte
  preservation and uncertain external checkpoint tests passed.
- Run API success, authentication, lookup, validation and stale-conflict responses
  retain `no-store` and `nosniff`; existing validation-error coverage also passed.
- Repository formatting/catalog checks and whitespace checks passed. Targeted
  Bandit found no medium/high findings. The full Sprint 5 audit remains outstanding.

Production build and all three browser features (`runs`, `skills`, `artifacts`)
passed, including corrected-assessment guidance, hidden polling, stop/continue
and mobile layout. Browser verification and private evidence locations are recorded in
`docs/planning/be38-verification.json`. Checks use disposable SQLite, synthetic
outputs and an owned loopback dashboard; they do not establish owner usefulness.
Failed browser runs are retained: the new next-step text exposed an ambiguous
locator, then the new combined fixture needed its disposable source IDs attached.
Both test-harness issues were corrected without relaxing behavior assertions.

Next independent implementation: BE-39 reproducible local model identity.
Owner usefulness acceptance, implementation PRs and merges remain pending.
