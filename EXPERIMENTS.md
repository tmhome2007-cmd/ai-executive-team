# Experiments and observations (BE-03)

An owner-defined experiment links one pending proposed action to a hypothesis,
baseline source/note and optional value, metric/unit, optional target, comparison
direction, expected result, budget, maximum cash risk and observation due time.
Missing baseline/target/measurement values remain unknown. Expected figures do not
become company earnings. One action per experiment is supported in this version.

Plans are created before action approval. Their monetary risk limit must be at most
their budget. Treasury-aware and internal approvals require a known action cost,
matching currency, and expected cost within both experiment limits. Execution checks
again, in the same transaction as its claim. The experiment policy/version is included
in the action's approval seal; tampering invalidates approval and releases reservations.
Unlinked action approval seals remain compatible. Plans freeze after approval or any
measurement. Editing a pending plan requires its current version; stale writes conflict.

These are planned cash-exposure limits, not a guarantee about provider billing or all
business risks. Actual cost is read from the existing approved execution/outcome and
treasury flow. Recording a real cost above the plan remains possible and produces an
over-limit assessment: history must not hide an overspend. Recording measurements
does not reserve/spend money, approve work, grant capabilities or credit revenue.

Observations record a timezone-aware measurement time, optional numeric value,
required source evidence, notes and an idempotency key. Matching retries reuse their
original record; changed retry payloads conflict. They can be recorded after terminal
action execution, and must not predate that execution or claim future measurement
(a 60-second clock-skew allowance is applied). They are immutable; corrections append
a new observation. Simulated observations remain labelled even if action state later
changes. Owner-supplied evidence is not independently verified.

The latest measurement is selected by observed time, then record ID; arrival order
does not turn an older measurement into the latest result. Comparison reports unknown
measurements/targets explicitly, target met/missed, change from a known baseline,
simulation/not-live/blocked state and recorded cost against the limit. It does not
automatically rewrite the action outcome, decide the next business action or infer
profit from capital funding. Values must be finite and bounded; credential-shaped text
is rejected. Large bodies, IDs, dates and pagination are validated.

Experiments in the dashboard supports plan creation/editing, result/cost comparison,
source-backed observations, older-record pages and navigation to the linked action.
The observation date is persisted planning data. Automatic observation job execution
belongs to BE-10 and is not claimed implemented here. Evidence freshness/conflict and
source verification belong to BE-04. All endpoints require the existing owner key:

- GET/POST `/experiments`
- GET/PATCH `/experiments/{id}`
- GET/POST `/experiments/{id}/observations`

No deletion, approval, execution or treasury-mutation endpoint is added. Plans and
observations are local SQLite history covered by whole-database backups and optional
encryption. The existing JSONL sync does not export them; 30-day generated-artifact
retention does not remove these business records. Activity events capture their changes.

Verification: six new real-SQLite/API tests cover monetary gates/rollback, approval seal
tampering, stale/frozen plans, immutable observation replay, actual overspend reporting,
unknowns, simulations, invalid/future/past measurements, secret rejection, authenticated
bounded APIs and unchanged financial authority. The combined suite passed 49 tests,
with one unchanged opt-in Docker test skipped. Foundation checks passed 150/150;
Bandit medium/high and frontend lint/build passed (one existing image warning).
The Chromium smoke verifies real forms against a disposable in-process FastAPI/SQLite
backend, stale edits, escaped source text, simulated results, mobile width and key privacy.
No real business action, model call, purchase or notification occurs.

To review locally, restart the isolated backend with its existing test environment and
database, refresh the dashboard, and choose Experiments. For disposable browser tests
with the built frontend on localhost:3000 and API base port 8001:

```bash
.venv/bin/python scripts/experiments_smoke.py
.venv/bin/python scripts/agile_smoke.py
```
