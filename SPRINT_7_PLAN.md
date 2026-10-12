# Sprint 7 — useful decisions from short requests

Planned 12 October 2026 at the owner’s request. **Planning only: implementation and internet/GitHub research have not started.** Work stays in AI Executive Team V2CHAT. The original folder and team.zip remain untouched.

## Goal

Let the owner write a short, natural request and receive a grounded, actionable plan with the right human actor, necessary drafts, realistic effort and meaningful stopping conditions. Detailed internal contracts should not become the owner’s writing burden.

## Evidence and baseline

The Sprint 6 owner run generated and saved a pending decision, but omitted requested steps and the message draft, proposed outreach by AI roles, and used a stopping count without a time window. The owner also found the supplied task description too long for normal use. These are observed findings; whether omissions originate in generation, schema or rendering must be traced before changes. Claude’s supplied review is an input, not a verified description of every code path. Private source text, raw model responses and contact details remain outside Git.

The temporary review launcher also had a macOS alias-path rejection and a short proxy timeout; both were corrected locally. The latter run completed and saved despite a browser error. These launcher fixes are not proof of normal startup acceptance.

Local planning base is 180e0fa on codex/sprint-6-maintenance; this plan is on codex/sprint-7-plan. Sprint 6 acceptance, active-CI dependency and merge remain pending. Local main is 822712a; remote Git/PR state has not been refreshed for this planning task and must be verified before integration. No fixed deadline or velocity is agreed.

## Backlog and order

Diagnose the real failure, then freeze the evaluation before tuning. Discuss the research scope with the owner before searching. Use research to inform implementation choices, not as an assumed solution. Deliver complete plans and sensitivity to facts before expanding the short-request flow. Test normal startup early, then evaluate and audit.

| ID | Priority | Item | State | Depends on |
|---|---|---|---|---|
| BE-55 | high | Trace owner-test failures from raw output to saved brief | ready | None |
| BE-56 | high | Freeze usefulness evaluation and untouched transfer cases | backlog | BE-55 |
| BE-57 | medium | Review reusable GitHub projects and primary documentation | backlog | None |
| BE-58 | high | Make clarifications and freshness affect recommendations | backlog | BE-55, BE-56 |
| BE-59 | high | Produce a complete actionable owner plan | backlog | BE-55, BE-56 |
| BE-60 | high | Separate independent proposals from attributed critique | backlog | BE-56, BE-59 |
| BE-61 | high | Handle short requests with reviewed context and few questions | backlog | BE-58, BE-59 |
| BE-62 | high | Make normal startup and long-running decision review reliable | backlog | BE-55 |
| BE-63 | high | Run final usefulness and owner end-to-end assessment | backlog | BE-56, BE-58, BE-59, BE-60, BE-61, BE-62 |
| BE-64 | high | Audit integration, privacy and existing release dependencies | backlog | BE-58, BE-59, BE-60, BE-61, BE-62, BE-63 |
| BE-65 | medium | Owner review, retrospective and closure | backlog | BE-63, BE-64 |

BE-57 is deliberately pending the next owner discussion. Research is not an implementation blocker if no suitable reuse is found; document the decision. Future source adoption must be explicit and scoped. Sprint 7 planning does not accept, merge or erase Sprint 6 failures.

## Stories and acceptance checks

### BE-55 · Trace owner-test failures from raw output to saved brief

Inspect the exact structured path, raw role samples, schema, renderer and saved decision from the owner test without regeneration. Map each requested deliverable to generated, stored and rendered fields. Verify prior-context visibility and critique/revision behavior from this path rather than assuming the legacy meeting code applies. Record observed omissions, incorrect proposed actor, unsupported stop rule, duplicate wording and historical-source handling separately from hypotheses. Preserve original inputs/results privately with hashes; inspect launcher path and timeout failures separately from model quality.

### BE-56 · Freeze usefulness evaluation and untouched transfer cases

Freeze a rubric, model identity/settings, protocol and sample counts before implementation tuning. Treat the owner example and contact variants as development/regression data. Reserve at least two newly authored transfer tasks for final assessment; disclose author exposure and do not call them blind. Assess structure, grounding, authority, responsiveness to changed facts and owner usefulness separately. Freeze five runs for the independent-proposal comparison and explain deterministic-setting limits. Retain failed, repaired, incomplete and error samples; any assessment case used for a fix becomes development data.

### BE-57 · Review reusable GitHub projects and primary documentation

Research only after the planned owner discussion. Compare a small shortlist against diagnosed problems and the frozen rubric: structured plans, bounded clarification, independent proposals and evaluation. Record exact repository/version, license, maintenance evidence, local-provider compatibility, dependencies, privacy/cost implications and concrete reuse scope. Prefer primary documentation and source; disclose uncertainties. Recommend adopt, adapt or reject with reasons. Search generic problem descriptions without transmitting private briefs. No installation, copied code, external inference or dependency adoption follows automatically from a research recommendation.

### BE-58 · Make clarifications and freshness affect recommendations

Represent owner clarifications with attributable evidence and preserve freshness/conflicts. Exercise three development variants: unknown relationship as originally supplied; distinct contact with recent reply; same contact already silent after an offer. Recent and silent variants must change the recommendation or explicit conditions and rationale; silence must be represented as risk rather than assumed interest. Unknown identity/date stays unknown. Explain why the chosen path beats relevant alternatives without fabricated response rates or success probabilities. Do not require the same recommendation to change when the changed fact is immaterial.

### BE-59 · Produce a complete actionable owner plan

Add typed steps with actors, durations, prerequisites, deliverables and conditional paths where needed. Outreach recommendations require an unsent draft, an eligibility check and a stop condition with a bounded time window. A multi-step owner task has at least two meaningful steps; estimated effort sums to the confirmed owner limit or is explicitly blocked. Require a current tool-availability check before inviting use when availability is unknown; the check remains a proposed owner step. Every real-world action is assigned to the human owner, never an AI executive. Drafting is distinct from sending. Required deliverables survive schema validation, storage/API and rendering; no empty filler fields or invented approvals. Schema completeness and semantic usefulness have separate checks.

### BE-60 · Separate independent proposals from attributed critique

Generate first proposals without access to other first proposals, then provide bounded context for actual critique and synthesis. Preserve canonical identities and attribution; no tools or authority expansion. Compare five frozen runs before/after using the same permitted inputs and settings where possible. Meaningful alternatives or evidence-based explanations of convergence must be visible; do not force diversity or invent objections. A trailing period, case or whitespace difference is normalized for wording matches without treating different meanings as agreement. Bound calls, context size and repairs, retain failures, and disclose latency/cost implications.

### BE-61 · Handle short requests with reviewed context and few questions

A short natural request can start the workflow without a manually authored long prompt. Show relevant reviewed stored facts as last recorded, not verified; disclose which context is used and allow correction. Reuse explicitly confirmed stable limits instead of asking again, while surfacing freshness and scope. Ask at most three decision-changing questions with quick answers and a skip path. Do not invent a factual plan when essential context is missing: produce a bounded conditional plan or explicit blocker. The owner can review the assembled brief before generation. Changed answers to selected questions must affect the relevant plan conditions; ask no questions whose answers cannot change the plan. Do not assume stored data exists in a fresh installation or retrieve unrelated company/private context.

### BE-62 · Make normal startup and long-running decision review reliable

Exercise ./company doctor, ./company start and ./company key in an explicitly isolated review installation with disposable data and owner-controlled local configuration. Preserve existing credentials/database; do not silently copy original company data or weaken path/approval guards. Verify long generation, interrupted browser connections, errors, refresh and saved-history recovery. A network timeout must not imply the team failed or invite duplicate submissions: retain request identity and provide an inspectable status/recovery route. Model validation failures have useful safe guidance without exposing raw private samples. Owner instructions use the normal launcher and own browser; no temporary /private/tmp script is the product entry point. Verify effective settings, local provider and scheduler behavior rather than assuming sandbox disables scheduling.

### BE-63 · Run final usefulness and owner end-to-end assessment

Run the frozen development comparisons and separately the reserved transfer assessment on the final candidate. Report denominators, first attempts, repairs, errors, latency, model identities and owner usefulness separately; no blanket competence percentage. Evaluate changed-fact sensitivity and short-request intake, complete plans and actor constraints. The owner uses normal terminal/browser startup, enters a short request, answers or skips questions, reviews actual team output and checks history after refresh. Record whether they understand and would use the next step, with reasons; an analyst rewrite never replaces a failed team answer or counts as owner acceptance.

### BE-64 · Audit integration, privacy and existing release dependencies

Run appropriate targeted checks and a complete final audit on the exact implementation with disposable data: backend/API/database, production browser, recovery, approvals, raw-sample retention, evidence provenance and local-provider boundaries. Preserve failures and report exact commit/counts/skips. Carry Sprint 6 active-CI approval/credential dependency and known Chroma findings explicitly; do not claim them resolved or edit active shared CI without authorization. Investigate any adopted dependency only after a specific reuse decision, with license/security/compatibility review. No deployment clearance follows from a local pass.

### BE-65 · Owner review, retrospective and closure

Provide concise own-terminal/browser instructions and short test inputs, actual outputs, remaining limitations and a reviewable PR scope. Record owner acceptance separately from technical success. No Done state or merge until owner acceptance and authorized actual merge; reconcile Sprint 6 pending work before deciding stacked versus separate delivery. Archive only closed narratives. Record research decisions, model limits and deferred work honestly; no invented customer outcome, delivery date or velocity.

## Boundaries and deferred work

- €0 spend; no publishing, customer contact, remote inference, model downloads or launch actions are authorized by this plan.
- Preserve owner approvals, sandbox defaults, role personalities, credentials, databases and private sample retention. Conditional plans and stored defaults never grant execution authority.
- Keep product-facing instructions simple; retain evidence and internal validation details in review/provenance views.
- Pricing decisions, office expansion, portfolio production and unrelated feature work remain deferred.
- The pending CI approval and upstream security findings remain separate from output usefulness. No forced objections, manufactured alternatives or keyword-only usefulness scores.

## Planning artifacts

Matching backlog: [sprint-7-cards.json](docs/planning/sprint-7-cards.json). Status: [sprint-7-progress.md](docs/planning/sprint-7-progress.md). Previous work: [Sprint 6 review](SPRINT_6_REVIEW.md).
