# BE-17 local review — 9 October 2026

The owner asked for an AI-operated path toward earning money, without assuming personal professional skills or authorizing any spending. This increment supplies research and private text practice. It does not launch a business.

## Try it

Stop the existing `./company start` with Ctrl+C in its own terminal, then:

```sh
cd "/Users/alpha/.codex/.chatgpt-projects/g-p-6ac6034a5d7881918e21bf72595bb34b/foundation-hardening"
./company start
```

The checkout is on `codex/business-experiment-discovery`. Do not switch branches with uncommitted personal changes. The launcher preserves the existing key/database and copies the key for dashboard login. Open http://127.0.0.1:3000 and select **Business research**.

1. Read the three starting sources, or select existing evidence records. Public reads use the existing bounded page reader and private-address restrictions. Failed pages are not evidence. Starting pages describe platform/hosting constraints; add relevant customer/demand records before expecting a justified business choice.
2. Save the default €0 brief, then **Compare options with local AI**. Sources remain unverified and the recommendation may be “insufficient evidence.” Read the full comparison and source records.
3. Choose an option for practice only. Example: “Documentation”; exercise: “Draft a guide explaining how to review a synthetic AI-generated recommendation. Clearly label unknown facts.” Checks, one per line: “Distinguishes evidence from assumptions”; “Does not claim owner approval”; “Provides a concrete next review step.” Pick a future review date.
4. Approve the practice plan, then generate the private sample. The AI explains an approach, drafts and self-checks. Nothing is executed or published. Only local Ollama is permitted, even if the app globally allows remote inference.
5. Inspect the sample and explicitly choose Passed or Failed for every check. Unassessed checks prevent submission. Record what you checked. The result is an owner assessment of this sample, not independent competence, demand or profit verification.

A due date is recorded, not automatically scheduled in this increment. Configuration is checked before claiming a stage. Failed/interrupted generations remain for review and do not replay automatically; refresh, then use **Create new attempt from this brief** to reuse saved sources without deleting the failed research record.

For an existing reviewed sample, use **Correct review results** if you recorded the wrong assessment. A correction adds a new review and preserves the old one. Then choose **Revise sample using this review**. The local model receives the latest feedback and previous sample; a successful revision creates a new sample awaiting a fresh owner assessment. Expand **Sample & review history** to compare every version. A failed or interrupted revision preserves the previous sample and review; retry explicitly. Each brief allows up to ten samples and twenty assessments per sample. Existing legacy samples/reviews are imported without rewriting their content.

Revision checks reject title-only deliverables, specific unsupported interface controls and model claims of passing checks. Task guides must include numbered instructions, and exercises requesting three FAQs require three answers. These checks cover observed regressions; they do not verify every generated claim or replace owner review.

## Verification

- Full disposable audit: `audit-results/20261009-214623`: 136 tests, real Docker isolation, 150/150 foundation checks, Bandit, frontend lint/build/policy/dependency audit, Chromium and local Ollama passed.
- Ten discovery tests cover stage/version gates, disputed sources, strict review results, interruption, zero treasury/action effects sensitive/failed URL handling and rejected remote reasoning.
- Copied-dashboard browser flow covers authenticated research → practice plan → sample → review with synthetic inference; mobile layout, literal script-like text and key safety pass. Screenshot: `/private/tmp/business-discovery-mobile.png`.
- Actual local Ollama research stage passed on disposable synthetic evidence. Its recommendation correctly withheld a business choice due to missing demand evidence. This does not validate market feasibility or every generated claim.
- Four previously tracked unpatched Chroma advisories remain; the dependency scan is not clean. Existing image lint warning remains informational.

## Limits and next work

Public pages are selected by the owner (with three starting URLs provided); this increment does not include a search engine or independent demand research. AI quality checks can warn, but source attribution and usefulness still need review. Text practice cannot establish that code runs or that external delivery works. Practice stores outputs and review evidence, not model retraining or automatically verified executive skills. Research briefs are separate from action-linked financial experiments and do not activate goals, schedule work, grant tools or authorize actions.

Before real commerce: reliable delivery tests, buyer/demand validation, applicable platform eligibility/terms, separate owner approval and realised revenue/profit accounting. No earnings forecast or promise is made.

Follow-up: CrewAI normalizes the Ollama provider and model separately. The local-only validation now accepts `provider=ollama, model=llama3.1` and still rejects other providers or remote endpoints. Preflight failure leaves the brief in Draft. The isolated browser test covers failed generation → new attempt with retained sources → completed review.

### Comparison quality follow-up

Research now compares three bounded service hypotheses (documentation, editing,
policy-based support drafts), not hosting platforms or marketplaces. These are
practice candidates, not a market-discovered shortlist. Local AI returns a structured
comparison; the server checks its service keys and required skills/exercises/checks,
and attaches opening excerpts directly from the immutable source records. Failed output gets one local text-only repair, then is
withheld if still invalid. Source restrictions are quoted with their own provenance,
not generalized into a commercial-use finding about all platforms.

Demand, pricing, competence and commercial eligibility stay unknown; platform-only
records do not establish the best business. Older reports retain their content but
cannot advance to a new practice plan until a new attempt passes the current contract.
Ten targeted tests cover this gating, platform-as-business regressions, model-supplied
quotations, broad commercial-use claims and the existing zero-budget workflow.

The local call uses CrewAI's supported per-call structured response model, without changing shared executive settings. Excerpts are attached directly by the server, not generated by the model. The full disposable audit at `audit-results/20261009-223736` passed; previously tracked Chroma findings remain visible.

The final comparison also supplies concrete minimum review controls (preserved facts, explicit unknowns and no invented executed actions). Real delivery access remains unassessed; the model cannot invent a platform-documentation dependency for private practice.

### Feedback revision verification

Sixteen targeted tests pass, covering legacy import, preserved original assessments,
corrections, duplicate/stale generation claims, crash recovery, completeness and
unsupported interface details. The copied-dashboard browser test passes the full
review → correction → revision → fresh review sequence, with no actions or money.
The disposable audit at `audit-results/20261009-230900` passed 148 tests, all 150
foundation checks, Docker isolation, Bandit and frontend checks. Its Ollama greeting
timed out while inference was under test; a subsequent separate local API greeting
succeeded. Previously tracked Chroma advisories remain visible.

Actual model testing also exposed a title-only answer and an invented pencil icon.
Both are rejected by the revision contract rather than published as successful
revisions. These safeguards do not guarantee a useful output from every local model
attempt. BE-17 remains in owner review; no competence or business launch is approved.
