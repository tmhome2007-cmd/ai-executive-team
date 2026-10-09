# Retained activity ledger (BE-02)

SQLite triggers append events in the same transaction as changes to decisions,
contributions, direction/preparation approvals, action execution/results, outcomes,
resources, treasury entries/reservations, goals, follow-ups, memories, board tasks,
experiment plans and observations.
An event stores UTC capture time, initiating actor/source, source entity/links, selected
previous/new state values and changed field names. It does not copy prompts, evidence
bodies, credentials, contribution text or tool output. Those remain in their original
records. This is state-transition history, not a versioned archive of free-text edits.

No-op writes, rejected transitions, stale task updates and rolled-back transactions
produce no extra events. Existing workflow-key replay remains idempotent. This does not
make arbitrary create requests idempotent or guarantee exactly-once external effects.

Authenticated HTTP changes identify the initiating owner and route. Internal/background
work identifies system/internal; signed sync imports identify import/signed-sync-import.
Attribution is the initiating context, not proof of a particular person or model speaker.
The API key, request body, headers and query parameters are never recorded as source.

On first installation, existing rows receive explicitly labelled legacy snapshots,
captured at installation time. Earlier transitions and actors are unknown. Installation
is atomic, serialized and repeatable; it does not reconstruct or approve old work.

`GET /company/activity?limit=50&before_id=<last event id>` requires owner authentication,
returns at most 100 events, and supplies `next_before_id` for stable pagination during
concurrent inserts. The older offset parameter remains supported. Company events are
shown in Conversations & activity; development task events are excluded there.

Update/delete triggers protect the ledger through normal SQL access. A database admin
who can remove triggers or replace the database can bypass this; it is not a cryptographic
tamper-evident journal. Application connections register required attribution functions.
Independent SQLite writes to tracked tables must use the application's connection helper;
unconfigured connections fail rather than silently omit events.

Whole-database backups include the ledger, with the existing optional encryption and
restore process. The JSONL sync format does not transfer it. Durable business history
is excluded from the 30-day generated-artifact retention policy. No automatic archival
or pruning policy is introduced; long-running deployments must monitor database growth.

Verification: five new real-SQLite/API tests cover migration replay/gaps, state history,
concurrent claims, workflow retry, atomic rollback, no-op writes, append-only protection,
bounded/authenticated API access, owner attribution and stable cursors. The complete
suite passed 43 tests with one unchanged opt-in Docker test skipped; foundation checks
passed 150/150. Bandit medium/high, lint and production build passed. The Chromium board
smoke verified retained blocked/completed states, actor/source, development isolation,
mobile width, credential privacy and unchanged pending action authority.
