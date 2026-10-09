# Security release gate — 2026-10-08

**Status: NOT CLEARED. Work remains on dependency remediation and deployment confinement. Do not merge into main or enable production execution based on this audit.**

## Implemented and locally verified

- Approval and execution authority are bound to owner-reviewed records. Imported sync history cannot confer execution authority. Two-worker SQLite claims, signed-import SQL attacks, tampered status/column inputs and bound UPDATE literals are tested.
- Approved action execution and synchronous CrewAI agent steps claim durable checkpoints. Successful agent outputs and proposal IDs resume without another model/tool invocation. Input changes, crashes, running steps and uncertain effects block replay for manual reconciliation. Decisions are persisted once per workflow key. Meetings, preparation, daily research and autonomous follow-up now supply durable run IDs.
- A private Unix file lock excludes a second server using the same database before startup reconciliation. Unsupported platforms fail closed; network filesystem locking is not verified.
- Research runs synchronous CrewAI in a worker thread that owns the execution lock. Timeout/cancellation does not release the worker's lock while its execution continues. Research evidence and terminal results are stored durably. Informational notifications are not exactly-once delivery.
- Real FastAPI/CrewAI integration with a synthetic LLM verifies decision replay, approval-required preparation, proposal creation, execution refusal before action approval, approved disposable file execution and refusal of duplicate execution. No real Telegram messages or business actions are used.
- Docker execution uses a digest-pinned offline image, non-root UID, blocked networking, read-only root, no capabilities, no-new-privileges and bounded resources. Local Docker Desktop tests cover host paths, symlink attempts and isolation. Unknown live outcomes require reconciliation.
- Full npm audit is **zero vulnerabilities** after replacing the vulnerable fast-glob development chain with a narrow native Node glob adapter. Tests exercise the real pinned Next ESLint plugin, brace limits, directories and unsupported options. Clean npm ci, lint and Webpack production build pass locally. No forced framework downgrade or advisory ignore.
- Bandit medium/high gate passes. The 21 reviewed B608 sites have individual dispositions and real SQL injection regressions; low-severity findings are not claimed eliminated.
- Consistent SQLite backups support optional authenticated Fernet encryption, exclusive integrity-checked restore and count retention. Tampering, wrong keys and unsafe backup paths fail closed. Encryption is not enabled on the live deployment by this audit.
- FileVault reports **On** on the audited Mac. That evidence does not cover off-device exports or other deployments. Live SQLite remains application-level plaintext on the encrypted volume.
- The owner selected **30 days** for generated logs, screenshots and sync exports. Startup/daily cleanup expires rotated logs, generated screenshots and registered exports in SYNC_EXPORT_DIR. Active logs also rotate daily or by size. Unknown files, unsafe directories, symlinks and hard links are protected. Approval/execution/decision/checkpoint history is preserved. Expiry runs daily while the server runs, and deletion is not forensic erasure.
- Agent verbose traces are disabled. Telegram defaults to generic dashboard reminders; explicit opt-in is required for sensitive details. Transport exception text and HTTP client logs are suppressed. Production credentials and data were not copied.
- GitHub workflow actions remain pinned. Application and audit tools install in one constrained resolver transaction followed by pip check. The earlier workflow credential limitation was resolved through the connected GitHub app.

## Local evidence

Python 3.12.14: 150/150 system regression checks pass. The security suite includes 27 distinct tests, including real Docker and daily
active-log expiry. pip check and Bandit medium/high pass.
Frontend lint passes with one pre-existing no-img-element warning; clean install,
native-glob integration tests, production Webpack build and full npm audit pass.
A tool-free real CrewAI agent completes a synthetic task against local Ollama
llama3.1 and resumes its saved result. This is not a ten-agent model-quality audit.
Default Turbopack passes on prior CI; local sandbox worker binding is restricted.
GitHub Actions evidence for the final tested implementation is recorded below.

## Remaining blockers and limits

1. **ChromaDB dependency advisories.** CrewAI 1.15.25 requires chromadb ~=1.5.9. The tested constrained resolution has four unique unresolved advisories: PYSEC-2026-311, PYSEC-2026-3813, PYSEC-2026-3814 and PYSEC-2026-3815. The audit feed reports no fix versions. No blanket ignore or incompatible package removal is used. Do not run a Chroma server or load untrusted models. A compatible patched release or a reviewed framework/storage replacement is required to clear this dependency gate.
2. **Deployment confinement.** Docker daemon/kernel trust and a writable workspace remain. Host preflight and URL/DNS checks cannot prove race-free confinement against concurrently hostile processes or DNS rebinding. Use a dedicated worker VM and verified network egress controls before exposing live tools to adversarial workloads. Local Docker tests are evidence of baseline boundaries, not proof of sandbox escape resistance.
3. **External effects and reconciliation.** Local checkpoints cannot guarantee exactly-once external effects. Interrupted tools remain inconclusive and need owner inspection; provider idempotency keys are still required for future external integrations. Cached output does not itself prove model reasoning is correct. Manual crash/escape testing on the final deployment is still required.
4. **Encryption deployment.** Optional backup encryption needs an owner-managed key and verified off-device recovery. This audit does not change production keys or delete older plaintext copies. Retention does not automatically delete legal/business approval history or copies exported outside configured directories.
5. **Final CI verified; dependency gate still fails.** Run 37826110515 on 08ee7ee passes backend compatibility, compilation, security tests, real Docker, 150/150 checks, Bandit and the complete frontend gate. Its only failing check is pip-audit with four Chroma advisories. The CI correction is verified.

## Release criteria

Compilation, regression checks, security tests, Docker isolation, pip check,
Bandit, lint/build and dependency audits must pass on the final head. No unresolved
critical/high vulnerabilities or undocumented accepted risk. Verify encryption,
restore and deployment confinement on the intended target. Explicit owner sign-off
is required before merging main. This record does not claim that the gate passed.

## CI continuation on b97c197

[Run 37825733581](https://github.com/tmhome2007-cmd/ai-executive-team/actions/runs/37825733581)
passes the complete frontend gate (clean install, native adapter, lint, production
build and both npm audits), backend install/pip check, compilation, all 150
regression checks and Bandit. The new log-expiry test used a macOS-specific
temporary directory and failed on Linux; its fixture now uses the platform
temporary directory with canonicalization. This is a test-portability correction.
Chroma pip-audit still reports four unique advisories with no fix versions.
The corrected final code needs a fresh CI run, including the Docker steps that
were skipped after the fixture failure.

## Final implementation verification

[Run 37826110515](https://github.com/tmhome2007-cmd/ai-executive-team/actions/runs/37826110515)
on implementation commit `08ee7eef481f5d35ca00ba3a8bd1c4a35927803c` confirms:

- Backend installation and pip check: pass.
- Python compilation: pass.
- Security suite: 27 discovered tests, 26 pass and the opt-in Docker test is
  skipped in this initial pass; the separate real Docker test passes.
- System regression: 150/150 pass.
- Bandit medium/high: pass (21 reviewed SQL dispositions; low findings remain).
- Frontend clean install, native adapter tests, lint and default production build: pass.
- Both npm dependency audits: pass, zero vulnerabilities.
- Python dependency audit: fails solely for four unique ChromaDB advisories.

The follow-up commit recording this evidence changes documentation only.
The release gate remains NOT CLEARED for the explicitly listed dependency and
deployment requirements; no main merge or live business action was performed.

## Organizational work sprint evidence — 9 October 2026

BE-04–07 add source provenance, reviewed executive planning, published discussion
rounds and scoped capability inventory. All APIs use the existing owner-auth dependency.
New activity events omit source/discussion contents and credential fingerprints.
Approval seals bind new capability authority; fresh checks, role/host/scope constraints,
rotation and revocation are checked before claiming execution. Scoped browser
preparation resources cannot be bypassed by omitting a manual action binding.

The Organizational work production-build Chromium smoke exercises source review,
owner plan/task review, discussion publication and manual access verification/revocation
against disposable SQLite via real APIs, with synthetic model responses. It verifies
pending direction, safe model text, mobile width, memory-only API keys and no business
execution or treasury movement. Real CrewAI tests separately verify plan generation,
seven role/round checkpoints, canonical personality snapshots and inference-free replay.
Provider permission/rotation/revocation tests use synthetic credentials and mocked
GitHub/Chromium probes; real user credentials were not read or used.

Whole-database backups retain these new tables. Existing sync payloads do not export
them. This implementation does not add arbitrary provider execution tools or certify
local model answers. Production/dependency release criteria above remain separate.

Final sprint head local checks: 69 tests run, 68 passed and one opt-in Docker test
skipped; 150/150 foundation checks; compilation/pip check; Bandit with zero medium/high
findings; frontend lint (existing image warning)/Webpack build; all three real API/
SQLite Chromium feature smokes passed. Docker/Ollama/dependency audits were not
re-run for this sprint; earlier evidence and unresolved upstream findings remain
separate. New final-head CI results must be evaluated after pushing.

## Tracing regression correction — 9 October 2026

A supplied manual-runtime log confirmed one CrewAI trace export and interactive
sharing prompts despite the telemetry opt-out. Prior claims that telemetry defaults
alone ensured no trace sharing were insufficient. The application now forces tracing
off before framework import and passes tracing=False to all production Crew instances.
Real synthetic-Crew regression tests cover saved consent and reject sharing/prompt
attempts. The prior uploaded trace's contents/deletion have not been verified.
70 tests passed with one opt-in Docker test skipped, 150/150 foundation checks and
frontend lint/build passed. Discussion waiting text now explains the multi-call local
model workload; the interrupted manual run was not automatically replayed or modified.


## Discussion evidence and test detail correction — 9 October 2026

Proposal, revision and synthesis now request prerequisites, setup, ordered steps,
observations, pass/fail criteria and a causal limit. Missing original reproduction
details must be requested before a test is executable. A reminder appearing alone
does not identify the cause of an earlier failure. Unsupported account settings
or external services must not be assumed from the fictional check example.

Each newly published round stores an immutable, versioned quality assessment.
Missing headings/test labels, selected unestablished dependencies and selected
causal assertions produce review warnings. Subsequent rounds receive these cues
separately from source evidence; unresolved synthesis warnings also appear on the
parent decision. The dashboard displays the stored assessment and its limits.
These are narrow heuristics, not factual validation, proof of causality or an
approval gate. Human review and action authorization remain separate. Historical
discussions are preserved and labelled not assessed; no saved conversations are
rewritten or re-executed. Fresh local Ollama output still needs owner review.

Verification: 77 tests passed, one opt-in Docker test skipped (78 run);
150/150 foundation checks passed. Changed Python files passed Bandit. Frontend
lint passed with the existing image warning; the production webpack build passed
in disposable storage. No real-model discussion was automatically re-run.


### Missing-prerequisite stop condition

The manual decision #9 trial exposed a contradictory variable-due-time fallback.
New proposal/revision/synthesis instructions forbid substituting unknown test
conditions. A deterministic safeguard detects explicit missing reproduction
prerequisites in the response and replaces its proposed test section with a
blocked request for the original reproduction steps, due time, build and
observation channel. Expected observations are suppressed while blocked.
The published round records a backend-intervention warning; the parent decision
also receives the guard and review warnings. Critiques remain available for
review. Historical records are unchanged. This conservative text check does not
certify all model output or infer missing conditions from arbitrary evidence.

Verification: 80 tests passed, one opt-in Docker test skipped (81 run),
150/150 foundation checks passed and changed Python files passed Bandit.
Regression cases cover the reported fallback, idempotence, known inputs,
critique preservation, published instructions, parent output and pending approval.
