# BE-43 — behavior review before refactoring

11 October 2026. Ready for review on codex/sprint-6-maintenance, based on Sprint 6 planning at 8948485. Scope is selected approval/preparation, recovery, storage and logging paths; this is not a complete independent security audit.

## Path and contract map

| Boundary | Reviewed path | Contract to preserve |
|---|---|---|
| Direction approval | main.py approve/reject routes → memory/database.py transition_decision_approval | Strategic approval is separate from preparation and action approval; in-progress/completed preparation fences rejection. |
| Preparation | main.py prepare_approved_decision → claim_decision_for_preparation → workflows/meeting.py | Approved direction and active goal required; one database claim wins. Original task is quantitative evidence; approved direction is not proof. |
| Proposal provenance | action_provenance_scope → propose_action/propose_resource_request → returned IDs | Decision ID, UUID and preparation phase must match persisted proposals; missing or orphan IDs fail preparation. |
| Nonexecuting resource compatibility | bounded retry → strict resource payload parsing → pending request | Printed actions never become executable proposals. Current resource fallback can materialize strictly validated pending requests after two meeting attempts; it does not grant access. Preserve this actual behavior despite the older contradictory inline comment. |
| Execution | workflows/action_control.py → approval seal and atomic claim → workflows/action_executor.py | Pending proposals cannot execute. Approval seal ties reviewed payload to execution; a stale or already claimed action does not dispatch again. |
| Interrupted effects | workflow_step_checkpoints and recover_interrupted_actions | Ambiguous external effects remain inconclusive and require reconciliation; restart does not replay them. |
| Dashboard review | executive-dashboard/app/page.tsx handleDecisionReview/handlePrepareDecision and action controls | Separate explicit review/prepare/approve/execute interactions. The browser is advisory; the API/database enforce authority. |
| Private responses | main.py log_requests middleware | Authentication, validation, conflicts and provider failures retain no-store and nosniff headers. |
| Logs and external notifications | logging_config.py, main.py preparation errors, notifications/telegram_bot.py | Owner-only rotating log files; notification transport suppresses business details by default. Exceptions must not expose private provider payloads. |

## Findings and corrections

Nine new SQLite/API tests cover auth and pending rejection, inactive goals, actual proposal provenance, pending action authority, missing/orphan proposals, printed-action refusal, bounded resource compatibility, concurrent preparation, retry after failure and notification errors. All generation/notification paths in these tests are mocked; no lifespan, company records or actual agents are started.

The initial test run exposed raw provider exception text in both 400 and 502 preparation responses. Corrected them to actionable fixed messages and sanitized event codes with decision IDs and exception type. Completion-notification failure also logs safe context without reversing successful preparation. Failed and successful verification evidence is retained separately. One initial fixture error attempted to link a draft goal, which the existing database correctly rejected; corrected the fixture to pause an initially active goal before preparation.

## Remaining review limits

This review reads storage and dashboard source around these boundaries, and exercises real disposable SQLite plus in-process HTTP. It does not certify all database migrations/sync, every dashboard panel or all logging call sites. BE-46 audits executor handlers; BE-45 must preserve the preparation contracts, and BE-53 performs the complete integration/security/browser audit. Existing process-wide provenance relies on serialized meetings. Goal changes during generation and commit-failure recovery warrant further fault-injection in extraction review; this report does not claim they were comprehensively tested.

Raw-error logging and response detail in other routes remain separate follow-up review areas. No company database, credentials or live board were changed. Owner acceptance and a future authorized merge are pending; this item is not Done.

Verification: 30 targeted tests passed. The subsequent complete backend run passed 303 tests with real Docker and zero skips; foundation passed 150/150. The full Sprint 6 audit and owner acceptance remain pending.
