# BE-37 — earlier browser and calendar checks

Current status: owner accepted the documented bounded Sprint 5 scope on 11 October
2026; merged via [PR #50](https://github.com/tmhome2007-cmd/ai-executive-team/pull/50). Earlier pending/
not-merged entries below describe their original evidence stage. See
[closure record](SPRINT_5_CLOSURE.md); known security/model-quality limits remain.

11 October 2026. Implemented for review; not Done or merged.

Implementation: `e5fa8867b27470254a3c6840d71a2c63beb03b89` on
`codex/sprint-5-be37`. Tested source hashes match this commit.

## Earlier checks

`./company check-ui` builds the production dashboard and runs navigation/design,
run-inspector, experiment/calendar and business-discovery checks. After a change,
select the affected features, for example `./company check-ui runs experiments`.
`./company check-ui --all` runs all 15 existing browser features. Experiments run
in both UTC and Europe/Brussels, so all features produce 16 browser cases.

The runner creates its own loopback server on an available port, uses disposable
SQLite/in-process APIs and synthetic public reads, and stops only its own server.
It does not load the company launcher environment, replace a key, reset company
records, or run a model/executor. Normal installed development dependencies are
required; existing dependencies were copied into this separate checkout for
verification without copying company credentials or databases.

Shared helpers now open destinations by exact navigation name, handle the
collapsed mobile menu and wait for the actual destination heading. All 15 browser
scripts use those helpers. Business-section navigation waits for the selected
panel and keeps draft input intact across those sections. Early and full audit
runners share the same feature registry; the full audit also accepts Sprint 5
development branches. No existing audit stage was removed.

## Calendar and timestamp fix

A fixed-clock regression reproduced incorrect latest-observation selection:
`12:00:00Z` sorted ahead of the later `12:00:00.000001Z` when sorted as text.
New timestamps normalize to six fractional digits. Observation selection and
pagination compare the UTC seconds and fraction separately, treating legacy
whole seconds as a zero fraction. Legacy bytes remain immutable. Equivalent
retries normalize the saved timestamp for comparison without rewriting it.

Execution-order validation still parses actual timestamps. A measurement one
microsecond before recorded execution is rejected; equal/later measurements are
accepted. The future-measurement guard remains. Calendar cases cover the worldwide
date boundary, UTC/local offsets, leap day and invalid dates. Production forms
verify fixed winter/summer UTC conversions and fractional observation timestamps
in UTC and Brussels browser contexts.

## Verification

| Check | Actual result |
|---|---|
| Fixed-clock regressions before correction | 6 run, 2 failed: precision and latest-observation ordering |
| Same regressions after correction | 6 passed |
| Targeted experiment/calendar/launcher/integration/operating tests | 39 passed |
| Final early production suite | 17/17 stages: one build and 16 browser cases |
| Desktop/mobile navigation | All 15 destinations; menu closes after each mobile selection |
| Draft retention | Research title survives research/skills/run-inspector subsection changes |
| Hidden polling | No run polling in a hidden panel or hidden browser document; visible polling resumes |
| Representative navigation regression | Deliberately blocked destination fails the helper check; removing the block restores passing navigation |
| Maintenance and security | Black, Prettier, catalog and whitespace checks passed; targeted Bandit found no medium/high issue |

The first production suite retained a failed mobile-helper check. Its role query
excluded hidden navigation before opening the menu. The corrected helper includes
the hidden navigation element when locating it, then opens the menu and checks the
destination. The final full feature rerun passed.

Private reports:
`audit-results/be37-892198a2382748f1ad128454a9af163e` (initial failure),
`audit-results/be37-a5baea6c61904474af6362e624e72b58` (final pass, including fixed-clock
before/after and backend logs). Report/source identities are summarized in
[be37-verification.json](docs/planning/be37-verification.json). Generated logs use
the existing 30-day retention boundary and owner-only storage.

The full integration/security/privacy audit remains BE-41. These early checks do
not clear known upstream advisories or record owner usefulness acceptance. Budget
and permitted loss remain €0. BE-38 can now build on the verified navigation and
recovery-test foundation.
