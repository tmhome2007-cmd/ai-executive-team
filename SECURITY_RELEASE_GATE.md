# Security release gate — 2026-10-08

**Status: NOT CLEARED. Do not merge this branch into main or enable production/live execution based on this audit alone.**

## Verified on GitHub Actions
- Python syntax compilation passes.
- Frontend ESLint and production build pass on hardening commits after typing fixes.
- Docker-worker unit tests pass on CI commit `bbb180e`.
- New CI runs now attempt dependency audits even when lint/Bandit fails.
- Full-system regression verification passed **149/149 checks** on the dependency-updated branch (workflow 37812997279).

## Remediations committed
- Centralized authority/approval bindings, imported-sync authority restrictions, fail-closed network/file controls, private artifact defaults: see `FOUNDATION_AUDIT.md`.
- Live raw-shell execution replaced by a Docker CLI invocation with fixed flags: network disabled, read-only container root, non-root UID, no capabilities, no-new-privileges, PID/RAM/CPU/timeout bounds, only workspace bind mount, Docker socket never passed, offline image selection; fails closed if Docker unavailable.
- Docker worker unit tests ensure constant CLI boundary. Tests mock the Docker invocation; they **do not** constitute a hostile-container penetration test.
- Owner-sensitive dry-run command details no longer printed verbatim to the console.
- Dashboard explicit-any ESLint errors repaired.
- Timed-out Docker worker attempts forced removal by unique name.

## Open release blockers
1. **HIGH — unresolved npm dev-tooling advisory.** Production dependency audit (`npm audit --omit=dev --audit-level=high`) passes on workflow 37812997279, but the full development-tooling audit fails. The one-time updater committed Next.js and eslint-config-next 16.3.8 plus a regenerated lockfile; that updater passed lint/build and reduced npm audit from one critical/eight high to five high. Remaining findings are in the `eslint-config-next -> @next/eslint-plugin-next -> fast-glob -> micromatch -> braces` development tooling chain. The upstream `braces` advisory has no patched release. Do not blindly downgrade eslint-config-next to v14 or report the audit clean. Recheck production-only vs development dependency exposure and document any risk acceptance.
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
