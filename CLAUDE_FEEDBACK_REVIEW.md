# Claude feedback — verification and maintenance proposal

11 October 2026. Feedback received after owner acceptance and Sprint 5 merge.
Checked against current main baseline `822712a671095803ed6fa46fd8e832811d2dbc60`.
This review and two documentation tidies are on `codex/claude-feedback-review` in
AI Executive Team Sprint 5. It does not start another sprint, enable cloud models,
change authority or grant permission to merge subsequent implementation.

## Confirmed findings and corrections

| Feedback | Current evidence | Assessment |
|---|---|---|
| Large approval-preparation route | `main.py` lines 1161–1684: 524 lines | Confirmed. Extract orchestration as well as routers; moving the same function to another file alone does not reduce complexity. |
| Scenario-specific shared checker | `workflows/output_quality.py` names original reproduction steps, reminder due time, build and observation channel | Confirmed evaluation-coupling risk. Keep the original benchmark/checker snapshot; introduce general evidence checks and version new evaluations separately. |
| No separate held-out evaluation | The recorded 24/30 and 30/30 comparison uses the same frozen fixtures | Confirmed gap in that measurement. A new scenario transfer is useful evidence, but it is not an untouched held-out suite after prompt tuning on its failures. |
| Eleven executives versus ten in documentation | The agent dictionary has eleven roles; its docstring and dictionary comment said ten | Corrected locally to eleven. |
| Repeated max_iter explanation | Eleven identical inline comments | Centralized the explanation while retaining every max_iter=5 value and all roles/tools/personalities. Executable AST is unchanged. |
| Twenty-four broad exception handlers | `workflows/action_executor.py` contains 24 | Confirmed count, not 24 swallowed errors. Many print errors; one closes a descriptor and re-raises; checkpoint handlers persist uncertain outcomes. Two bare-pass handlers warrant distinction: an unused resource-limit helper and a notification fallback. Audit reachable failures and log safe context, not raw exceptions indiscriminately. |
| One model for executive roles | `agents/executive_agents.py` constructs a shared configured local LLM | Confirmed. It does not by itself prove that model capacity is the dominant failure cause. |
| All roles limited to 4096 context | The explicit num_ctx=4096 setting is in `workflows/quality_benchmark.py` | Not established for every workflow. Executive LLM construction does not set that option. Inspect effective local runtime settings before making a global claim. |
| Meetings/discussions mostly text contracts | Their published text is checked by parsing/regex; private-work schemas are more explicit | Confirmed useful migration candidate. Valid schema output still needs grounding and approval checks; structure does not prove factual truth. |
| Synthesis loses disagreement | Meeting and discussion prompts already request material/unresolved disagreements | Outcome quality is unproven. Test attribution and preservation using actual conflicting inputs before concluding the contract has no dissent support. |
| Generated catalog is large | Current CODE_CATALOG.md is 75,174 bytes | Confirmed maintenance concern. Compact navigation and automatic checks are candidates; deleting the index does not improve runtime correctness. |

## Recommended maintenance and evaluation order

1. **Characterize authorization and recovery before extraction.** Cover the approved
   decision preparation route's status/version transitions, action provenance,
   separate owner approvals, privacy headers, atomic claims and reconciliation.
   Include the database layer that Claude's ZIP did not contain. Existing tests
   are evidence to preserve, not a reason to assume unreviewed storage is flawless.
2. **Unify test discovery and commands safely.** Backend regression tests belong
   in tests/. Root test_config.py, test_crew.py and test_cso_tool.py are executable
   manual/demo scripts; some initialize records or invoke model/web/Telegram paths.
   Give them explicit opt-in entry points under scripts/manual_checks rather than
   moving them directly into automatic discovery. Keep JavaScript/package self-tests
   in appropriate frontend/vendor locations, or update packaging and clean-copy CI
   deliberately if moving them. Verify discovery itself performs no real actions.
3. **Extract one backend domain at a time.** Move preparation orchestration to an
   owning workflow/service and mount thin authenticated routes. Preserve request
   models, endpoint URLs, transactional behavior, private headers and test patch
   seams. Run affected tests plus the complete disposable audit before review.
4. **Make operational failures observable.** Classify every broad executor handler
   as expected rejection, cleanup/rethrow, persisted failure/uncertainty, notification
   fallback or unexpected swallowed failure. Log fixed event codes, action IDs and
   sanitized error types where appropriate; exclude secrets, raw prompts, command
   payloads and external URL credentials. Fault-inject persistence/notification
   failures and verify reconciliation remains required without replay.
5. **Add a separate locked evaluation split.** Freeze new scenarios, rubrics,
   generation settings and model digest before generating results. Keep them out
   of prompt iteration; a case used to repair prompts becomes development data.
   Separate JSON/schema validity, factual accuracy, unsupported claims and reader
   usefulness. Preserve every result and label human judgments; do not rewrite the
   existing 24/30 or 30/30 measurement or silently compare changed checkers.
6. **Adopt structured output in one representative meeting path.** Use typed
   claims with source references, unknowns, role positions and actual attributed
   disagreements. Reject invalid or fabricated references; bounded repair and
   owner review still apply. Measure against the locked evaluation rather than
   assuming that schema validity removes semantic failure.
7. **Reduce documentation clutter with an index and scoped archive.** Archive
   completed narrative reports after updating links and retaining a closure index.
   Keep active authority/privacy/setup instructions and machine-readable fixtures,
   contracts and verification manifests where code/tests expect them. Preserve
   failed evidence and the generated company artifact retention policy.

## Real-work and model experiments need defined inputs

A real project question is a better usefulness test than another synthetic score,
provided its approved facts, intended reader, expected decision and exact unknowns
are specified. The Reinstatly free-versus-paid question is a candidate; this chat
has not supplied the pricing, users, costs, usage or project documents needed to
answer it. Do not invent those facts or search unrelated company databases.

First compare outputs with the same approved inputs and assessment rubric. Changing
model, prompt, context budget and checker together would not isolate the cause.
Another installed local model can be a comparison candidate after identifying its
runtime requirements. Cloud role routing is a separate data/privacy/cost decision:
ALLOW_REMOTE_LLM alone is not per-role data classification, remote-provider setup,
consent to transmit private information or an assurance of free usage. No cloud
setting, provider key, model download or budget change was made by this review.

A one-page decision brief should show who supports each recommendation, actual
objections, evidence and the next owner decision. Do not fabricate disagreement to
make the brief more interesting. Portfolio recording/diagram work is optional
presentation work after a representative job and safe review flow are demonstrated.

The four known unpatched Chroma advisories remain a separate release finding.
Claude explicitly did not review memory/, the dashboard or logs. This feedback is
therefore a partial code review, not a security clearance or a reason to weaken the
existing privacy, approval, sandbox or audit boundaries.
