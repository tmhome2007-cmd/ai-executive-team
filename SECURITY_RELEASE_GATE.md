# Security release gate — 2026-10-08

**Status: NOT CLEARED. Do not merge this branch into main or enable production/live execution based on this audit alone.**

## Verified on GitHub Actions
- Python syntax compilation passes.
- Frontend ESLint and production build pass on hardening commits after typing fixes.
- Docker-worker unit tests pass on CI commit `bbb180e`.
- New CI runs now attempt dependency audits even when lint/Bandit fails.
- Full-system regression verification passed **150/150 checks**, alongside all 12 isolated/unit security tests and the live Docker boundary test (workflow 37818629298).

## Remediations committed
- Centralized authority/approval bindings, imported-sync authority restrictions, fail-closed network/file controls, private artifact defaults: see `FOUNDATION_AUDIT.md`.
- Live raw-shell execution replaced by a Docker CLI invocation with fixed flags: network disabled, read-only container root, non-root UID, no capabilities, no-new-privileges, PID/RAM/CPU/timeout bounds, only workspace bind mount, Docker socket never passed, offline image selection; fails closed if Docker unavailable.
- Docker worker unit tests validate fixed CLI boundaries. Real Docker CI integration tests **passed**, including pinned image digest (workflow 37818443981), network disabled, non-root UID, read-only root and host paths absent. This is stronger evidence, not proof against kernel/daemon exploits.
- Owner-sensitive dry-run command details no longer printed verbatim to the console.
- Dashboard explicit-any ESLint errors repaired.
- Timed-out Docker worker attempts forced removal by unique name.
- The bind-mount preflight rejects socket/device/FIFO entries and aborts if traversal fails or exceeds a fixed limit. This mitigates accidentally exposing host Unix sockets in the workspace but is not race-free if untrusted processes can change the workspace concurrently.
- Timed-out action outcomes now become **inconclusive**, with mandatory manual reconciliation before any retry; the system verifier previously passed **150/150** on this protection.
- Two-worker SQLite approval-claim concurrency test added.
- Persistent step claim ledger and crash reconciliation primitive added and initialized at backend startup; it is not yet integrated with every workflow step.
- GitHub Actions use pinned immutable SHAs, verified against upstream release-tag commit references.
- SQLite backups now reject zero/negative retention counts and symlink backup directories. An on-disk restore/integrity regression test and SQL status injection tests **passed** (CI run 37818629298; 12 unit tests plus 150/150 full-system checks).

## Open release blockers
1. **HIGH — unresolved npm dev-tooling advisory.** Production dependency audit (`npm audit --omit=dev --audit-level=high`) passes on workflow 37812997279, but the full development-tooling audit fails. The one-time updater committed Next.js and eslint-config-next 16.3.8 plus a regenerated lockfile; that updater passed lint/build and reduced npm audit from one critical/eight high to five high. Remaining findings are in the `eslint-config-next -> @next/eslint-plugin-next -> fast-glob -> micromatch -> braces` development tooling chain. The upstream `braces` advisory has no patched release. Do not blindly downgrade eslint-config-next to v14 or report the audit clean. Recheck production-only vs development dependency exposure and document any risk acceptance.
2. **HIGH — vulnerable ChromaDB transitive dependency.** pip-audit reports five advisories against chromadb 1.5.9 installed via CrewAI. Investigate compatible updates/constraints without bypassing CrewAI compatibility. A lockfile/constraints mechanism is recommended.
3. **MEDIUM — dynamic SQL Bandit B608 warnings.** Current 21 findings include parameterized placeholders and code-generated column lists; validate each dynamic identifier against fixed whitelists. Suppress only individually justified false positives, never blanket-skip B608.
4. **Workflow persistence.** A transactional step checkpoint ledger now exists and is initialized/reconciled on startup, but existing long-running agent workflows have not been migrated to use per-step keys, stable result identifiers, and explicit recovery decisions. Exactly-once external effects cannot be guaranteed by local SQLite alone; use provider idempotency keys and manual reconciliation.
5. **Docker runtime limitations.** CI now exercises a real Docker runtime and has passed the baseline network/filesystem confinement test. However, Docker daemon trust, mutable image tags, workspace writable mount, race conditions in preflight, and malicious code inside workspace remain concerns. Pin an image digest, use a dedicated worker VM and restrict Docker daemon access before live production deployment.
6. **Privacy.** Long-lived SQLite, backups, sync history and audit data are not encrypted at rest at the application layer. Add retention configuration, full-disk encryption guidance and opt-in encrypted exports.
7. **External transports.** Remote LLM and Telegram opt-ins transmit context to external services. Maintain disabled-by-default and verify logs contain no sensitive data.
8. **End-to-end testing.** Exercise decision -> owner approval -> preparation -> execution -> failure -> restart -> idempotent resume, plus tampered imports, adversarial URLs, symlinks, and concurrent approval requests on a disposable machine.
9. **GitHub Actions supply chain.** Security workflow actions are pinned to inspected upstream commit SHAs. Continue rotating these through reviewed dependency update PRs.

## Gate criteria
- GitHub Actions: compilation, verification, isolated-executor unit tests, Bandit, pip-audit, npm ci/lint/build/audit all green.
- No unresolved critical/high vulnerabilities or undocumented accepted risk.
- Real Docker baseline confinement test passes in CI; manual adversarial sandbox escape, SSRF, concurrent approval and crash/restart tests still required on deployment target.
- No accidental calls to real Telegram or external LLM during verification.
- Database migration and backup/restore tested on copies.
- Explicit sign-off before merging `main`.

This file is an **audit record, not a claim that the release gate passed**.
