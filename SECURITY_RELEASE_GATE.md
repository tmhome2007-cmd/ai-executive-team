# Security release gate — 2026-10-08

**Status: NOT CLEARED. Do not merge this branch into main or enable production/live execution based on this audit alone.**

## Verified on GitHub Actions
- Python syntax compilation passes.
- Frontend ESLint and production build pass on hardening commits after typing fixes.
- Docker-worker unit tests pass on CI commit `bbb180e`.
- New CI runs now attempt dependency audits even when lint/Bandit fails.
- Full-system verification has been wired into CI, but its final result must be read from the latest workflow run.

## Remediations committed
- Centralized authority/approval bindings, imported-sync authority restrictions, fail-closed network/file controls, private artifact defaults: see `FOUNDATION_AUDIT.md`.
- Live raw-shell execution replaced by a Docker CLI invocation with fixed flags: network disabled, read-only container root, non-root UID, no capabilities, no-new-privileges, PID/RAM/CPU/timeout bounds, only workspace bind mount, Docker socket never passed, offline image selection; fails closed if Docker unavailable.
- Docker worker unit tests ensure constant CLI boundary. Tests mock the Docker invocation; they **do not** constitute a hostile-container penetration test.
- Owner-sensitive dry-run command details no longer printed verbatim to the console.
- Dashboard explicit-any ESLint errors repaired.
- Timed-out Docker worker attempts forced removal by unique name.

## Open release blockers
1. **CRITICAL — vulnerable Next.js dependency.** npm audit reports a critical `next/og` advisory and eight other high vulnerabilities. Patch Next.js and matching eslint-config-next and regenerate `package-lock.json` with npm; rerun npm ci, lint, build, audit. Never edit package.json alone and leave a stale lockfile.
2. **HIGH — vulnerable ChromaDB transitive dependency.** pip-audit reports five advisories against chromadb 1.5.9 installed via CrewAI. Investigate compatible updates/constraints without bypassing CrewAI compatibility. A lockfile/constraints mechanism is recommended.
3. **MEDIUM — dynamic SQL Bandit B608 warnings.** Current 21 findings include parameterized placeholders and code-generated column lists; validate each dynamic identifier against fixed whitelists. Suppress only individually justified false positives, never blanket-skip B608.
4. **Workflow persistence.** No integrated per-step transactional checkpointing and exactly-once effect recovery has been demonstrated. Approved side effects must not be replayed after process crashes.
5. **Docker runtime limitations.** Docker daemon trust, mutable image tags, workspace writable mount, process cleanup failure, host-level process ownership and malicious code inside workspace remain concerns. Pin image digest, use a dedicated worker host/VM and restrict Docker daemon access. Test with a real installed Docker runtime prior to live use.
6. **Privacy.** Long-lived SQLite, backups, sync history and audit data are not encrypted at rest at the application layer. Add retention configuration, full-disk encryption guidance and opt-in encrypted exports.
7. **External transports.** Remote LLM and Telegram opt-ins transmit context to external services. Maintain disabled-by-default and verify logs contain no sensitive data.
8. **End-to-end testing.** Exercise decision -> owner approval -> preparation -> execution -> failure -> restart -> idempotent resume, plus tampered imports, adversarial URLs, symlinks, and concurrent approval requests on a disposable machine.
9. **GitHub Actions supply chain.** Existing third-party actions are referenced by mutable major tags; consider full-commit SHA pinning.

## Gate criteria
- GitHub Actions: compilation, verification, isolated-executor unit tests, Bandit, pip-audit, npm ci/lint/build/audit all green.
- No unresolved critical/high vulnerabilities or undocumented accepted risk.
- Manual live sandbox escape/SSRF/concurrent-approval tests witnessed.
- No accidental calls to real Telegram or external LLM during verification.
- Database migration and backup/restore tested on copies.
- Explicit sign-off before merging `main`.

This file is an **audit record, not a claim that the release gate passed**.
