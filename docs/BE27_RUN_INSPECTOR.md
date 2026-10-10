# BE-27 — run inspection and private continuation

Business research now has a **Run inspector** above the research workspace. It shows progress without revealing prompt text or checkpoint results. Existing checkpoints remain the execution authority; the new inspection table adds generation metadata and control references.

## Review locally

Stop your existing app terminal with Ctrl+C, then run `./company start`. Keep your existing dashboard key and database.

1. Open **Business research → Run inspector**. Expand **Other workflow checkpoints** to see older recorded steps; their private keys and results are hidden.
2. Start a private practice generation or a revision from an existing approved exercise. Click **Refresh runs** to see its phase and checkpoint. The panel also refreshes every 15 seconds while visible.
3. While it is running, click **Stop private run**. Publication is blocked immediately. The current Ollama call may keep running until it returns; do not force another generation during that wait.
4. When the worker releases, click **Refresh runs**, then **Continue private run**. The control returns promptly and the inspector tracks the new attempt. Open/refresh the research record after completion and assess its actual sample separately.
5. Expand **Prompt and model versions**. Only hashes and the configured local model tag appear, not your private prompt.

A fast generation may finish before you can stop it. Do not create extra attempts just to force a stop; the deterministic worker/browser tests cover that boundary. Existing reviewed samples are not changed by merely opening this panel.

## What continuation means

A continuation is an explicit owner request for the same frozen private exercise, not replay of an arbitrary checkpoint. It is restricted to private **practice** and **revision**. Interrupted research keeps its frozen evidence snapshot; create a new research brief instead of modifying that snapshot. Old runs without inspection metadata have no stop/continue controls.

A stopped worker must release before continuation. The latest tracked run must still own the expected brief/control versions. The same approved rubric and source-freshness checks remain in force, and accepted procedures are rechecked for revocation. Revisions still require a reviewed parent and respect the ten-sample history limit. Each continuation has a distinct checkpoint key and durable link to its predecessor. Stale or repeated requests cannot claim a second result.

If generation completed durably but publication failed, continuation reuses its saved, validated text only when inputs, persona, prompt implementation, rendering/quality contracts and configured model tag still match. Otherwise it refuses reuse and asks for a new owner-reviewed exercise. If no completed checkpoint exists, continuation starts a fresh private generation; the earlier inconclusive checkpoint stays unchanged. No external action or tool is replayed.

The configured model tag is captured, but its immutable Ollama digest is **not** captured or pinned by this feature. A tag can be replaced on disk without changing its name. The inspector labels this limitation rather than asserting model identity or deterministic output. Raw generated results stay in the existing private checkpoint/database storage.

## Stop, sleep and recovery

Stop changes the brief to `needs_review` and increments its version in the same transaction as the stop request. Every worker checks its claim before inference, bounded repair and publication. A result arriving after stop cannot save a sample or clear its flag. Stop is cooperative cancellation, not a process kill; the in-flight local model call may still consume CPU until it ends.

Sample publication and the run's completion acknowledgement commit together. A failed acknowledgement rolls back the sample write, leaving the completed checkpoint available for safe recovery. Terminal completion cannot later be overwritten by an error classification. Owner assessment and launch approval remain independent.

On application startup the existing recovery paths mark interrupted steps inconclusive and briefs `needs_review`. Inspection metadata records the interruption without scheduling anything. Safe tracked private work can then be continued explicitly. A crash before inspection registration, or a legacy untracked attempt, can require a new brief; this feature does not manufacture missing provenance.

Laptop sleep pauses local work. Displayed elapsed time includes lock waiting and sleep, so a long duration alone does not prove failure and never authorizes retry. A request timeout does not stop its worker or start another one. Refresh the inspector first. Force quit loses in-memory worker state, so startup reconciliation is required before continuing. The normal server uses its existing single-process/database startup protection.

## API and storage

Owner-authenticated, no-store routes:

- `GET /runs`: bounded/paged summaries of private inspected runs and other existing checkpoint steps.
- `GET /runs/{id}`: one private run's safe metadata.
- `POST /runs/{id}/stop`: optimistic `expected_version`.
- `POST /runs/{id}/continue`: optimistic run and brief versions; queues private work and returns promptly.

`workflow_run_inspection` records brief/stage/claimed version, private checkpoint references, prompt input digest, implementation fingerprint, configured model tag, phase, closed error categories, stop flag, optimistic control version and continuation links. It creates no approval, capability or financial ledger. The UI shows no raw prompts, source bodies, checkpoint result JSON or exception traces. Legacy checkpoint keys are replaced with opaque hashed references in summaries. Metadata and result authority are kept separate.

## Verification

- 220 regression tests passed; one existing optional real-Docker integration test skipped.
- 150/150 foundation checks passed.
- Concurrency tests verify immediate publication fencing, waiting for the stopped worker, one continued sample, stale/repeated control rejection and stop-before-repair preventing another model call.
- Recovery tests reuse completed private output without inference, reject changed inputs, and verify publication/inspection atomicity.
- Owner API tests cover authentication, strict identities and private headers; summary tests exclude raw keys and private checkpoint contents.
- Real Chromium with disposable SQLite and a controlled local worker verifies metadata, stop/wait/continue, one saved sample and mobile layout. It starts no company scheduler, external action or real inference.
- Frontend lint/build/TypeScript, focused Bandit medium/high checks and formatting/catalog passed. One pre-existing image-performance lint warning remains.

Developer browser test: `.venv/bin/python scripts/runs_smoke.py` against a built temporary dashboard at port 3002 (`DASHBOARD_SMOKE_URL` can override it). Your live company API is not used.
