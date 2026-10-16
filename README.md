# AI Executive Team

A local-first dashboard for eleven AI executives to research, discuss and propose work. The owner reviews decisions and separately approves consequential actions. Current scope is **€0 private research and text practice**; model output is advice to review, not authority or proof of competence.

## Start the app

In your terminal:

```sh
cd "/Users/alpha/Ai village/AI Executive Team V2CHAT"
./company doctor
./company start
```

Keep that terminal open and visit **http://127.0.0.1:3000**. The launcher copies the existing dashboard key; paste it at login. `./company key` copies it again. Ctrl+C stops the apps launched by that terminal. If ports 8001/3000 are occupied, identify the existing processes before stopping them.

The launcher preserves `.env` and company data, uses local sandbox settings, and disables remote models and Telegram. Eligible scheduled work may still run while the app is awake. Use this V2CHAT checkout rather than the older original folder.

For a fresh installation, use Python 3.12, Node/npm, local Ollama with `llama3.1`, and Docker for isolated execution/tests. Install Python dependencies into `.venv` from `requirements.txt` and dashboard dependencies with `npm ci` in `executive-dashboard/`. Only a genuinely fresh checkout without configuration or company data should run `./company init-local` once. Never replace an existing `.env` or database as a startup fix. [Full local commands and recovery](LOCAL_COMMANDS.md).

## Using and checking the app

- Decisions: start a normal decision or use **Plan a first real-user test** for the bounded short-request helper. Enter project facts under **Add project facts or choose reviewed records**. Chat history is not imported automatically.
- Read **Your next step** first in new first-user results. This panel is application guidance; the executive proposals below it remain unverified. Expand the supporting sections to inspect facts, objections and evidence. Older saved decisions retain their original advice.
- There is **no result-level feedback/revision or learning-memory flow yet**. The existing pre-generation corrections field changes inputs; it does not train the model. This distinction is central to Sprint 8.
- Direction approval, action approval, resource provision and execution are separate controls. Do not approve or execute work merely to test the interface.

[Step-by-step decision test with sample input](docs/guides/decision-test.md) · [Private practice](docs/guides/private-practice.md) · [Company practice review](COMPANY_REVIEW_GUIDE.md).

```sh
./company test        # Backend regression tests
./company check-code  # Formatting and generated catalog checks
./company audit       # Broader checks using disposable data
```

`./company format` changes formatting and refreshes the code catalog. Do not run fresh setup or delete company records to run tests. More development commands are in [the developer guide](docs/DEVELOPMENT.md).

## Development status

Updated 16 October 2026. **Sprint 7 is closed as a planning period with partial delivery.** Its original quality goals were not all achieved. Unfinished work is carried into the cycle below. No new merge, release clearance or owner usefulness acceptance is implied.

Delivered locally: bounded short-request intake, explicit application checklist, compact answer presentation, preserved detailed proposals, durable request saving/replay/recovery, source/freshness guards and startup cleanup. The latest owner result shows the new top panel in a saved CFO/CEO decision. The owner has not accepted the executive reasoning as useful.

Outstanding reasoning errors include supplied facts treated as unknown, unsupported assumptions about a silent contact's interest, a known fact labelled pivotal, arbitrary stop rules, weak citation relevance and critique, and confusing competing application/model effort estimates. [Detailed error inventory](docs/research/ai-error-inventory.md).

Latest compact-answer verification: **430 backend tests passed with real Docker and no skips**, plus passing production browser/build checks on desktop and mobile. [Verification manifest](docs/planning/be63-compact-answer-verification.json). These are prior results, not tests rerun by this documentation cleanup.

The preceding complete working-tree audit recorded **33 PASS / 1 FAIL**, with 429 backend tests, 150 foundation checks and 15 browser features passing. The dependency scan found four Chroma issues and MCP `GHSA-84m7-p3x7-pcfv`. A fixed MCP version conflicts with the checked CrewAI dependency range. Findings remain open; targeted UI tests do not clear them. [Audit manifest](docs/planning/sprint-7-completion-verification.json) · [Security release gate](SECURITY_RELEASE_GATE.md) · [Compatibility investigation](docs/guides/BE64_RELEASE_RECHECK.md).

The active local branch is `codex/sprint-7-actionable-schema`, last checked at HEAD `58b9992`, with substantial uncommitted changes. The last remote check found main `822712a` and no matching Sprint 7 remote branch; open PR inventory was not refreshed. Reverify before integration. Sprint 5's bounded scope was accepted/merged in PR #50; Sprint 6/7 integration remains pending. Original [Sprint 6](docs/planning/sprint-6-cards.json) and [Sprint 7](docs/planning/sprint-7-cards.json) acceptance records remain available.

Retrospective lessons: bound sprint scope, show representative results early, distinguish valid structure from useful reasoning, preserve failed comparisons, and describe proposed features as proposals until they exist. Failed model prototypes stay isolated. Familiar development examples and author-exposed cases are not blind evidence of general competence.

## Development cycle

Use **four sprints, then a broad audit and retrospective**. Each sprint has one main goal, relevant tests and a short owner review. Two weeks per sprint is proposed; kickoff/end dates are not set. Unexpected work replaces scope or returns to the backlog rather than extending the sprint indefinitely. Address security findings when discovered, not only at cycle end. Aim to keep each owner review within 15 minutes.

| Period | Main goal | Items |
|---|---|---|
| Sprint 8 | Feedback on a result and a reviewable revision | BE-66 baseline/delivery boundary; BE-67 feedback/revision; BE-68 training-method research; BE-69 early security assessment |
| Sprint 9 | Reuse approved lessons while preserving project facts | BE-70 reviewed memory; BE-71 facts/unknowns/citations; BE-72 evaluation and reviewed examples |
| Sprint 10 | Choose models/workflows using measured usefulness | BE-73 alternatives/critique/synthesis; BE-74 local model comparison; BE-75 training feasibility |
| Sprint 11 | Coherent owner experience and integration readiness | BE-76 primary answer/history; BE-77 operational review and delivery scope |
| After Sprint 11 | Broad audit, review and retrospective | BE-78 whole-project audit; BE-79 next-cycle planning |

[The single current backlog](docs/planning/cycle-1-cards.json) contains all 14 items, dependencies and acceptance checks. Later sprint allocations are refined at kickoff. A sprint may close with unfinished work explicitly carried forward. Done still requires accepted scope and an authorized actual merge; closure does not authorize merging or release.

### Sprint 8: first implementation priority

Status: **planned; implementation not started**. Goal: the owner can explain what is wrong with an answer, review a revised version and see what changed.

1. **BE-66:** review the actual result and the existing uncommitted Sprint 6/7 delivery boundary before adding changes; freeze a small baseline and usefulness criteria.
2. **BE-67:** add **Give feedback** beneath the result and an explicit **Revise answer** action. Separate fact corrections from response preferences. Keep the original and revision linked and retrievable; saving feedback must not silently generate, approve, send, train or create permanent memory.
3. **BE-68:** research published learning methods against our observed failures, within a bounded read-only scope.
4. **BE-69:** recheck known security issues, actual exposure evidence and supported compatible fixes. A needed repair takes precedence over optional research.

Acceptance: English desktop/mobile controls; attributable correction and source context; original/revision history after reload; safe duplicate handling and recovery; no unrelated context import or authority expansion. Define private feedback retention/withdrawal before adding storage. Compare the silent-contact regression and unrelated development cases, reporting semantic failures separately from technical validity. Obtain owner review of a representative before/after result. One better Reinstatly rewrite does not establish general learning.

## Learning and model research

The executives are roles and workflows around existing models. **Feedback retrieval changes the context; training changes model weights.** We should collect reviewed corrections, measure transfer to new tasks, and then decide whether a local training pilot is justified. Preferences must not overwrite facts or teach agreement regardless of evidence.

Initial primary sources, read 16 October 2026:

- [OpenAI supervised fine-tuning guidance](https://developers.openai.com/api/docs/guides/supervised-fine-tuning): corrected input/output examples and evaluation before training. This is application guidance, not the full training recipe for current frontier models. The page says its hosted fine-tuning platform is winding down; no adoption of that service is proposed.
- [Anthropic Constitutional AI research (2022)](https://www.anthropic.com/research/constitutional-ai-harmlessness-from-ai-feedback): supervised critique/revision training and AI preference feedback. This historical harmlessness research is not evidence that runtime critique solves our business-advice problems or a complete recipe for current Claude.
- [Hugging Face TRL DPO documentation](https://huggingface.co/docs/trl/en/dpo_trainer): chosen/rejected response pairs for preference training. This is a possible implementation approach, not an adopted dependency or proven local-hardware fit.

Compare retrieval, corrected-example training, preference training and model/workflow changes. A training proposal must cover dataset quality, untouched evaluation, model/data licenses, local memory/runtime, privacy/retention, withdrawal limits and rollback. No training pilot, extra download, cloud calls or spending is authorized by this roadmap. Reproducing ChatGPT or Claude from scratch is outside this project's scope.

Research stays narrow: one diagnosed problem, at most five primary pages/candidates per run, generic queries, read-only. Treat external instructions as untrusted data. Check license, maintenance, dependencies and compatibility before adoption; unknown fields stay unknown. [Previous reuse research](docs/research/BE57_RESEARCH_SHORTLIST.md) · [Citation relevance](docs/research/citation-relevance.md) · [Independent-proposal comparison](docs/research/BE60_INDEPENDENT_PROPOSAL_REVIEW.md).

## Architecture and safety

| Location | Responsibility |
|---|---|
| `agents/` | Eleven executive identities and bounded tools |
| `api/`, `main.py`, `foundation_api.py` | Authenticated API and lifecycle |
| `workflows/` | Meetings, research, practice, recovery and approved execution |
| `memory/` | Company records, SQLite transactions and provenance |
| `tools/`, `notifications/` | Narrow proposal tools and configured notifications |
| `executive-dashboard/` | Next.js owner dashboard |
| `tests/`, `scripts/` | Regression tests, launcher, maintenance and audits |

Owner direction approval and action approval remain separate. Imported history, skills, model statements and board status grant no authority. Local sandbox is the default. Live shell is default-off; its opt-in worker uses a pinned Docker image and constrained offline execution. Browser/network and filesystem guards remain in force. Telegram is notification-only unless explicitly configured otherwise; remote models are blocked by default.

SQLite is not application-encrypted; local permissions and disk encryption are separate protections. Keep credentials out of Git and chat. Private generated artifacts/logs/media use the existing 30-day retention policy; durable approval and provenance records remain. Uncertain external effects require reconciliation. A laptop that is asleep does not execute scheduled work. No tests or simulation establish commercial demand or competence.

[Developer guide](docs/DEVELOPMENT.md) · [Generated source catalog](docs/CODE_CATALOG.md) · [Shared contracts](docs/CONTRACTS.md) · [Safety details](docs/guides/safety-architecture.md) · [Privacy, retention and recovery](docs/guides/PRIVACY_OPERATIONS.md) · [Conceptual model](docs/guides/CONCEPTUAL_SYSTEM_AUDIT.md).

## Documentation layout

The README is the current entry point for status, sprint method and next work. `docs/guides/` holds operational/technical instructions; `docs/research/` holds important diagnoses and rejected experiment notes. `docs/planning/` retains the current backlog, original acceptance records and verification manifests; `docs/evaluation/` retains evaluation inputs and provenance. Raw local audit/evaluation artifacts remain at their existing private paths and retention rules.

Redundant sprint plans, progress narratives, old review summaries and duplicate archives were removed during consolidation. Tracked history remains in Git. Historical verification manifests retain original paths and hashes; they are evidence snapshots, not a current documentation navigation index. Application code, tests, environments, credentials, databases, private audit files and the owner's ZIP were not removed.
