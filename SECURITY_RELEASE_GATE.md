# Security release gate — 2026-10-08

**Production status: NOT CLEARED. Dependency remediation and deployment confinement remain. On 9 October the owner requested merging the verified work into main as the development baseline; that authorization does not enable production execution or certify AI answers. Historical audit evidence below remains scoped to its dated commits.**

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

Decision #10 manual review confirmed a blocked final recommendation, but its
proposal used “does not provide/specify” instead of “unknown”. The safeguard
now recognizes these missing-detail statements too. Regression coverage checks
that both executable steps and predicted observations are removed. Verified:
81 tests passed, one opt-in Docker test skipped (82 run), 150/150 foundation
checks passed, and the changed guard passed Bandit. Existing records remain intact.


### Published-claim attribution correction

Decision #11 revealed a critique attributing permission to guess/run to a proposal
that already blocked the test. Critique prompts now require `Claim quote:
executive_key | verbatim published text` lines. The backend verifies named-speaker
quotation membership against the guarded, published proposal, allowing only
Markdown bold removal and whitespace normalization. Critiques without matching
quotations are replaced with an explicit unverified-attribution notice; already
blocked proposals are acknowledged. Backend correction warnings remain visible.
Revision tasks also receive original published proposals separately from source
evidence. If an original proposal already blocks the test, the changes section
acknowledges that retaining the stop condition is not a new change.

Quotation membership verifies attribution only, not the interpretation, completeness
or truth of a critique. These conservative safeguards do not certify arbitrary
model reasoning. No saved discussions are rewritten or model calls replayed.
Verified: 83 tests passed, one opt-in Docker test skipped (84 run); 150/150
foundation checks passed and changed Python files passed Bandit.


## Shared quality verification — 9 October 2026

Final isolated regression: 94 tests passed, one opt-in Docker test skipped
(95 run), and 150/150 foundation checks passed. The comprehensive local audit
in audit-results/20261009-182705 passed all project checks, including its
90-test suite with real Docker enabled, clean frontend install/lint/build/audit,
browser runtime and local inference. pip check and Bandit medium/high passed.
The Python dependency scan remains unclean with four known Chroma advisories.

A fresh complete-evidence local Ollama discussion completed with pending approval
and zero actions. One text-only repair per failing tool-free task was exercised.
The model still failed to produce a valid quoted critique and still falsely
called supplied fields missing; those outcomes were withheld or flagged instead
of being certified. A follow-up regression fixes warning text satisfying a
missing-heading check. Positive synthetic coverage verifies a valid quotation
can pass and publish; separate tests verify tool authority is never replayed,
corrected outputs are cached, distinct-source coverage and full research publication.
This is improved quality control, not certification of arbitrary AI reasoning.

The owner requested merging the verified work into main as a development
baseline. That request is separate from production deployment approval. Existing
credentials, runtime records and local servers were preserved. Production
dependency, confinement, encrypted off-device recovery and external-effect
limits remain documented; no real business action was enabled by this work.

## BE-08–BE-11 operating foundation audit — 9 October 2026

The new operating-policy, memory-reconciliation, observation-scheduling and
executive-activity implementation passed the comprehensive local audit in
`audit-results/20261009-191333`: 108 backend tests passed with real Docker enabled,
150/150 foundation checks, Bandit medium/high, Python compatibility, frontend
clean install/lint/build, npm audit (zero vulnerabilities), Chromium runtime and
local Ollama inference. A separate Chromium test exercised the new Operations
forms against a disposable SQLite database, including policy persistence, retained
memory correction, source-backed observation results, executive state, mobile
layout, text safety and API key privacy.

Audit fixes include timezone-aware due/expiry comparisons; atomic daily spending
limits; policy-version approval invalidation; immutable curated memory/history;
immutable observation inputs bound to exact read actions; bounded source retry
and no interrupted tool replay; actual executive role/task state; bounded activity
replay and SSE connections; and accessible Operations form labels.

Four known upstream Chroma advisories remain visible; Python dependency scanning
is not clean. Existing encrypted off-device recovery/deployment constraints and
external-effect guarantees remain outside this sprint. Existing screenshot blob
rendering retains its informational Next.js optimization warning; it requires
owner-authenticated fetching and does not expose an unauthenticated optimizer URL.
These passing development checks do not certify arbitrary AI answers or production
release. BE-08–BE-11 remain in Review until owner acceptance. See
`OPERATING_FOUNDATION.md` for provider, retention, sync and state limits.

Final follow-up: source commit `c8c382e7e8f0c2c68ed693ec033d693edd4a5b52`
passed the complete local audit in `audit-results/20261009-191836`, with all
109 backend tests passing including real Docker and the cross-device memory
regression. Curated memories now export as inactive historical records when
legacy sync cannot carry their lifecycle/source constraints; local eligibility
is unchanged. The 150 foundation checks and all other project checks passed.
The first PR #28 CI run passed compile, backend tests, live Docker, foundation,
Bandit and frontend checks; its sole failed step found the same four unpatched
Chroma advisories. The dependency gate remains visibly unclean.
