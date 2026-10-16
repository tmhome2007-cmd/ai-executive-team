# BE-61 — short-request intake prototype

Dated technical/research record; results and limitations apply to the versions described. Use [the README](../../README.md) for current status and planning.

12 October 2026. Owner authorized the focused next step after the actionable-schema experiment failed. Work remains on codex/sprint-7-actionable-schema, unmerged.

## User flow

Decisions now offers “Plan a first real-user test”. Enter a short request; optionally select up to five explicitly owner-reviewed project records or add a correction. The helper asks at most three material questions: contact response status, tool availability today, and owner minutes this week. Answers may be skipped. Confirmed supplied answers/limits are not asked again by the intake service; unanswered facts are never inferred from arbitrary source text.

Preview shows selected historical records and freshness as last recorded, not verified current. Current answers and corrections are separate. The owner reviews the assembled conditional brief, then confirms it to fill the existing structured decision form. No model, record write, outreach or action occurs in preview/confirmation. Start Decision remains a separate explicit step. Confirmation is review of input, not approval of the resulting decision or any action.

The helper currently supports first-user testing, not arbitrary decision domains. It uses deterministic domain rules, not an LLM claiming to infer priorities. Recent replies route to eligibility checking; prior silence routes to reviewing another known permitted conversation or a blocker; unknown status requires checking identity/date/status and keeps both branches conditional. Tool unavailability blocks invitations. Unknown time requires confirmation before an outreach plan. The conditions are proposed owner workflow instructions, not observed business facts or proof of model reasoning.

## Boundaries

Only explicitly selected owner_confirmed sources are retrieved; missing, disputed, unreviewed or oversized contexts fail. No private ignored business fixture is automatically imported into live company records. €0/private-team boundaries are system limits, not guessed preferences. Current answers are supplied through typed fields; historical prose cannot silently become a current answer. This prototype does not create a general persistent preference store or auto-select context across projects.

Preview hashes bind input, source versions/freshness and assembled text. Changed inputs or records require a new review. Edits in the helper invalidate a previously filled form; edited free-form task text returns to the existing manual path. Intake-backed generation rechecks the hash and exact task/source binding, requires structured strategy and no unrelated linked goal. Authentication and private error headers remain intact. Historical decisions remain readable and pending approval; legacy requests work unchanged.

The failed small OwnerPlan schema remains isolated. The dashboard feeds the confirmed brief to the existing structured meeting path; there is no automatic production rollout of that schema. A separate frozen local experiment compares the same three development contact variants using the unchanged experimental OwnerPlan with the new brief. Its results must be judged separately from deterministic routing and production UI tests.

## Verification plan and limits

Seven intake regressions cover skipped questions, known limits, changed routes, stale/unreviewed sources, authentication, source-version changes, confirmation tampering, no generation/write on mismatch and pending persistence on accepted generation. The production browser review covers short input, three quick questions, skip/default preview, changed answers, confirmation, invalidation and form population, without real inference. The remaining full audit and local model findings will be recorded below. No merge or general competence is claimed.

## Completed technical checks

Final audit on 0be2a90feec6169be1587aee1a89c946c204c638: 33 PASS, zero FAIL, one UPSTREAM. **353 backend tests with real Docker and zero skips, 150 foundation checks and 15 browser features passed.** The browser review now includes short intake, three questions, skipped answers, changed-contact conditions, confirmation/form population, invalidation after an edit, mobile and text/key safety. It intercepts the real API on disposable data and does not generate or mutate approvals. The initial audit invocation was refused because its branch allowlist stopped at Sprint 6; adding the authorized Sprint 7 prefix enabled the normal disposable audit without changing shared CI.

The usual four unpatched Chroma findings remain. Existing image-performance lint warning remains. No production clearance, remote CI result or Sprint 7 closure follows from this audit. [Exact evidence](../planning/be61-intake-verification.json).

## Frozen model findings

An explicitly selected historical fixture plus a **nine-word owner request** and typed answers produced three distinct conditional routes. The unchanged experimental OwnerPlan schema then ran three repetitions of each route on the installed local model, no repairs. Nine JSON responses completed, but **0/9 passed the full plan contract**: all outreach-labelled steps had null draft_message. The silent-case model also misclassified private conversation review as outreach. Three byte-identical unique answers represent the nine same-setting samples; these are development cases, not held-out or independent statistical evidence.

The unknown case now proposes checking availability and contact identity/date; the responsive case quotes the identity/recent-reply clarification and checks live-case eligibility; the silent case moves to reviewing existing conversations. First tool checks are present in all nine raw proposals. This is evidence that the supplied intake conditions influence the proposal, not proof the model independently reasoned out the routes. The routes were deliberately supplied by deterministic policy.

Further issues remain: unsupported assumptions of continued interest/live-case eligibility, missing actual safe-input/feedback instructions, and omitted drafts. Full-usefulness acceptance remains 0/9. The previous experiment stays intact; no failing sample was repaired, discarded, published as a valid plan or relabelled as success. Raw responses and individual review notes stay in ignored owner-only files; production retention of new experiment folders needs explicit coverage before integration.

**Decision: keep the branch unmerged.** The intake UI/API is ready for owner review of its bounded first-user scope. The failed OwnerPlan is still not enabled in the production API. The existing structured meeting remains the generation path for confirmed intake; the full three-role model path and owner usefulness are not certified by this isolated CEO comparison. Normal ./company startup configuration/recovery is still BE-62, not solved by a temporary demo. The existing disposable review launcher was updated locally to allow only stateless intake/confirmation in addition to private structured generation; it still blocks approval/execution and preserves original company data.

## Next implementation boundary

Separate plan routing/action classification from draft generation: a private review must not be marked outreach, and a proposed outreach step must produce a real unsent text artifact through a focused bounded drafting stage. Do not relax the missing-draft check. Freeze any revised candidate and rubric before rerunning these development cases; reserve new transfer cases for final assessment. General intent intake, persistent structured owner defaults, independent first-role proposals and owner end-to-end usefulness review remain unfinished Sprint 7 scope.

The earlier passing audit on ab017bd is retained. After model assessment the preview heading was made neutral (“for owner review”); the model comparison remains tied to its original frozen db579e2 assets and was not rerun or retuned. The final audit verifies the current label and UI/API implementation. Remote main was read-only reverified at 822712a; PR listing was unavailable because gh is not installed, so no global PR state is claimed. No merge was attempted.

## Subsequent delivery repair

The owner authorized the separated draft stage. [BE-59 delivery review](../research/BE59_DRAFT_DELIVERY_REPAIR.md) records 9/9 full-contract passes and actual drafts in all three responsive-contact samples, while six prerequisite-only plans remain private. Full usefulness still fails 0/9, so the candidate remains isolated and unmerged. This does not retrospectively change the frozen intake results or enable the experimental plan in the dashboard.
