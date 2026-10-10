# BE-26 — private practice files

Saved practice samples can be exported as plain text or Markdown. An export preserves the exact stored sample, including any AI commentary; it does not rewrite the sample, assess quality or grant launch permission. No code runs and no cloud service is used.

## Review locally

Stop your app terminal with Ctrl+C, then run `./company start` in this checkout. Keep your existing dashboard key.

1. Open **Business research** and select a brief with a saved practice sample.
2. In **Private deliverable files**, choose the sample and TXT or Markdown, then **Export saved sample**.
3. Download the file. Its content should match that saved sample exactly. The displayed hash and rubric identify its provenance.
4. If that brief has a revised sample, export it too. Choose the original and revised files and click **Compare files**. A text difference is not proof of improvement; the owner review remains separate.

Legacy samples without an immutable rubric binding cannot be exported. Make a new structured exercise rather than inventing provenance for an old record. You do not need to generate a new sample just to export an existing bound sample.

## Storage and authority

`practice_artifacts` is an append-only metadata table. Each row records its source sample/brief/attempt, format, SHA-256, byte count, frozen specification/rubric, parent sample and feedback review, optional procedure version, frozen research-source snapshot and creation/expiry times. Source assessments stay in the existing review ledger; exports create no approval ledger.

Files live next to the configured database in `practice-artifacts/`, with directory permissions 0700 and file permissions 0600. Storage names are opaque server-generated identifiers, never client paths. The owner-authenticated API serves attachments as inert plain text with no-store, nosniff and sandbox headers. The dashboard downloads through an authenticated fetch; it never puts the key in a URL or renders Markdown as HTML.

One export per saved sample and format makes retries idempotent. A revision creates a distinct immutable sample/version. Exporting again cannot replace bytes, repair a missing file or reset expiry. Comparisons require the same frozen exercise. A changed file fails its hash check; symlinks, hardlinks, special files, unsafe permissions and symlinked parents are rejected.

Export permits only `.txt` and `.md`, up to 120000 UTF-8 bytes. It rejects HTML-like tags, javascript/vbscript/data URL schemes and non-printing control bytes. This deliberately conservative prose restriction is not a universal content sanitizer. Code fences are inert text and are never executed. Comparison is bounded to 2000 lines per file; the workspace holds at most 1000 files (at most 120 MB of normal export bytes). Metadata lists page in batches of 100.

## Retention and recovery

Generated export bytes expire **30 days after their first export**, even if the application was offline. Downloads are refused at expiry. Startup and the existing periodic retention job remove expired safe owned files. Their immutable metadata, saved sample text, reviews and source records remain. Thus 30-day file retention does **not** erase the durable practice text. User-downloaded copies and earlier backups are outside this deletion policy and require separate owner handling.

Publication writes and fsyncs an exclusive private file before committing its metadata under a SQLite write transaction. A database failure cleans the file; a process crash can leave an unpublished orphan. Safe orphan files with generated names are removed after 30 days. Missing/corrupt files are reported as unavailable rather than regenerated. Unrelated or unsafe files are left alone. Backups containing only SQLite preserve metadata and samples, not the exported file directory; a database-only restore therefore honestly reports missing files. Preserve that private directory separately if restoring unexpired exports is required.

## Verification

- Regression suite: 212 tests, passed; one existing optional real-Docker test skipped.
- Final focused artifact/retention tests after expiry-boundary and concurrent-removal fixes: 13 passed.
- Foundation regression: 150/150 passed.
- Artifact boundaries include authentication, private headers, exact content, immutable metadata, expiry, retry, missing/corrupt/link handling, directory confinement, unsafe markup, output limits, crash orphans and failed-publication cleanup.
- Real Chromium with disposable SQLite/API: authenticated download bytes, two versions, comparison and mobile layout passed. No company scheduler or real model generation was started.
- Frontend lint/build/TypeScript, focused Bandit medium/high findings and formatting/catalog checks passed. Lint retains one existing image-performance warning.

Developer browser check: `.venv/bin/python scripts/artifacts_smoke.py` against a built temporary dashboard at port 3002. `DASHBOARD_SMOKE_URL` overrides that address. Synthetic test data and intercepted API requests keep this separate from the running company database.
