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
2. **HIGH — vulnerable ChromaDB transitive dependency.** The fresh local pip-audit reports four advisory records (PYSEC-2026-311, PYSEC-2026-3813, PYSEC-2026-3814, PYSEC-2026-3815) against chromadb 1.5.9 installed via CrewAI, each with no fix version in the feed. Investigate compatible updates/constraints without bypassing CrewAI compatibility. `constraints-python312.txt` now pins the locally tested Python 3.12 resolution, including audit tooling. It is a constraints file, not a hash-verified lock; Linux CI installs the pinned application resolution successfully. CI now installs audit tools in the same constrained resolver transaction and runs `pip check`, preventing separate tool installs from upgrading CrewAI-incompatible tomli/tomli-w versions. Do not run a Chroma server or enable untrusted model loading while these findings remain unresolved.
3. **CLOSED for reviewed SQL sites — Bandit B608.** The 21 expressions are individually justified with code-adjacent B608 suppressions. Real SQLite malicious-status, signed table/column injection, and bound UPDATE-literal regressions pass. Bandit remains enabled and passes the medium/high gate; future dynamic SQL changes need renewed review.
4. **Workflow persistence.** Approved action dispatch now claims and finalizes a durable checkpoint keyed to the action ID, with results in the existing action record. Dry-run, crash/restart, no-replay and uncertain live-failure tests pass. Analysis, preparation, research and autonomous meetings still lack complete per-agent-step migration and resumable result storage. Startup recovery assumes one application instance; multiple concurrent server instances are not supported by this recovery design. Exactly-once external effects cannot be guaranteed by local SQLite alone; use provider idempotency keys and manual reconciliation.
5. **Docker runtime limitations.** CI now exercises a real Docker runtime and has passed the baseline network/filesystem confinement test. However, Docker daemon trust, mutable image tags, workspace writable mount, race conditions in preflight, and malicious code inside workspace remain concerns. Pin an image digest, use a dedicated worker VM and restrict Docker daemon access before live production deployment.
6. **Privacy.** Opt-in authenticated encrypted SQLite backups and exclusive, integrity-checked restore are implemented, along with scheduled backup and log retention configuration. Encryption is not enabled on the user’s live deployment by this audit. Live SQLite, logs, screenshots, sync history and audit data still need deployment encryption and owner-defined history/age retention. Existing plaintext copies are not removed.
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

## Local continuation evidence — 2026-10-08

Checkout: `chatgpt/foundation-hardening` cloned separately from the user's main
checkout. No production credentials or data copied; synced project sources and
main checkout remain unchanged.

- Python 3.12.14: compilation and `pip check` pass; 150/150 system checks pass
  using temporary CrewAI storage and test credentials, with Telegram disabled.
- 18 security tests pass, including real Docker isolation on Docker Desktop,
  host-path/symlink attempts, no-new-privileges, concurrent approval claims,
  durable execution crash/no-replay, signed-import SQL attacks and authenticated
  encrypted backup restore/tamper/wrong-key/retention tests.
- Local Ollama `llama3.1:latest` completes a short synthetic prompt with no
  external service. This is an inference smoke test, not an agent-meeting audit.
- ESLint passes with one existing `no-img-element` warning. Webpack production
  build passes. Default Turbopack build is blocked locally by worker port binding
  (`Operation not permitted`); initial sandbox run also could not fetch fonts.
- Production npm audit: zero vulnerabilities. Full npm audit: five high
  dependency-chain findings rooted in unpatched braces advisory
  GHSA-vfj7-8cjw-p6xm. No risky forced downgrade or blanket advisory ignore.
- pip-audit: four advisory records for ChromaDB 1.5.9, no published fix versions
  in the queried feed. These remain release blockers.
- Bandit medium/high gate passes with exactly 21 individually scoped B608
  dispositions; lower-severity findings are not claimed eliminated.

Final CI on these new changes is separate evidence and must still be checked.
The comprehensive release gate remains **NOT CLEARED**: dependency remediation,
universal workflow recovery, deployment encryption/history retention, full
meeting-to-preparation end-to-end adversarial tests and deployment confinement
remain unfinished. No merge or live business execution is authorized by this
record.

### CI follow-up on commit 4d08955

[Run 37821956157](https://github.com/tmhome2007-cmd/ai-executive-team/actions/runs/37821956157)
confirms 150/150 checks, 17 non-Docker unit tests (one opt-in test skipped in
that pass), the separate real Docker test, Bandit medium/high, dashboard lint,
default Turbopack production build and production npm audit. The jobs fail at
the expected dependency audits: five npm high chain findings and five Chroma
rows representing four unique advisory IDs (PYSEC-2026-311 appears twice).
The separate audit-tool installation also upgraded tomli/tomli-w incompatibly;
the follow-up CI change installs application and tools together under the same
constraints and adds `pip check`. That follow-up requires its own CI evidence.

The follow-up CI correction is committed locally but its push was rejected by
GitHub: the local credential lacks `workflow` scope. The published application
head remains `4d08955`. Publishing workflow changes requires an appropriately
authorized GitHub credential; never paste tokens into chat.
