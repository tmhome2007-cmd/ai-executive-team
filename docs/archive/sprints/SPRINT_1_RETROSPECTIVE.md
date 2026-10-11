# Sprint 1 retrospective — 9 October 2026

Sprint 1 grew from its original board/activity/experiment scope to BE-01–14 through explicit owner requests. BE-01–11 were accepted and merged before this final increment. BE-12–14 were tested locally and accepted by the owner on 9 October 2026; merge was authorized.

A **sprint review** checks the delivered product against its acceptance criteria. A **retrospective** examines how we worked and chooses improvements for the next sprint. This document covers the latter, with delivery/test evidence as context. It is a development retrospective, not an AI-generated company meeting or an assertion of owner approval.

## What we delivered

| Work | Result |
|---|---|
| BE-01–03 | Separate development/company boards, retained activity and experiments with observations |
| BE-04–07 | Evidence registry, owner-reviewed executive plans, recorded discussion rounds and scoped access inventory |
| BE-08–11 | Operating policies, source-backed memory reconciliation, restart-safe observations and actual agent activity stream |
| BE-12 | Versioned appearances/body/voice preferences and usable 2D character previews; Kai follows the requested appearance |
| BE-13 | Departments, employee lifecycle/capacity, company-task allocations and office roster |
| BE-14 | Explicitly fictional personal lives, relationships and marriage/divorce history, separated from business evidence and authority |

The final increment passed 123 regression/security tests with Docker enabled, 150/150 foundation checks, Bandit medium/high, dependency compatibility, frontend lint/build, npm audit, browser availability and local Ollama inference. The separate Chromium workflow smoke passed character editing/history, local-only voice selection, workforce allocation/progress, social transitions, business-evidence isolation, mobile layout and in-memory key privacy. Tests used disposable data; speech was stubbed for the workflow test.

Evidence: `audit-results/20261009-200756/summary.json` and its individual logs, `tests/test_people_simulation.py`, and `scripts/people_smoke.py`. The audit ran against the implementation before its commit. Four known unpatched upstream Chroma advisories remain visible separately. Lint retains the existing authenticated screenshot image warning. Automated checks do not certify every future AI answer or clear production deployment.

## What worked

- Owner testing found real usability and AI-quality issues that automated tests alone would not reveal: invented acknowledgement, unclear recommendations, missing/unknown evidence and confusing setup.
- We converted failures into regression cases and kept approval, spending and evidence boundaries explicit. This final increment also tests concurrent capacity reservations and marriages with real SQLite transactions.
- Disposable databases and separate frontend builds allowed testing without replacing the owner's company data or interrupting the running app.
- Later work used a separate feature branch and review PR after earlier changes were merged. Existing agent identities/personality snapshots were preserved when adding presentation metadata.

## What was difficult

**Owner feedback:** local testing was hardest. The owner did not initially know what each command did, how to switch branches or why different terminals were needed. Earlier testing felt like selecting a branch, starting the app and calling one endpoint; later instructions became a large block with key-copying steps. The owner now understands more, but the initial workflow was confusing.

**Owner feedback:** long AI answers are difficult to inspect while reading diagonally. Errors can be missed, and the owner finds it helpful when the coding assistant identifies them. That is useful support, but approval screens should make the relevant evidence, uncertainty and requested decision easier to review directly.

**Observed process issues:** multiple checkouts and terminal environments caused missing `.venv` paths, key mismatches and authentication failures. Changing a Git branch did not change `.env` or the database, while a dashboard could still serve a build from an earlier branch. We explained these distinctions too late.

**Observed scope issue:** the sprint grew substantially. Large batches made review and troubleshooting harder. Delivering many features is not, by itself, evidence that the sprint estimate or workflow was good. We did not record planned capacity, effort or cycle times consistently, so we cannot honestly calculate velocity or claim an improvement percentage.

## Improvements already made

[LOCAL_COMMANDS.md](../../../LOCAL_COMMANDS.md) now separates backend, dashboard and audit, explains every command's purpose, and distinguishes the configured dashboard key from disposable internal audit keys. It uses this checkout's Python directly and avoids unnecessary activation steps.

The new features expose their actual limits: 2D previews, device-dependent local voices, recorded employee allocations and fictional personal events. They do not claim a completed 3D office, autonomous staff execution or unique cloned voices.

## Three experiments for next sprint

| Improvement | Owner | Measure at next retrospective |
|---|---|---|
| A simpler local start/check workflow: one documented entry point checks checkout, branch, environment, ports and services, then gives the exact next command without exposing or replacing secrets | Coding assistant builds it; project owner tests it | The owner can restart both apps and run the audit using the guide, explain what each step does, and report any remaining confusing step. Record actual elapsed time and assistance needed rather than inventing a target result. |
| Short, reviewable AI results: show supported findings, unknowns and the requested next action first; expand evidence/details on demand | Coding assistant implements; owner reviews examples | Test a fixed set of empty-evidence, complete-evidence, conflicting-evidence and missing-prerequisite cases. No invented owner approval; every claimed fact has supplied support or an explicit uncertainty label. Owner confirms the short view is understandable. |
| Smaller stories and earlier review: define acceptance examples and limits before coding; prefer one coherent feature per PR and one active implementation item | Owner chooses priorities; coding assistant scopes/builds/verifies | Each completed story has acceptance evidence, known limits and an owner review before merge. Record scope changes and whether troubleshooting stayed within one feature. |

These are proposed next-sprint improvements, not silently scheduled work. The owner chooses the next sprint's goal and priorities. We should select a bounded outcome rather than committing the entire remaining 3D/voice/business vision at once.

## How to use this at school or work

At a retrospective, everyone contributes observations, the team chooses a small number of improvements, assigns responsibility, and checks them next sprint. Keep it blameless and concrete: “the setup instructions mixed three purposes” is more useful than “the tester did it wrong.”

When reviewing BE-12–14, first check the acceptance examples in the feature guide. Once accepted, mark those items Done and merge the review PR. Then choose the next sprint goal and bring the three improvement experiments into planning. The owner has supplied retrospective feedback; acceptance of these final features remains a separate decision.

## Final owner review

The owner accepted BE-12–14 after local testing and requested merge. They reported that
female executives appear male in the shared avatar design and that browser voices sound
low quality. Both are carried into Sprint 2 at low priority. This feedback confirms why
visual and audible owner review must supplement automated checks: schema/behavior tests
do not establish that a character looks or sounds right.
