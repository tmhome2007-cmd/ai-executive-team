# BE-61 — short-request intake prototype

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
