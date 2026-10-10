# Backend agile roadmap

Planning baseline: 8 October 2026. Proposed priorities; owner can change ordering.
Two boards serve different purposes: Development tracks building this product; Company
tracks the executives' business work. Neither task status nor assignment grants execution
or spending authority. Existing approvals, capabilities and treasury gates remain in force.

## Sprint 1 — make company work visible

| Ready | In progress | Review | Done |
|---|---|---|---|
| — | — | — | BE-01–14: owner accepted Sprint 1 on 9 October 2026 |

- [x] BE-12 Face, body and voice profiles — owner tested and accepted.
- [x] BE-13 Departments and employee lifecycle — owner tested and accepted.
- [x] BE-14 Fictional personal lives — owner tested and accepted.

The owner approved merge after local review. Gender-aware character presentation and
higher-quality voices are accepted follow-up work for Sprint 2, at low priority.
The sprint expanded beyond its original BE-01–03 scope by explicit owner requests.

## Backlog and acceptance criteria

| ID | Priority | Feature | Acceptance criteria | Dependencies |
|---|---|---|---|---|
| BE-01 | First sprint | Development and company agile boards | Separate boards; task owner, priority, status and acceptance criteria; company tasks link to valid goals/decisions/actions; stale updates rejected; completion note required; board movement does not execute work | Existing owner auth and company records |
| BE-02 | First sprint | Append-only activity event ledger | New transitions retain actor, source, previous/new state and timestamp; retries do not duplicate events; timeline reads retained events; legacy gaps are explicit | BE-01 and existing workflow state functions |
| BE-03 | First sprint | Experiments and observation plans | Hypothesis, baseline, expected result, budget/risk limit, linked action, observation dates and evidence; compare results without inventing missing measurements | Existing outcomes, treasury and follow-ups |
| BE-04 | Next | Evidence/source registry | Conclusions and observations reference dated sources; provenance and freshness visible; missing/conflicting evidence stays explicit | BE-03 |
| BE-05 | Next | Executive planning and workload | Executives propose assigned tasks and dependencies; owner reviews plan; scheduler respects active goals, budgets and execution gates; no duplicate runs | BE-01, BE-02 |
| BE-06 | Next | Structured executive discussion rounds | Persist published proposals, critiques, revisions and final synthesis with speaker and round; persona retained; guard unsupported owner claims | Existing contributions, BE-04 |
| BE-07 | Next | Scoped connector/capability inventory | Track requested/provided/verified access separately; credentials stay in secret storage; health/revocation checks; resource fulfillment grants only configured scope | Existing resources/capabilities |
| BE-08 | Later | Structured operating policies | Owner-defined risk limits, spending limits, approval boundaries and prohibited activities persist and are checked consistently | Existing treasury and approval gates |
| BE-09 | Later | Memory reconciliation | Source-backed memories can be corrected, superseded or expired without deleting provenance; contradictory lessons surface for review | BE-04, existing memory |
| BE-10 | Later | Reliable observation scheduling | Persist due dates, retries and claimed observation jobs; restart-safe execution; data collection uses approved capabilities | BE-03, existing checkpoints |
| BE-11 | Office support | Agent activity stream | Authorized consumers receive real task/meeting/role events; reconnect/resume supported; idle/unknown distinct; bounded retention | BE-02, BE-05 |
| BE-12 | Office support | Face, body and voice profiles | Versioned per-agent visual/voice references and preferences; existing identity/personality preserved; owner chooses assets/providers | Existing profiles |
| BE-13 | Office support | Departments and employee lifecycle | Persist organizational roles, capacity and relationships to work; employees cannot inherit executive authority automatically | BE-05, BE-08 |
| BE-14 | Future simulation | Virtual personal lives | Separate simulation records for relationships, marriages/divorces and personal events; clearly fictional; no influence on real approvals or business evidence unless owner defines a policy | BE-12, BE-13 |

## Definition of ready

The user story, expected behavior, acceptance criteria, dependencies and approval impact
are clear. External integrations require a chosen provider and known access/cost limits.

## Definition of done

The feature has persisted backend state, bounded authenticated APIs, required migrations,
relevant regression checks, clear empty/error states, a usable dashboard surface where
needed, documentation and owner review. Known upstream dependency advisories remain a
separate register rather than invented development tickets with no available fix.

## This sprint's decision

Build BE-01 first. Then prefer BE-02 before expanding autonomous behavior: a real retained
event ledger supports trustworthy history and the future 3D activity stream. BE-03 then
turns actions into experiments with measurable learning. Frontend 3D rendering is a
separate implementation track once these event and identity contracts are stable.

## Work log — 9 October 2026

BE-02 is in Review: transactional append-only events, initiating actor/source, state
changes, legacy snapshots and stable cursor pagination are implemented and verified.
43 tests passed (one opt-in Docker test skipped), 150/150 foundation checks passed,
Bandit has no medium/high findings, frontend lint/build passed, and the real SQLite/API
Chromium board smoke verified retained task transitions. Owner review remains.

Product direction: build towards evidence-backed revenue and profit. Experiments must
separate planned results from observed results, track costs and require supporting
evidence. Funding is capital, not automatically revenue; forecasts are not earnings.

BE-03 is in Review: owner-defined hypotheses, unknown-aware baselines/targets, linked
pending actions, planned observation dates, budget/risk gates, frozen approval-bound
plans, immutable idempotent evidence observations and the Experiments dashboard view.
The combined suite passed 49 tests with one unchanged opt-in Docker test skipped;
150/150 foundation checks, Bandit medium/high, lint/build and both real SQLite/API
Chromium feature smokes passed. BE-02 commit: a707b5f. Owner review remains for both.
The next candidate is BE-04, currently Backlog rather than Ready.

The checked-in roadmap and new-board template reflect this work. Existing runtime
boards are deliberately not overwritten by reseeding. The current default local DB
has not loaded the board migration; restart the isolated backend with its original
test environment/database before reviewing/updating existing cards.

## BE-04–07 implementation — 9 October 2026

Owner explicitly requested BE-04 through BE-07 together. All four are implemented
and enter **Review**, with an Organizational work dashboard surface:

- BE-04: immutable dated source provenance, freshness/review labels, source links,
  explicit missing/context-only/conflicting evidence and observation integration.
- BE-05: validated executive-proposed task graphs, owner plan review, company cards,
  budget/goal/dependency-aware single claims, scheduled tool-free recommendations,
  workload counts and separate result review.
- BE-06: durable proposal/critique/revision/CEO-synthesis rounds with canonical persona
  snapshots, source links and guarded owner-consent claims.
- BE-07: requested/provided/verified access, fixed GitHub/local-browser health adapters,
  manual inventory, metadata-only secret references, expiry/refresh/revocation and
  exact approval-bound action scope checks.

Details, owner test steps and integration limits are in ORGANIZATIONAL_WORK.md.
New records are retained in database backups; cross-machine sync does not yet include
these organizational tables. No real provider credentials, business execution or
spending was used during verification. Existing runtime boards remain untouched by
reseeding, and owner review is required before moving these cards to Done.

Final local verification: **68 tests passed, one unchanged opt-in Docker test skipped**;
150/150 foundation checks; pip check; Bandit medium/high; frontend lint and Webpack
build; and all three SQLite/API Chromium feature smokes (boards, experiments,
organizational work). Lint retains the existing image warning. Provider tests were
synthetic, and live model-quality/provider-permission trials remain owner checks.

## Operating foundation sprint — 9 October 2026

BE-08 through BE-11 are implemented on `codex/operating-foundation-sprint`
and moved to Review in the development template. Existing boards retain owner
edits. Owner review is still required before marking them Done.

- BE-08: immutable policy versions; cost/risk/type limits checked inside approval
  and execution transactions; policy changes invalidate earlier approval seals.
- BE-09: source-backed correction, supersession, conflict review and expiry;
  original lessons and revisions remain; unsuitable lessons are withheld from agents.
- BE-10: durable, atomic observation claims, bounded source retries and interruption
  recovery; owner-confirmed structured sources or independently approved file reads.
- BE-11: actual task start/completion metadata, authenticated cursor replay/SSE,
  bounded sessions and explicit unknown states; Operations dashboard controls.

See [OPERATING_FOUNDATION.md](OPERATING_FOUNDATION.md) for scope and verification.
External observation providers, unrestricted autonomous spending and the 3D office
are future work. These features do not enable production deployment.

## Character, workforce and simulation sprint — 9 October 2026

BE-12–14 are in Review on `codex/identity-organization-simulation`. New development
board templates include these as Review; existing boards keep owner edits.

- BE-12: versioned visual/body/voice preferences, Kai's requested appearance, 2D office
  portraits/full-body previews and manual local browser voice selection.
- BE-13: departments, floor placement, adult virtual employees, capacity/lifecycle,
  transactional Company-task allocations and a bounded office roster.
- BE-14: disabled-by-default fictional personal lives, chronological relationship
  transitions, marriage/divorce history and isolation from business evidence/authority.

See [CHARACTERS_ORGANIZATION_SIMULATION.md](CHARACTERS_ORGANIZATION_SIMULATION.md),
[LOCAL_COMMANDS.md](LOCAL_COMMANDS.md) and [SPRINT_1_RETROSPECTIVE.md](SPRINT_1_RETROSPECTIVE.md).
A 3D animation engine, imported assets, voice cloning and autonomous employee execution
remain future implementation work. These features are not production deployment clearance.

## Owner acceptance — 9 October 2026

BE-12–14 accepted after owner testing; merge authorized. The owner reported that shared
avatar rendering makes female characters appear male and browser voices have poor
quality. Both are low-priority Sprint 2 improvements, not silently discarded findings.
See [SPRINT_2_PLAN.md](SPRINT_2_PLAN.md) for proposed priorities and acceptance examples.
Earlier Review entries above are historical implementation logs.

## Sprint 2 — BE-15 and BE-16 in Review

Owner selected simpler local startup/testing and shorter evidence-first AI review.
Both are implemented on `codex/sprint-2-local-review`; owner acceptance remains.
BE-17 discovery and BE-18/19 appearance/voice refinements remain Backlog, with the
latter two at Low priority. See SPRINT_2_LOCAL_REVIEW.md for scope and test examples.

## Sprint 2 owner acceptance — 9 October 2026

- [x] BE-15: local startup tested successfully after stopping the old dashboard.
- [x] BE-16: owner reviewed and accepted the new report view.

Owner authorized PR #30 merge. BE-17–19 remain Backlog. Earlier Review entries are historical.

## BE-17 — research and practice in Review

Owner clarified AI-operated work, €0 spending and €0 permitted loss, then approved
implementation. The dashboard now supports dated public-source records, a persisted
research brief, local tool-free comparisons, owner-selected text practice and
observed pass/fail review. Records grant no action or launch authority. See
[BE17_LOCAL_REVIEW.md](BE17_LOCAL_REVIEW.md) for verification and explicit limits.
Owner acceptance is pending; this item is not Done.

## BE-17 acceptance — 10 October 2026

Owner accepted the bounded research/private-practice workflow and authorized PR #31 merge. BE-17 is Done; earlier Backlog/Review entries are historical. BE-18/19 remain Backlog. This is not commercial launch acceptance. See [CONCEPTUAL_SYSTEM_AUDIT.md](CONCEPTUAL_SYSTEM_AUDIT.md) for current boundaries and proposed follow-ups.


## Owner acceptance — 10 October 2026

The owner confirmed the corrected neural auditions play, completed review and authorized merge. BE-18 and BE-19 are Done for the implemented character presentation, local voice comparison and neural audition/preference scope. Earlier pending/rejected review entries remain historical. Sprint 2 review is complete. Generated-conversation neural synthesis, 3D animation and paid/cloud voices remain future work.

## Sprint 3 selected scope — 10 October 2026

Pre-Sprint 3 audit PR #34 is merged. BE-20–22 (useful deliverables, evidence-backed business comparisons and measurable feedback improvement) were accepted and merged on 10 October 2026 via PR #36 (`7d0acdb`). See [SPRINT_3_PLAN.md](SPRINT_3_PLAN.md) and [SPRINT_3_PRACTICE_EVIDENCE.md](SPRINT_3_PRACTICE_EVIDENCE.md).

The owner then selected BE-23 local voiced contributions. Implementation is in Review in draft PR #37; listening acceptance remains pending. Generated audio expires after the owner-confirmed 30 days. Live board cards are not automatically changed.
