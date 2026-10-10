# Sprint 5 — useful AI work and simpler review

Planning date: 11 October 2026. Owner requested the Sprint 5 backlog after accepting and merging Sprint 4. This plan creates work items; it does not start implementation or promise all items fit a fixed timebox.

## Sprint goal

An executive produces one useful private deliverable from supplied facts, the owner understands the next step immediately, and feedback improves a revision under the same rubric. Evidence, model identity and recovery remain inspectable. No spending or launch authority is added.

## Scope and order

Start BE-34, then BE-35. BE-37 can be the next independent foundation task before more UI changes. Deliver BE-36, BE-38 and BE-39 in coherent increments, then BE-40, BE-41 and BE-42. BE-39 is the first candidate to defer if capacity is limited; tag-only limitations must remain visible if deferred. Dependencies below govern readiness; backlog status is not a claim that code is missing or already defective.

| ID | Priority | Item | Initial state | Depends on |
|---|---|---|---|---|
| BE-34 | high | AI quality failure analysis and comparable baseline | ready | None |
| BE-35 | high | Useful evidence-grounded private deliverables | backlog | BE-34 |
| BE-36 | high | Clear next steps and concise owner review | backlog | BE-35 |
| BE-37 | high | Earlier browser and calendar integration checks | ready | None |
| BE-38 | high | Consistent interruption and permission-change guidance | backlog | BE-37 |
| BE-39 | medium | Reproducible model identity for private runs | backlog | BE-34, BE-38 |
| BE-40 | high | End-to-end private work acceptance scenario | backlog | BE-35, BE-36, BE-38, BE-39 |
| BE-41 | high | Sprint 5 integration, security and privacy audit | backlog | Selected implementation cards ready for review |
| BE-42 | medium | Sprint 5 retrospective and closure | backlog | BE-41 and owner review |

## Stories and acceptance

### BE-34 · AI quality failure analysis and comparable baseline

As the owner, I want to see why generated work fails before we change prompts.

Acceptance: Inspect all six failing JSON-mode benchmark attempts and classify exact failures without rewriting raw reports. Preserve the original 30-attempt dataset, rubric, checker, prompt and model digest; rerun a comparable baseline or explicitly report missing local raw evidence. Show counts, denominators, errors and limits. Distinguish contract coverage from semantic usefulness; do not weaken checks to improve scores.

### BE-35 · Useful evidence-grounded private deliverables

As the owner, I want the executives to draft useful work I can assess rather than repeat the assignment.

Acceptance: Deliver one documentation exercise and one unfamiliar transfer example using frozen supplied facts and exact owner rubrics. Include actionable instructions without invented controls, facts or approval. Missing information produces a specific question or clearly bounded draft. Compare prompt changes against the retained BE-34 baseline; preserve raw failures and revisions. Owner separately assesses usefulness; no claim of model training, general competence or revenue.

### BE-36 · Clear next steps and concise owner review

As an owner who scans text, I want to know the current state and the one next step immediately.

Acceptance: Research and practice cards show current state, one eligible next step and a concise explanation when blocked. Separate supplied evidence, unknowns and recommendations; expose full text and provenance on demand. Pending assessments, rejected work and missing evidence have distinct examples. No invented recommendation when information is insufficient; preserve draft inputs and existing approval gates. Owner can explain the next step from the summary alone.

### BE-37 · Earlier browser and calendar integration checks

As the implementer, I want navigation and date regressions caught before the full audit.

Acceptance: Centralize shared production-browser navigation helpers and run affected feature smokes after UI changes. Cover desktop/mobile destinations, hidden-tab polling and draft retention. Add deterministic UTC/local calendar and canonical fractional datetime cases without weakening execution-order validation. Verify selected checks fail on a representative regression and pass after correction. Keep the full audit as the final gate; use disposable data and synthetic public reads.

### BE-38 · Consistent interruption and permission-change guidance

As the owner, I want a stopped or invalidated run to tell me what can safely happen next.

Acceptance: Cover interrupted local work, revoked skills, withdrawn templates and corrected source assessments together. UI eligibility matches authoritative transactional checks; stale concurrent requests cannot publish or duplicate results. Show sanitized reasons and explicit recovery actions while preserving earlier samples/artifacts. Test private headers on success/error responses. Uncertain external outcomes require reconciliation; no automatic replay or renewed authority.

### BE-39 · Reproducible model identity for private runs

As the owner, I want to know whether a resumed run uses the same local model.

Acceptance: Capture the resolved local Ollama model digest and relevant configuration for new supported private runs without exposing prompts or secrets. Verify identity again before continuation; changed or unresolved identity blocks automatic reuse with a clear explanation. Legacy tag-only records remain explicitly unknown and are not backfilled with invented digests. Test changed-tag and unavailable-model cases; no automatic model downloads or cloud fallback.

### BE-40 · End-to-end private work acceptance scenario

As the owner, I want one understandable test of the complete private-work flow.

Acceptance: Document a fictional brief through draft, exact-rubric assessment, failed-check feedback, revision, private file comparison and reviewed procedure reuse. Preserve every record and show what each transition proves. Automated tests use disposable data; any real local generation is separately labelled and owner assessed. Supply a short ./company review guide with the existing key, no database reset and no spending/publishing/customer contact.

### BE-41 · Sprint 5 integration, security and privacy audit

As the owner, I want fixable project defects resolved before acceptance.

Acceptance: Audit the final selected changes across domain relationships, authorization, privacy, recovery, retention, dependency findings and browser behavior. Fix actionable project findings; preserve failed evidence and rerun appropriate checks. Report exact implementation commit, actual test counts, model-quality limits and upstream findings separately. Keep generated artifacts at 30-day retention and budget/loss at €0. No claim of a clean release gate if advisories remain.

### BE-42 · Sprint 5 retrospective and closure

As the owner learning agile, I want evidence of what we delivered and how to improve.

Acceptance: Compare intended and delivered scope with actual tests, quality measurements and owner feedback. Record confusing review steps, defects and proposed improvements without invented velocity or earnings. Mark Done only after documented owner acceptance and actual merge evidence. Keep deferred cards visible; propose next-sprint priorities separately from completed work.

## Concrete first example

Use a fictional task app that supports creating, editing and completing a task. Interface controls and reminders are unspecified. The sample must use one concrete task through all three steps, include three FAQ answers and state the unknowns without inventing buttons. Review useful instructions, factual grounding and the exact rubric separately. Passing this example does not establish customer demand or competence on other work.

## Working agreements

- Each story starts with a supplied-facts example and a failure example; show a representative result early.
- Run targeted checks after each change, then the complete final audit. Preserve credentials and the existing company database.
- Prefer one coherent PR at a time. Record owner acceptance and authorized merge before Done; do not accumulate another long dependent stack unnecessarily.
- Keep owner instructions short: ./company start for viewing, ./company audit for disposable checks. Feature-specific commands must explain what they do.
- The implementer builds and verifies; the owner selects priorities and reviews usefulness. The board’s owner assignment identifies accountability, not a requirement for the owner to write code.
- Budget and permitted loss remain €0. No paid service, cloud fallback, customer contact, publishing or executing generated code.
- Generated artifacts retain the existing 30-day policy; durable approval, sample and review provenance remains intact.

## Boundaries and planning evidence

The inputs are the [Sprint 4 retrospective](SPRINT_4_RETROSPECTIVE.md) and [recorded 24/30 narrow-check baseline](docs/planning/be24-baseline-summary.json). No new research or revenue evidence is claimed. Known unpatched Chroma advisories remain in the existing security release gate; they are not invented fixable sprint tickets.

Full 3D bodies, additional floors/employees, personal-life simulation expansion and real-money operation remain later increments. This sprint prioritizes useful, trustworthy work over expansion of the office prototype.

Matching cards: [sprint-5-cards.json](docs/planning/sprint-5-cards.json), on the separate **Sprint 5 development plan** board. Existing Development and Company records are preserved. There is no fixed velocity or delivery date because neither capacity nor estimates have been established. The owner can change the proposed order or defer scope before implementation.
