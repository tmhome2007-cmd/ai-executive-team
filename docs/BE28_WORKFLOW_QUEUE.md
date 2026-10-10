# BE-28: reviewed workflow patterns and research queue

## Owner review

Stop the previous `./company start` with Ctrl+C, then run `./company start` in this checkout. Keep your existing dashboard key.

Open **Business research → Workflow templates & research queue**:

1. Expand the five-step pattern to inspect its inputs, outputs, dependencies and owner gates. Enter a review note and choose **Review template for reuse**.
2. Queue a real public HTTP(S) URL and a research purpose. Its category is only a hypothesis. Queuing does not visit the website or create evidence.
3. Choose **Read queued public page**. Only a successful read creates an unverified evidence record. Owner classification in the existing evidence controls remains separate; platform documentation does not become buyer evidence because of its queued category.
4. Select at least three dated evidence records, optionally select the reviewed workflow template, then save a new brief. Comparison, practice-plan approval, generation and sample assessment still use their existing buttons and authority records.
5. A withdrawn template blocks future bound generation and publication. Earlier briefs, samples and assessments remain readable. Create and review a new proposed version and bind it to a new brief to proceed.

Model-suggested URLs now offer **Queue proposed source** rather than automatically reading and selecting them. Explicit public reads remain available. No paid search, publication, customer contact or spending is authorized.

## Design and recovery

This increment provides one fixed evidence-to-private-practice pattern, not a general workflow editor or arbitrary graph executor. Five supported nodes describe evidence selection, local comparison, owner practice approval, private generation and owner assessment. Validation rejects cycles, missing typed producers, unknown dependencies, arbitrary fields and unsupported capabilities/gates. Node IDs and dependencies may vary; the supported capability contracts cannot.

Template definitions, review events and brief bindings are immutable SQLite records. Reviews have optimistic versions; withdrawn versions cannot be reactivated. An optional binding preserves compatibility with existing briefs and never substitutes for the existing practice approval ledger. Withdrawal checks fence claims, local reasoning, bounded repairs, continuation and transactional publication.

Source proposals have immutable URL/purpose/category/origin identity. Reads require an explicit owner request and version claim. Static URL validation does no DNS or network activity; the existing public page reader rechecks public addresses and redirects at read time. Credentials, queries, fragments, private hosts and placeholder URLs are rejected. Actual fetched content remains unverified and may be stale or misleading.

Checkpoint payloads make successful public GETs recoverable across a publication gap. Evidence registration and queue linking commit together. Failed reads create no evidence. Startup moves abandoned fetching claims to `needs_review` without fetching. An explicit retry can reuse a completed payload; an inconclusive read gets a new attempt. Fetched URLs are idempotent unless the owner explicitly queues a new snapshot. Old evidence and approvals remain unchanged.

Queue reads use the existing durable checkpoint ledger. Source text, URLs and review provenance are durable evidence records under the existing privacy/backup policy; generated-file retention does not erase this history. No credentials are stored in queued URLs. Authenticated endpoints use `Cache-Control: no-store`.

## Verification

- Eleven disposable SQLite/API tests: graph validation, review/binding immutability, withdrawal, frozen approvals across guarded continuation, concurrency, unverified classification, failed reads, recovery, cached payload retry, atomic evidence linking and URL/auth boundaries.
- Full regression suite and the 150 foundation checks; changed-code Bandit scan.
- Frontend lint, TypeScript/production build and real Chromium workflow/mobile checks with synthetic data. Public reads are mocked in the browser test; unexpected external traffic is blocked.

No new dependencies or copied third-party code. Existing upstream Chroma advisories remain tracked separately. This increment does not establish business demand or competence.
