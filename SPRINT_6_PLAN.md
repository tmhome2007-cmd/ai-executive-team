# Sprint 6 — maintenance and honest evaluation

Planned 11 October 2026 at the owner’s request. The owner subsequently authorized implementation. BE-43–52 work is ready for review; the final local audit passed, with CI approval, owner usefulness/acceptance and merge still pending; see [current progress](docs/planning/sprint-6-progress.md). The same working folder was renamed to **AI Executive Team V2CHAT**. The older AI Executive Team folder remains separate.

## Goal

Make the project easier to maintain and assess whether the executives produce useful, grounded decisions on cases we have not tuned against. Freeze unrelated feature expansion for this sprint.

Planning inputs: [verified Claude feedback](CLAUDE_FEEDBACK_REVIEW.md), [Sprint 5 closure](SPRINT_5_CLOSURE.md), and the owner’s request. Sprint 5 is merged into main through PRs #50 and #51; the planning baseline is main `822712a671095803ed6fa46fd8e832811d2dbc60`. The local documentation tidies and feedback review at `fb6e6cb` are prerequisites on this planning branch, not a new merged implementation.

## Backlog and order

Start BE-43 and BE-44. Freeze the independent evaluation protocol before adapting quality checks or meeting prompts. Extract one backend domain at a time. Show the decision brief early, then complete the real-job assessment, final audit and owner review.

| ID | Priority | Item | State | Dependencies |
|---|---|---|---|---|
| BE-43 | high | Protect behavior before refactoring | review | None |
| BE-44 | high | Organize tests and safe test commands | review | None |
| BE-45 | high | Extract decision preparation and thin API routes | review | BE-43, BE-44 |
| BE-46 | high | Make executor failures observable | review | BE-43 |
| BE-47 | high | Freeze independent evaluation cases and protocol | review | BE-44 |
| BE-48 | high | Generalize evidence quality checks | review | BE-43, BE-47 |
| BE-49 | high | Use structured output in one meeting path | review | BE-43, BE-47, BE-48 |
| BE-50 | medium | Preserve disagreement in the decision brief | review | BE-49 |
| BE-51 | medium | Simplify documentation and the code catalog | review | BE-44, BE-45 |
| BE-52 | high | Evaluate one real project decision | review | BE-47, BE-48, BE-49, BE-50 |
| BE-53 | high | Complete integration, privacy and security audit | blocked | BE-43, BE-44, BE-45, BE-46, BE-47, BE-48, BE-49, BE-50, BE-51, BE-52 |
| BE-54 | medium | Owner review, retrospective and Sprint 6 closure | review | BE-53 |

The owner supplied BE-52 inputs and a follow-up on 11 October. They are retained in ignored private storage; evaluation awaits BE-47–50. Historical facts and remaining unknowns must stay explicit. The other maintenance items can progress independently according to their dependencies. BE-53 assesses selected scope; a blocked real-job item may be explicitly deferred before closure, but cannot be marked Done. No fixed delivery date or velocity has been agreed.

## Acceptance criteria

### BE-43 · Protect behavior before refactoring

Review the database, dashboard and logging paths omitted from Claude’s ZIP. Map decision preparation and recovery; add meaningful characterization tests for separate approvals, stale versions, source provenance, private headers, atomic claims and uncertain outcomes. Use disposable records and report remaining review gaps.

### BE-44 · Organize tests and safe test commands

Consolidate backend regression tests under tests/ and document one supported command. Move side-effecting root demos to explicit opt-in scripts/manual_checks with guarded entry points; automatic discovery must not invoke real models, web, Telegram or company mutations. Preserve JavaScript/vendor tests and update packaging, test counts and CI paths deliberately. Demonstrate discovery and clean-copy checks.

### BE-45 · Extract decision preparation and thin API routes

Extract the 524-line prepare_approved_decision orchestration into an owning service/workflow, then mount thin routes for that domain. Preserve endpoint URLs, request/response contracts, authentication, transactions, private headers, approval boundaries and recovery. Keep test patch seams deliberate; affected characterization tests pass. Do not merely relocate the long function or rewrite all routers at once.

### BE-46 · Make executor failures observable

Classify all 24 broad exception handlers by expected rejection, cleanup/rethrow, persisted uncertainty, notification fallback or swallowed failure. Remove unused helpers only after checking references. Add sanitized event codes, IDs and error types for reachable gaps; never log secrets, raw prompts, command payloads or credential-bearing URLs. Inject notification, checkpoint and persistence failures; uncertain outcomes still require reconciliation and cannot replay automatically.

### BE-47 · Freeze independent evaluation cases and protocol

Separate development cases from new held-out scenarios. Freeze case/rubric hashes, model digest, effective settings, prompt version and assessment protocol before generation or tuning. Cover missing facts, conflicting evidence, unsupported consent/numbers, unknown controls and cross-domain tasks. Distinguish schema validity, grounding, unsupported claims and human usefulness; retain failures, errors and denominators. A case used for repair becomes development data and cannot remain an untouched test.

### BE-48 · Generalize evidence quality checks

Replace scenario field-name assumptions in the shared checker with explicit evidence contracts and source-linked checks. Develop changes against the development split; use held-out results only for declared final assessment. Version the new rubric/checker separately; preserve original 24/30 and 30/30 fixtures and raw reports. Add false-positive and false-negative cases; changed measurements must not be presented as directly comparable scores.

### BE-49 · Use structured output in one meeting path

Adopt schema-constrained typed output for one representative existing meeting/decision path, including source-backed claims, unknowns, role positions and disagreement. Verify supported local provider behavior and fail closed on invalid output, fabricated references or unavailable schema support. Bound repair attempts, preserve failed samples and legacy reads. Grounding checks, owner approvals and personalities remain intact. Compare against the declared baseline with fixed inputs/settings and a separately labelled new schema prompt.

### BE-50 · Preserve disagreement in the decision brief

Render a concise one-page brief from actual role contributions: recommendation, supporting roles, objections, evidence, unknowns and next owner decision. Conflicting inputs retain attribution and unresolved disagreement; unanimous inputs do not gain fabricated dissent. Verify storage/API and affected dashboard behavior, including empty and error states. Ask the owner to judge whether the brief is understandable and useful.

### BE-51 · Simplify documentation and the code catalog

Archive closed sprint narratives with a closure index and working links. Keep active setup, authority/privacy contracts, fixtures and verification manifests at required operational paths. Make the generated catalog compact and reproducible with scoped refresh/check commands. Verify links and generation without editing immutable audit evidence or erasing failures; retain the existing generated-artifact retention policy.

### BE-52 · Evaluate one real project decision

Freeze an owner-supplied brief, permitted facts, intended reader, exact unknowns and decision rubric before running the team. Use the supplied primary decision; any separate later question stays deferred. Private business inputs stay outside Git and remote transmission. Record whether output changes the owner’s decision and why. Add a controlled same-input comparison when a suitable second local model is already available; keep prompt/rubric/settings fixed where possible and disclose unavoidable differences. If no second model is available, record the comparison as deferred rather than inventing results. No automatic downloads, cloud transmission or spending.

### BE-53 · Complete integration, privacy and security audit

Audit the final selected implementation with disposable backend/database, real Docker, foundation, frontend/browser, recovery, privacy and retention checks. Ensure extracted API/service modules are included in local and CI scans; repository workflow permissions are a dependency for remote workflow edits. Fix actionable project regressions, retain failed evidence and report exact commits/counts/skips. Recheck dependency advisories without promising an upstream fix. An unresolved release gate remains explicitly failed; no production clearance.

### BE-54 · Owner review, retrospective and Sprint 6 closure

Present representative outputs and concise navigation instructions with supplied test data. Record actual scope, usefulness feedback, failures, deferred work and improvement priorities. Mark implementation Done only after documented owner acceptance and authorized actual merge. Keep blocked or deferred items visible and distinguish maintenance success, model quality and security release readiness. No invented velocity, dates, earnings or general competence.

## Real-job input needed later

For BE-52, supply one question (for example, “Which Reinstatly functions should be free versus paid?”), the intended reader, approved product facts, available usage/cost evidence, relevant constraints and what decision the output must help make. Missing evidence stays unknown. We do not invent pricing, users or revenue and do not search unrelated databases. Technical maintenance does not wait for these inputs.

## Model experiments and deferred ideas

First measure the current local model. Where a suitable second local model is already installed, compare the same permitted inputs and rubric and record model identities and effective settings. Multiple changed variables do not establish that model capacity caused a score change. Schema validity is assessed separately from factual correctness and usefulness.

Per-role cloud model routing is deferred pending a separate provider, privacy, transmission-consent and cost decision. ALLOW_REMOTE_LLM alone does not supply those decisions. The budget and permitted loss remain €0. Portfolio recording, architecture presentation, office expansion and other new product features are later optional work; they are not committed Sprint 6 deliverables.

## Working and review agreements

- Preserve existing credentials, company databases, personalities, approval gates, sandbox defaults and source provenance. Board status never grants execution authority.
- Use disposable data for verification. Do not import this backlog into a live database without choosing the existing Development board and configuration; checked-in cards are currently the authoritative planning artifact.
- Keep backend regression tests automatic and manual scripts opt-in. Keep JavaScript tests appropriate to their ecosystem; consistent commands matter more than putting every test file in one directory.
- Characterize relevant behavior before extraction; run meaningful affected checks after changes and the complete audit at the end. Do not add tests that only mirror moved code.
- Preserve old evaluation reports and failed evidence. Lock a new evaluation split before tuning; if its results drive repairs, disclose that contamination and use fresh cases for subsequent untouched assessment.
- Keep coherent review batches. Owner acceptance and a new explicit merge instruction are required before implementation cards become Done. This planning request does not authorize implementation merges.
- Generated artifacts retain the existing 30-day policy. Durable approval and review provenance remains intact.

## Security and scope limits

The four recorded Chroma advisories (PYSEC-2026-311, PYSEC-2026-3813, PYSEC-2026-3814, PYSEC-2026-3815) remain visible and must be rechecked during BE-53. No fix or clean release gate is promised. Claude omitted memory/, the dashboard and logs; BE-43 addresses those review gaps instead of treating the feedback as a full clearance.

No paid services, cloud fallback, customer contact, publishing, automatic model downloads or generated-code execution is enabled by this plan.

Matching backlog: [sprint-6-cards.json](docs/planning/sprint-6-cards.json). No live board status or Company execution records were changed.
