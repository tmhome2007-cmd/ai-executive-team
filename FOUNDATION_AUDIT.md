# Foundation Hardening Audit

> **2026-10-08 update:** A constrained Docker-only opt-in command worker is now implemented and unit-tested. The original host-shell execution path was removed. This is not equivalent to a dedicated VM security boundary, and the dependency, runtime, recovery and privacy release blockers remain open. Read [SECURITY_RELEASE_GATE.md](SECURITY_RELEASE_GATE.md) before merging.

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

**Current mitigation:** local-first default, owner-only permissions, signed sync integrity, no secrets intentionally stored.

**Recommended:** rely on full-disk encryption immediately; later add an optional encrypted export/backup layer with a dedicated key and authenticated encryption. Do not invent a home-grown crypto format.

### 3. Durable workflow execution is not yet step-checkpointed

The database records business state and guards side effects well, but a long multi-agent workflow is still closer to a single run than a durable workflow engine.

**Recommended next foundation phase:** explicit run/step state:
- run UUID;
- step UUID and deterministic idempotency key;
- input hash;
- started/completed/failed timestamps;
- persisted output;
- retry count;
- side-effect marker;
- resume-from-last-safe-step logic.

Never replay a completed side effect just because the LLM/workflow process restarted.

### 4. Retention is not globally policy-driven yet

Logs/backups/screenshots are bounded, but durable decisions/actions/memories/outcomes are intentionally long-lived and there is no central privacy-retention policy.

**Recommended:** owner-configurable retention classes:
- operational logs;
- screenshots/browser evidence;
- sync exports;
- retired memories;
- old failed test fixtures;
- permanent audit/treasury records.

Deletion rules must preserve accounting/audit integrity.

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

1. **Run and fix all 149 verification checks on this branch.**
2. Run CI dependency/security scans and review any Bandit/pip-audit/npm findings.
3. Perform one real regression flow:
   - decision -> approval -> preparation -> action proposal -> approval -> sandbox execution;
   - verify approval binding and no Telegram remote control by default.
4. **Containerized execution boundary** for future side-effecting tools.
5. **Durable step/checkpoint model** with idempotency/resume semantics.
6. Add global retention-policy configuration.
7. Only then continue major frontend/virtual-office work.

## Security posture after this branch

The control plane is substantially stronger than the original implementation: authority is centralized, sensitive transports are opt-in, host shell is default-off, network/file boundaries are fail-closed, runtime artifacts are private/bounded, sync has integrity/auth authority separation, and autonomous failures are recoverable.

The largest remaining risk is architectural: side effects still ultimately execute from the host process rather than an isolated disposable worker. That should be treated as the next major foundation milestone, not hidden behind additional regexes or prompt rules.
