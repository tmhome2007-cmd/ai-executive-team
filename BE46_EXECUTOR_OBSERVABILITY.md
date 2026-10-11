# BE-46 — executor failure observability

11 October 2026. Implementation verified with targeted faults; full integration rerun pending.

## Handler review

The original 24 broad exception handlers were classified before editing:

| Category | Count | Treatment |
|---|---|---|
| Notification fallback | 16 | Replace raw exception prints and the bare-pass fallback with fixed safe events. Business operation results remain unchanged when notification fails. |
| Persisted failure or uncertainty | 5 | Log safe context before persistence or cleanup, preserving existing failure/uncertainty transitions. |
| Expected URL rejection | 1 | Keep the bounded rejection result; avoid logging URL credentials. |
| File descriptor cleanup and rethrow | 1 | Preserve cleanup and propagation; it does not swallow the original failure. |
| Unused optional host resource helper | 1 | No callers exist. Remove it and its platform import; the active Docker worker enforces runtime limits. |

The helper logs only fixed event codes, action IDs and exception type. Prompts, commands, raw errors and credential-bearing URLs are excluded. The logging module documentation now correctly describes owner-only files rather than claiming a global secret-redaction filter. Existing private action outcomes retain their detailed records.

The foundation resource check previously passed by finding RLIMIT/preexec_fn strings in the unused helper. It now follows the active worker and requires its fixed memory=256m, cpus=1 and pids-limit=64 flags. The container argument test asserts those security limits as well as offline/nonroot confinement.

## Fault verification

Seven tests cover shell/file/browser dry-run notification errors, the blocked-shell fallback, checkpoint failure before dispatch, an effect-handler exception, transient result-persistence failure and persistent storage failure. Synthetic secrets never enter captured events. No live generated command or real browser navigation is performed by these new tests.

A persistent storage failure still propagates rather than claiming a recorded outcome. Its already-claimed action and running step reject replay; after storage recovers, existing restart reconciliation records the outcome as inconclusive. No automatic replay, renewed approval or silent success is introduced.

An initial fixture tried to grant a CTO browser capability and was correctly rejected. The fixture now uses the existing authorized COO role; the role policy was preserved. Initial failed evidence remains alongside passing verification.

Owner acceptance, merge and final Sprint 6 closure remain pending.
