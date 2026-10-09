# Backend agile roadmap

Planning baseline: 8 October 2026. Proposed priorities; owner can change ordering.
Two boards serve different purposes: Development tracks building this product; Company
tracks the executives' business work. Neither task status nor assignment grants execution
or spending authority. Existing approvals, capabilities and treasury gates remain in force.

## Sprint 1 — make company work visible

| Ready | In progress | Review | Done |
|---|---|---|---|
| — | — | BE-01 Development and company task boards | Existing foundation audit and local checks |
| — | — | BE-02 Append-only activity events | Goals, treasury, resources and outcome tracking |
| — | — | BE-03 Experiment records and observations | Decision/action lineage, follow-ups and executive memory |
| — | — | — | Meeting types, dashboard v2, virtual office v1 |
| — | — | — | Published executive contributions and activity timeline v1 |

Scope of done items is their verified current implementation, not every future extension.
One implementation item at a time. Move to Review only after code and appropriate checks
pass; Done requires owner review. Dates for future sprints are not committed.

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
