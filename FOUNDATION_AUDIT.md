# Foundation Hardening Audit

> **2026-10-08 update:** Docker command isolation, durable agent/action checkpoints, 30-day generated artifact retention, optional encrypted backups and clean npm audits are implemented and tested. Chroma dependency and deployment confinement blockers remain. Read [SECURITY_RELEASE_GATE.md](SECURITY_RELEASE_GATE.md) before merging.

Status: pre-frontend backend/security/privacy audit  
Branch: `chatgpt/foundation-hardening`

## Scope

This pass reviewed the backend control plane, persistence, action execution, browser/research networking, Telegram control, scheduler/autonomous follow-up, executive memory, sync, treasury/approval authority, runtime artifacts, configuration, dependency automation, and the current dashboard credential/browser boundary.

The goal is not to claim the system is "perfectly secure." The goal is to make the trust boundaries explicit, fail closed where practical, and record residual risks that require architectural—not regex/prompt—solutions.

## Fixed or materially hardened on this branch

- One authoritative action-control path for API and Telegram approvals/execution.
- Approval payload binding so an approved action cannot silently mutate before execution.
- HMAC-authenticated JSONL sync; tampered rows are rejected.
- Imported remote approvals/reservations do not become local execution/spending authority.
- Raw host shell execution is disabled by default.
- Structured file I/O uses descriptor-relative/no-follow operations, rejects special/multi-hard-link targets, bounds reads/writes, uses atomic writes, and keeps files private.
- Browser actions block service workers/downloads and validate HTTP(S) navigation, redirects, subresources, popups/new pages against SSRF policy.
- Research networking rejects embedded credentials/unapproved ports, revalidates redirects, bounds body size, and restricts content types.
- API binds loopback by default and refuses accidental non-loopback plaintext exposure.
- Non-local LLM endpoints are blocked unless explicitly opted in; explicit remote LLM transport must use HTTPS.
- CrewAI telemetry is disabled before framework imports by project default.
- Telegram transport details/errors are suppressed from logs.
- Telegram action descriptions/details stay local by default.
- Telegram remote approve/reject/execute is disabled by default and requires explicit opt-in.
- Unauthorized Telegram callback sender identifiers are not retained in logs.
- Dashboard API key is held in memory only; no localStorage/sessionStorage persistence.
- Dashboard security headers/CSP are enabled and production CSP removes unsafe-eval.
- Database, backups, sync exports, logs, workspace and screenshots use owner-only permissions where supported.
- Browser screenshots have explicit bounded retention.
- Common credential/token shapes are rejected from durable action storage.
- Autonomous follow-up retry state is durable and backoff-aware.
- Autonomous scans paginate instead of silently stopping at fixed row limits.
- Security CI runs compilation, Bandit, pip-audit, frontend lint/build and npm audit.
- Dependabot monitors Python, npm and GitHub Actions.
- Duplicate environment templates were removed to prevent security-config drift.

## Residual risks that are NOT solved by this branch

### 1. Host execution is still not a strong sandbox

Even with raw shell default-off and structured action guards, the current execution boundary is the host process. Playwright and future side-effecting tools can still interact with host resources allowed to the process.

**Recommended next foundation phase:** disposable Docker/VM execution workers with:
- read-only base image;
- explicit workspace mount only;
- no host Docker socket;
- dropped Linux capabilities;
- non-root user;
- CPU/memory/PID/time limits;
- network off by default, per-action egress allowlist when needed;
- ephemeral filesystem destroyed after the action;
- signed result envelope returned to the control plane.

This should happen before adding broad new execution capabilities.

### 2. SQLite/backups/sync exports are private-permission, not encrypted at rest

`0600` protects against other normal local users, but does not protect against:
- malware running as the same user;
- stolen/unlocked device;
- copied backup/export files;
- filesystem-level access outside the OS account boundary.

**Current mitigation:** local-first defaults, owner-only permissions and signed sync integrity. FileVault is verified On on the audited Mac; optional authenticated encrypted backups and integrity-checked restore are implemented. Backup encryption needs an owner-managed key and does not encrypt copied sync exports or replace deployment verification.

**Remaining:** verify off-device encryption/key recovery and account isolation. Application SQLite is plaintext on the encrypted system volume; other machines and older copies are outside this evidence.

### 3. Checkpoint integration is implemented; uncertain effects still require review

Approved actions and synchronous agent tasks now use input-bound durable checkpoints.
Meetings, preparation, daily research and autonomous follow-up use persistent run IDs.
Successful outputs and proposal IDs are reused; interrupted/running steps block replay.
A private Unix instance lock prevents startup recovery from reconciling another server.
Exactly-once external effects still need provider idempotency and owner reconciliation.
See SECURITY_RELEASE_GATE.md for tests and deployment limits.

### 4. Generated artifact retention is implemented

The owner selected 30 days. Startup/daily cleanup expires generated rotated logs,
screenshots and registered exports in SYNC_EXPORT_DIR. Active logs rotate daily and
by size. Existing count limits remain. Approval, execution, decision, memory and
checkpoint evidence is preserved; unknown files and copied exports are not deleted.
Deletion is not forensic secure erasure, and cleanup needs the server to run.

### 5. Telegram is still a third-party trust boundary

With the new defaults it is notification-only and redacted unless explicitly opted into remote control/detail egress. If the owner enables remote control, Telegram account/device security becomes part of the execution trust chain.

### 6. Remote LLM use changes the privacy model

The system is local-first by default. Explicitly enabling a remote HTTPS model means prompts, executive memory and task context can leave the machine. Provider retention/training policies are outside this repository's control.

## Comparable project research

### OpenHands

Relevant lesson: execution belongs in an isolated runtime rather than the control-plane host. OpenHands documents hardened Docker/network-binding guidance for security-sensitive deployments.

**Adopt:** disposable execution runtime pattern.  
**Do not copy blindly:** mounting the host Docker socket would undermine the isolation goal for this project.

### Microsoft AutoGen

Relevant lesson: local command execution is a materially different risk class from Docker execution. AutoGen's ecosystem explicitly calls out the danger of LLM-generated local code execution.

**Adopt:** make unsafe local execution an explicit opt-in and display the executor/risk class in audit state. The current branch already defaults raw shell off; the next step is container execution.

### LangGraph

Relevant lessons:
- checkpoint state at workflow boundaries;
- use durable thread/run identifiers;
- persist pending writes;
- resume without recomputing successful work;
- isolate side effects into idempotent tasks;
- prune persistent state instead of letting it grow forever;
- strict deserialization allowlists.

**Adopt:** step-level durable execution + idempotency layer for meetings/preparation/execution.  
**Already aligned:** schema-limited SQLite/JSON storage instead of arbitrary Python-object deserialization.

### Letta / memory-oriented agents

Relevant architectural lesson: distinguish working context from durable long-term memory and make memory explicitly inspectable/manageable.

**Already aligned:** executive memory is structured, role-scoped, provenance-linked, advisory-only, and owner-deactivatable.

### CrewAI

Relevant lesson: framework agent/tool behavior should not itself be the security boundary. Tool capability and approval authority must remain outside model prompts.

**Already aligned:** reasoning-only agents, separate preparation, resource/action gates, centralized capability policy and deterministic action control.

## Recommended sequence before frontend v2

1. **Completed locally: all 150 verification checks.**
2. Run CI dependency/security scans and review any Bandit/pip-audit/npm findings.
3. Perform one real regression flow:
   - decision -> approval -> preparation -> action proposal -> approval -> sandbox execution;
   - verify approval binding and no Telegram remote control by default.
4. Docker command boundary is implemented/tested; extend verified isolation to host-side browser tools and the final deployment.
5. Durable agent/action checkpoints are implemented; interrupted effects require reconciliation.
6. Generated artifact age retention is implemented; legal/business audit evidence remains durable.
7. Only then continue major frontend/virtual-office work.

## Security posture after this branch

The control plane is substantially stronger than the original implementation: authority is centralized, sensitive transports are opt-in, host shell is default-off, network/file boundaries are fail-closed, runtime artifacts are private/bounded, sync has integrity/auth authority separation, and autonomous failures are recoverable.

The largest remaining risk is architectural: side effects still ultimately execute from the host process rather than an isolated disposable worker. That should be treated as the next major foundation milestone, not hidden behind additional regexes or prompt rules.

## Local dashboard and meeting verification — 2026-10-08

The owner confirmed the isolated dashboard/8001 API meeting flow. A real bug in
Next's CSP was fixed: connect-src now follows the validated configured API origin
rather than hard-coding port 8000. Local lint/build and browser verification pass.

Generated Owner Acknowledgement sections are now normalized to pending owner
review, including cached retries; they cannot assert newly recorded human consent.
When a retrospective's current source explicitly declares no company/business data
or no supplied outcome evidence, final and individual published outputs report
missing evidence rather than model-invented outcomes. Historical memory does not
satisfy current evidence. Observations supplied in other prompts are not classified
as verified merely because this narrow absence guard does not trigger.

Eight recovery/evidence integration tests pass, 150/150 foundation checks pass,
and the changed workflow files pass Bandit. A separate real local Ollama -> FastAPI
-> SQLite test verifies the no-evidence retrospective with disposable data and
Telegram/background workflows disabled. Existing history is not rewritten.

Audit scope follows the owner's clarification: controllable project security,
privacy and bug fixes are audited; unpatched third-party advisories are tracked
separately as upstream limitations. Deployment readiness and production release
requirements remain separate from completion of a particular project fix.
