# Agile boards

Two board purposes are supported:

- **Development** plans this product's backend work, independent of business decisions.
- **Company** assigns executive business tasks with optional validated goal, decision and
  action links. Inconsistent or missing links are rejected. Moving a card never approves
  or executes its linked action, reserves money or grants a capability.

The Agile boards view creates boards and tasks, assigns owner/executive, sets priority,
records acceptance criteria, and edits task state. Six columns are available: Backlog,
Ready, In progress, Review, Done and Blocked. Criteria are required before starting work,
blockers require reasons, and Done requires a completion note. Existing execution and
approval controls remain authoritative. This first version supports manual planning;
executives do not automatically pick up cards or execute tasks yet.

## Development roadmap

Create development roadmap imports fourteen proposed features from the planning template
represented in BACKEND_AGILE_ROADMAP.md. Creation is atomic and repeat requests reuse the
existing named roadmap without overwriting owner edits. BE-01 is in Review, BE-02/BE-03
are Ready, and later features start in Backlog. The first sprint is a proposal; priorities
and ordering can be changed by the owner. No dates, story-point estimates or automatic
implementation are promised.

Task cards sort by priority and then ID. Each board loads 100 tasks at a time, with older
pages available. Up to 100 boards are listed in the initial selector. Columns scroll
independently on desktop and stack on mobile. SQLite history persists through restart and
is covered by whole-database backups. The existing JSONL sync format does not export these
new planning tables in this version.

Updates require the loaded task version. Concurrent changes return 409; refresh and reopen
the current card before saving. Credential-shaped text is rejected, input sizes and roles
are validated, SQL values are parameterized, and every API requires the existing owner
key. No new runtime dependencies or external services are introduced.

Latest company task states appear in the company activity timeline. Development tasks are
excluded from business activity. This remains a latest-state view; BE-02 proposes an
append-only event ledger to retain every future transition.

## API

- GET/POST `/boards`
- POST `/boards/roadmap` — create or reuse the development template
- GET/POST `/boards/{board_id}/tasks`
- PATCH `/tasks/{task_id}` — version-checked update

No task deletion or autonomous execution endpoints are included in this version.

## Use locally

Restart the existing isolated backend terminal with its previous environment variables:

```bash
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

Refresh the dashboard and open Agile boards. Choose Create development roadmap for our
backlog, then use Create board with purpose Company work for executive tasks.

## Verification

- 39 security/recovery/database/API tests passed; one unchanged real-Docker test skipped.
- 150/150 disposable foundation regressions passed.
- Bandit reports zero medium/high severity findings; existing low severity findings remain.
- Production build and TypeScript passed. ESLint has no errors; the existing screenshot
  optimization warning remains. Native glob/Next contract passed; npm audit has zero findings.
- Real SQLite/FastAPI Chromium smoke verified both boards, task creation/editing, lineage,
  acceptance/blocker/completion rules, concurrent edit rejection, mobile width and
  authentication privacy. Marking a task done left the linked action pending.
- Existing dashboard browser regressions passed with synthetic data.

Run `.venv/bin/python scripts/agile_smoke.py` while the dashboard built for port 8001 is
running on localhost:3000. API requests go to a disposable in-process test backend, never
the user's running company backend. Scheduler lifespan is not started; no business
execution, funding, resource fulfillment or notification is performed.
