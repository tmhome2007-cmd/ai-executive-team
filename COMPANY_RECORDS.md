# Recorded executive contributions and company activity

## Existing identities and personalities

`GET /executives/profiles` exposes the existing agent role, goal and backstory with its
existing name: Kai Akira, Maya Chen, Alex Sterling, Jordan Blake, Sarah Okonkwo, Marcus
Rivera, Zoe Nakamura, Dev Patel, Elena Volkov, Brandon Fire and Priya Raman. The office
uses these profiles and offers a Background & role personality panel. Agent reasoning
continues using the original goal and backstory. Brandon's CCO office grouping and fallback
label now correctly reflect Compliance & Operations rather than Commercial.

The longer-term frontend vision remains individual faces, voices and bodies, a 3D office
with moving agents and employees, and a separate simulation of virtual personal lives.
This change does not invent biographies, conversations, employees or business evidence.

## Durable published contributions

Successful ad-hoc, daily research and autonomous follow-up meetings store published,
evidence-guarded individual task outputs atomically with their decision. Successful
preparation stores its published outputs atomically with preparation completion. Records
capture phase, task sequence, executive key, profile snapshot and capture time. Capture
time identifies persistence, not the exact time an executive spoke.

`GET /decisions/{id}/conversations` returns those records. The frontend lets the owner
choose a recent meeting or a decision linked from the timeline and filter by phase.
These are written task contributions, not a verbatim multi-turn chat or hidden reasoning.
Old meetings without recorded contributions show an explicit empty state; no dialogue is
fabricated or reconstructed from raw checkpoint traces.

Writes validate roles, text size and profile shape, reject common credential patterns,
and bind retries to immutable stored content. Invalid contributions roll back the parent
write. At most eleven 100,000-character contributions can be saved per phase. No raw tool
traces or hidden model reasoning are captured here. Text renders through React escaping.

Records are local SQLite history included in existing whole-database backups, including
optional encrypted backups. The existing JSONL sync format does not transfer these new
contributions; they are intentionally local in this version. Generated-artifact retention
does not remove durable company history.

## Activity timeline

`GET /company/activity?limit=50` now reads the append-only activity ledger. New state
changes persist alongside their business transaction, with initiating actor/source and
previous/new states. Legacy snapshots identify unknown earlier history. Cursor pagination
using `before_id` avoids skips when newer events arrive. See ACTIVITY_LEDGER.md.
The existing owner API key is required; no execution authority is added.

## Local use

The running backend must be restarted to load the new endpoints and initialize the new
table. In the existing isolated backend terminal, press Ctrl+C and rerun its previous
start command, preserving the test environment variables and database. If its current
working directory is the hardening repository, the Python launch command is:

```bash
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

Then refresh the dashboard and choose Conversations & activity. Create a synthetic meeting
through Decisions to populate future contributions; legacy meeting reports remain intact.

## Verification

- 35 security/recovery/database/API tests passed, one unchanged real-Docker test skipped.
- 150/150 disposable foundation regression checks passed.
- Bandit: zero medium/high severity findings; existing low severity findings remain.
- Production frontend build/TypeScript passed; lint has no errors and its pre-existing
  screenshot image optimization warning remains.
- Full npm audit: zero vulnerabilities; pinned glob/Next contract passed.
- Extended synthetic Chromium checks passed all ten views, executive names, decision and
  preparation contributions, phase filtering, harmless HTML-shaped text, provenance,
  mobile layout, API recovery, memory-only authentication and no mutation requests.
- Six new SQLite/API tests cover idempotent immutable snapshots, secret/invalid-input
  rollback, atomic preparation, legacy records, pagination, API authentication/bounds and
  actual decision endpoint persistence with a synthetic meeting.
