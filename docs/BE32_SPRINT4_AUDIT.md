# BE-32 — Sprint 4 integration audit

11 October 2026. Scope: the combined BE-24–31 implementation and owner-approved dashboard redesign. Fix project issues in the local development baseline; preserve company credentials/data and keep upstream and deployment requirements separate. No main merge, spending, publishing, customer contact or new service authority is granted.

## Findings and fixes

| Finding | Change | Evidence |
|---|---|---|
| Dependency response headers were lost on authentication, validation, lookup and conflict errors | Apply `Cache-Control: no-store` and `X-Content-Type-Options: nosniff` to backend responses in the request middleware | API tests assert private headers on 200, 401, 400, 404 and 422; mutation authentication matrix |
| Interrupted runs could advertise continuation after skill revocation or workflow withdrawal | Recheck current frozen specification, skill evidence and workflow state when reporting continuation eligibility; retain transactional checks at the actual claim | Combined SQLite tests revoke a bound skill/withdraw a template after an interrupted generation, reject continuation and preserve historical exports |
| The retained hidden Run inspector continued polling | Poll only while its business tab is selected; retain component state | Browser test switches to practice beyond the 15-second polling interval and confirms no hidden reads or extra generated samples |
| Local “today” publication dates were rejected around UTC midnight | Shared date-only age policy allows the current calendar date worldwide (up to UTC+14), rejects later dates and uses the same rule in research recency | Frozen 22:00 UTC regression accepts the next calendar date, rejects the day after, and checks age/invalid dates. This does not verify publication or demand |
| Full audit rejected Sprint 4 branches and omitted the new features | Add Sprint 4 support and skills, artifacts, runs, workflow queue, knowledge and office/browser checks | Same short `./company audit` command; temporary production build on a free loopback port |
| Older smoke tests expected old headings, exposed mobile navigation or immediate source reads | Update selectors to the reviewed layout and explicit queue/read/record-selection flow | Dashboard, agile and business research browser checks |
| Browser observation fixture could reject noncanonical fractional times; dropping fractions could move an observation before execution | Preserve millisecond ordering with canonical trailing-zero normalization in the fixture | Real API/SQLite experiment browser check retains execution-order validation |
| Direct audit builds did not explicitly suppress Next telemetry | Disable it in the audit environment, alongside existing framework opt-outs; bind pip audit to the checkout interpreter | Direct and owner-command audit environments use disposable data and existing privacy settings |

## Conceptual and authority review

| Feature | Actual delivered behavior | Boundary retained |
|---|---|---|
| BE-24 quality benchmarks | Fixed fictional fixtures and versioned measurements | Narrow automated checks, not owner approval, competence or production prompt certification |
| BE-25 executive skills | Immutable procedures grounded in exact reviewed examples | Revocation/corrected assessments block new use; skills grant no tools, budget or launch authority |
| BE-26 private artifacts | Exact inert text/Markdown exports, provenance, hash and bounded diff | Owner authentication, confined no-follow paths, private files, 30-day generated-byte expiry; samples/reviews/history remain durable |
| BE-27 run inspector | Metadata, cooperative stop and explicit private continuation | No private prompt/result defaults; no automatic replay of uncertain external actions; the authoritative sample write and completion are atomic |
| BE-28 workflows and research queue | Reviewed five-step pattern and explicit proposed-source reads | Review is not execution approval. Proposed URLs are not fetched evidence; fetched records remain unverified and separately classified |
| BE-29 company knowledge | Read-only links across existing SQLite records | No second truth/permission ledger; current memory excludes corrected, disputed, missing-source and expired records while provenance remains visible |
| BE-30 office | One CSS perspective floor using Kai’s saved illustrated portrait | Movement is opt-in presentation, pauses offscreen/hidden/reduced motion, and does not prove work; full bodies and expanded simulation remain future work |
| Dashboard redesign | Grouped navigation and separate business tabs | Existing feature and approval routes remain; tab-local state retention is not durable draft storage |

The review traced owner approval, source snapshots, exact rubric binding, sample/review history, skill withdrawal, interrupted work, artifact expiry and UI navigation together. Existing action approvals, treasury and capability checks remain the authority. Budget/permitted loss remain €0.

## Representative checked results

- An interrupted exercise bound to a subsequently revoked skill reports `can_continue: false` and `pending_input: "Skill version revoked"`. The prior artifact remains byte-for-byte unchanged; no new sample is published.
- A withdrawn workflow similarly removes continuation eligibility and rejects the claim. Reading metadata does not reapprove the template.
- An unauthenticated skill-drafting request returns 401 and creates no skill/run/artifact/source records. Boolean sample IDs fail strict validation with 422. Private response headers also cover error responses.
- At 22:00 UTC on 10 October, a date-only publication of 11 October is age zero; 12 October is rejected as future. These are synthetic calendar cases, not source verification.

## Privacy and recovery

Tests use temporary SQLite/files, synthetic credentials and synthetic model/voice results. Docker isolation and a tool-free local Ollama greeting are real runtime checks; they do not certify every agent answer or neural voice. Public-source browser tests intercept synthetic reader results and do not contact customers or fetch owner business records. The frontend build uses a separate clean copy, preserving the owner’s running apps and `.next` output.

FileVault reports **On** in a fresh read-only local check. Live SQLite remains application-level plaintext on that encrypted volume. Optional encrypted backup, restore, tampering and retention regressions remain in the backend suite. Generated-file expiry is not forensic erasure and does not remove historical sample/review text, backups or copies exported elsewhere.

## Verification

The final command and immutable implementation commit are recorded below after the complete audit finishes. Raw reports remain locally under ignored `audit-results/`; they are not published in Git.

Known Chroma advisories remain separate, unpatched upstream findings. The npm and optional voice dependency scans are independently checked. Bandit’s medium/high gate does not claim to eliminate low-severity warnings. Existing deployment confinement, external-effect reconciliation and owner-managed off-device recovery requirements remain in `SECURITY_RELEASE_GATE.md`.

## Simple owner review

From this checkout:

```bash
./company audit
```

It creates disposable test data and an internal test key. You keep your existing dashboard key and company database. If you want to view the app, stop its current terminal with Ctrl+C and run:

```bash
./company start
```

Review Business research → Run inspector and Virtual office. No new business test or spending is required. BE-32 is awaiting owner acceptance; BE-33 (retrospective) is the remaining sprint item after this review.

## Final local evidence

`./company audit` completed on implementation `5292f9481998f96ea14398b03b1f8dd68462b494`. Local report: `audit-results/20261011-000620/summary.json`. All 32 project audit stages passed, with one separate upstream dependency stage.

- 247 backend tests passed, including real Docker isolation (opt-in enabled); no test skip.
- All 150 foundation regression checks passed.
- All 15 isolated production browser feature checks passed, including the new combined office/dashboard check.
- pip check, Bandit medium/high, optional voice dependency audit, clean npm install, review-summary/native-glob contracts, lint, TypeScript/webpack build, API policy, npm audit, Chromium runtime and tool-free local Ollama inference passed.
- npm audit: zero vulnerabilities. Bandit: zero medium/high findings; 16 low-severity findings remain. The existing image-performance lint warning remains.
- Python audit: four known unpatched Chroma advisories; recorded as UPSTREAM, never ignored or called clean.
- `./company check-code` passed. FileVault is On.

Earlier failed audit reports remain visible. Their failures led to the recorded fixes; they were not rewritten or passed by suppressing tests. The final report above is the complete successful rerun. Subsequent documentation-only commits do not change the tested implementation. GitHub CI must be evaluated separately after push; this local result is not production deployment clearance.
