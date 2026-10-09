# Characters, workforce and fictional personal lives

BE-12–14 were tested and accepted by the owner on 9 October 2026. Open **Organizational work → People & simulation** after restarting both applications from `codex/identity-organization-simulation`.

## What is implemented

| Item | Current behavior | Boundary |
|---|---|---|
| BE-12 | Eleven executive face/body/voice profiles, editable 2D SVG previews, append-only version history and manual local voice preview | Existing names, roles, reasoning personalities and historic speeches are preserved. This is the data/preview foundation for a future 3D office. |
| BE-13 | Departments, responsible executives, office floors, employee onboarding/active/suspended/retired states, capacity and company-task allocations | Virtual employees do not receive executive tools, spending authority or autonomous execution. Recording an assignment as completed does not complete the linked company task. |
| BE-14 | Owner-enabled fictional friendship, dating, marriage, separation, divorce, hobbies and milestones with retained event history | Disabled by default. These records never become business evidence, executive memory, owner consent or budget authority. |

Kai Akira's initial profile follows the owner's specification: a tall, well-built Black man, no beard, black dreadlocks, black eyes with a subtle red tint. Height is initially 190 cm and remains editable. Other profiles have varied appearances and voice preferences. All characters are fictional adults.

The office shows each registered employee on their department's floor with actual recorded status and allocated hours. It does not invent movement or claim an employee is executing tools.

## Voice and asset limits

Only the built-in SVG asset and `browser_local` voice provider are currently supported. SVG colors, shapes and body parameters are validated; remote assets, custom markup and voice-provider credentials are rejected. This implementation does not include imported 3D models, voice cloning, continuous spoken conversations or a 3D animation engine.

Voice preview requires an installed browser voice marked `localService=true`; unavailable requested voices produce a visible message rather than a remote fallback. Some browsers expose no local voices. A style description records the intended character direction; actual browser controls currently apply the selected installed voice, pitch and pace. It cannot guarantee a unique studio-quality voice for every executive. [Web Speech specification](https://webaudio.github.io/web-speech-api/#dom-speechsynthesisvoice-localservice).

Voice preview is manual and speaks a fixed introduction, never a business conversation. It is cancelled when the character view is closed. Character preferences are stored separately from immutable reasoning/personality snapshots.

## Consistency and privacy

- Every API requires the owner's existing API key. Lists are paginated and capped at 100 records; the dashboard requests 50 per page.
- Character changes require the current version and preserve prior versions. Stale updates are rejected.
- Employee creation uses an idempotency key; conflicting retries are rejected. Capacity reservations are transactional, so concurrent assignments cannot overbook.
- Allocated hours remain committed until completed/cancelled; they do not automatically reset each week. Suspension, retirement and department moves require releasing unfinished assignments first.
- Only ready/in-progress tasks on a Company board can be allocated. Linked goals must be active. Development tasks cannot be assigned to virtual employees.
- Personal events have their own idempotency keys, chronological relationship transitions and stale-version checks. A character cannot enter another marriage while an existing marriage/separation remains unresolved.
- Retired employees retain history and presentation but cannot receive new work or personal events. No real users, hiring, wages or external services are involved.
- Fictional events are excluded from the company activity/evidence feed. They are durable company-local simulation records, backed up with the database; the 30-day generated-artifact cleanup does not delete this retained history.
- Cross-machine sync does not yet include these new tables. Use the existing database backup/restore workflow for full local state.

## API map

| Area | Owner endpoints |
|---|---|
| Character | `GET/PUT /characters/{character_key}`, `GET /characters/{character_key}/history` |
| Department | `GET/POST /organization/departments`, `PUT /organization/departments/{id}` |
| Employee | `GET/POST /organization/employees`, `PUT /organization/employees/{id}` |
| Work | `GET/POST /organization/assignments`, `POST /organization/assignments/{id}/review` |
| Office | `GET /organization/office-roster` with optional floor and pagination |
| Personal simulation | `GET/PUT /simulation/settings`, `GET /simulation/relationship`, `GET/POST /simulation/events` |

Keys use `executive:ceo`, other canonical executive keys, or `employee:1`. Relationship version is 0 for a new pair; inspect the current relationship before later transitions.

## Verification

The security/regression suite covers profiles, original persona preservation, authentication, strict schemas, concurrency, lifecycle gates, social transitions, immutable history and isolation from evidence/approvals/treasury. `scripts/people_smoke.py` exercises the actual dashboard against disposable SQLite through the owner API, with speech stubbed to verify local selection and remote refusal without audio transmission.

The comprehensive disposable audit is `.venv/bin/python scripts/local_audit.py`. Browser workflow verification uses a separately built dashboard pointed at `http://127.0.0.1:8001`; the smoke intercepts that API and never writes to a running company database. The generic audit's Chromium check verifies browser availability; it is not a substitute for the feature smoke.

Local startup and command meanings are in [LOCAL_COMMANDS.md](LOCAL_COMMANDS.md). Owner acceptance and merge authorization were recorded on 9 October 2026. Female character presentation and higher-quality voices remain low-priority Sprint 2 improvements.
