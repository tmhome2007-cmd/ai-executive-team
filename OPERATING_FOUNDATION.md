# Operating foundation: BE-08–BE-11

Implemented on `codex/operating-foundation-sprint`, based on merged foundation
PR #14. The owner dashboard exposes controls under **Organizational work →
Operations**. New records are stored in the company SQLite database and included
in existing whole-database backups. Existing company records and credentials
are retained. New tables are initialized during normal backend startup.

## Operating policies

The owner publishes immutable, versioned limits: currency, maximum action cost,
rolling 24-hour spend plus all active commitments, maximum experiment risk,
required known estimated cost and prohibited action types. Blank caps are
unrestricted additional limits; zero is a real zero limit. Existing treasury,
goal, capability, sandbox and owner approval controls always apply.

Approval and execution validate inside SQLite write transactions. A policy update
invalidates approval seals from an earlier policy; the action returns to pending
and its reservation is released when execution detects the changed seal.
Concurrent approvals cannot both pass a shared spending limit. No currency
conversion is assumed. Legacy timestamps are interpreted in the local timezone;
explicit timezone timestamps retain their own offset. Daily limits count gross
spending; refunds do not silently restore risk allowance. Agents receive policy
limits as planning context, without treating them as approval.

## Memory reconciliation

Owner reviews require current, undisputed registered source IDs and the memory's
current version. Corrections create a replacement and retain the original lesson,
source IDs, review note and revision history. Automatic repeated writes cannot
overwrite curated lessons. Superseded and expired lessons cannot be reactivated
through reconciliation. Conflicted lessons require a source-backed correction.

Shared claim keys identify differing lessons for review. This is explicit
contradiction grouping, not automatic semantic truth detection. Conflicting,
disputed, expired or superseded curated memories are withheld from active agent
context. Legacy memories without lifecycle metadata retain their prior behavior.
Memory is advisory; source registration or owner confirmation does not certify
independent verification. Confidence is not increased by correction. Expiry is
checked during retrieval and processed at startup/every 15 minutes.

## Observation scheduling

Jobs have immutable inputs, stable idempotency keys, due times, atomic claims,
bounded attempts and versioned review. The scheduler claims at most five due
jobs per minute. Supported collectors are:

1. An owner-confirmed, unexpired source whose summary is a JSON measurement.
2. A structured `file_operation` read action, independently approved through the
   existing owner controls. Scheduling binds to the exact action type/details.
   It cannot invoke a shell, browser or write operation. Existing executor
   workspace confinement, capability, policy and checkpoint controls apply.

A measurement contains exactly:

```json
{"experiment_id": 1, "metric_name": "requests", "observed_at": "2026-10-09T17:00:00Z", "value": 25}
```

The experiment/metric must match, and the timestamp must follow the observation
job due time and experiment execution. Future measurements are rejected.
`value: null` means unknown; it is never converted to zero or a success. Results
retain source links and the existing simulation/live classification. File-read
sources remain unverified until owner review; an approved read is not independent
measurement verification. An already completed read uses its stored result,
which is truncated by the existing executor; incomplete JSON requires review.

Transient SQLite collection failures retry only source collectors, with bounded
backoff and at most three claims. Restart recovery retries interrupted source
collectors; interrupted file collectors require owner review and a newly reviewed
read/job. An unknown tool result is never automatically replayed. Observation
idempotency prevents duplicate measurements after a persistence interruption.
Missing/invalid data stays `needs_review`, without publishing raw provider errors.

## Activity stream

Actual CrewAI task callbacks record executive start and completion. Cached tasks
are not reported as newly running. Exceptions/interruption produce `unknown`;
a running record older than 15 minutes is also unknown. Unknown roles do not get
an invented idle state. Role names and personalities remain unchanged.

Owner-authenticated `/activity-stream/page` and `/activity-stream` expose activity
metadata, without prompts, tool output, run keys or credentials. Consumers resume
with `after_id`; invalid/expired cursors request a reset. SSE sessions last at
most five minutes, return at most 100 events per batch, and permit 16 concurrent
streams per server. Connections release their slot on cancellation. The dashboard
uses the same cursor feed with five-second polling while visible, keeps at most
200 displayed events and aborts requests when unmounted.

Replay covers 30 days. Durable company approval/execution/memory provenance is
retained in the existing append-only ledger; the stream window does not delete
that history. These are observed task states, not a worker heartbeat guarantee.

## Verification and audit scope

The tests use disposable SQLite databases, synthetic credentials and local files.
Coverage includes concurrent approval limits, stale policy seals, immutable memory
history, contradictions/expiry, exactly one observation claim, unknown values,
real approved reads, changed collector bindings, bounded retry/crash recovery,
owner API validation and SSE connection cleanup. Chromium exercises policy,
memory correction, observation results, actual activity, mobile layout and key
privacy against a disposable API database.

```sh
.venv/bin/python scripts/local_audit.py
```

The comprehensive audit includes Docker isolation, backend regressions, the
150-check foundation suite, Bandit, Python/npm dependency scans, frontend install,
lint/build, Chromium runtime and local Ollama inference. Upstream Chroma advisories
remain visible separately. This does not certify production deployment or every
AI answer. External service collectors, semantic contradiction adjudication,
heartbeat supervision and new multi-device sync for these tables are future work;
existing whole-database backup covers the new records. Legacy JSONL exports carry
curated memories as inactive historical records, so missing lifecycle metadata on
another device cannot silently activate them. Their local eligibility is unchanged.
