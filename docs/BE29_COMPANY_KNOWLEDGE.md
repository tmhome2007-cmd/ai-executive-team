# BE-29: evidence-linked company knowledge

## Owner review

Stop your running `./company start` with Ctrl+C, then run `./company start` from this checkout. Keep your existing API key and database.

Open **Company knowledge**:

1. Search record titles and excerpts, or filter by record kind. The initial page includes historical records.
2. Choose **Inspect** to see saved fields, status, warnings and the relationships recorded in the database. Follow a related record; use **Back to previous record** to retrace your route.
3. For a lesson, inspect **Current agent memory context**. A withheld lesson stays visible in history, with reasons such as correction, expiry, conflicting claims or disputed/missing sources.
4. Choose **Exclude withheld lessons** to see only currently eligible lessons alongside other historical record types. Eligibility means advisory context, not verified truth or approval.
5. Inspect a skill to follow its exact samples and owner assessments. Corrected assessments remain readable and make dependent skill evidence unavailable under the existing skill rules.

Corrections still use the existing authenticated memory-review controls under **Organizational work**, rather than a new fact-editing system. No test data is inserted into your company records by this feature.

## Domain and boundaries

This increment is read-only navigation over existing SQLite goals, decisions, proposed actions, outcome measurements, executive lessons, skill versions, evidence records, research briefs, practice samples and assessments. It creates no graph database, inferred relationships, duplicate approval ledger or autonomous retrieval workflow.

Relationships explain their source field/table, recorded timestamp when available and target identity. Stored `supports`/`contradicts` claims remain unverified; source registration or owner confirmation does not independently verify them. Proposed URLs in the research queue are not evidence and are excluded. Personal-life simulation records, executable action details, commands, result blobs, approval seals and credentials are excluded from this view.

Linked goals, decisions and actions are checked against stable sync UUIDs where recorded. A missing or mismatched target remains unresolved and cannot be followed as if the link were valid. Action/outcome links apply the same identity check. No fallback associates a record solely by a conflicting local ID.

Memory eligibility uses one shared policy in `memory/context_policy.py`, consumed both by executive-memory retrieval and this explanation view. It withholds inactive/non-active-lifecycle lessons, expired or invalid-expiry lessons, lessons with missing/disputed/expired sources, and conflicting current claims. Uncurated legacy memories can remain advisory context and are explicitly labelled as lacking registered review sources. Existing source-backed correction and immutable revision history remain authoritative.

Skill status uses the existing exact-review eligibility logic. Accepted procedures become unavailable when supporting assessments are corrected; old versions and assessments remain visible. This view grants no spending, tools, publishing, customer contact, model training or launch authority.

## Retrieval and privacy

All endpoints require the existing owner authentication and return `Cache-Control: no-store`. Reads occur in a SQLite snapshot and return a retrieval time. Search binds owner text as data; kinds and SQL schemas are fixed internal whitelists. The current context policy uses fixed predicates, never model- or owner-supplied SQL.

Search is literal, case-insensitive under SQLite's standard `lower` behavior, against titles and the first 300 characters of content. It is not semantic or exhaustive full-text search. Pages contain at most 50 nodes (dashboard uses 30); relationship pages contain 30 links. Individual incoming relationship groups are capped at 200 with an explicit omission notice. Saved text fields are capped at 12,000 characters and indicate truncation. Memory revision detail shows the latest 50 revisions with a remaining-history flag; use the existing paged history endpoint for older revisions.

Timestamps describe the record's stored creation/update/observation time. Practice assessments preserve the owner-supplied observation time; the legacy table lacks a separate assessment creation timestamp. Missing times remain unknown. This view does not fetch source URLs, invoke models, write files, change records or transmit company context externally. Durable evidence/review retention follows the existing policy; no new generated artifact storage is introduced.

## Verification

- Eleven disposable SQLite/API tests cover recorded provenance, metadata privacy, correction history, shared exclusions, conflicts, expired/missing/disputed sources, stable identity mismatch in both directions, bound/paged search, retained corrected assessments and skill eligibility, multiple evidence claims, link pagination and explicit text truncation.
- Full regression suite and 150 foundation checks; changed-module Bandit scan with narrowly documented fixed-schema SQL construction.
- Frontend lint/build, formatting/catalog checks and real Chromium navigation through goal → decision → action → outcome and corrected lessons, current-context filtering, safe search and mobile layout. The browser uses disposable SQLite, only GET API requests and blocks external traffic.

No new dependencies or imported third-party code. Existing upstream Chroma advisories remain separately tracked. General semantic retrieval and reviewed AI relationship suggestions are later increments.
