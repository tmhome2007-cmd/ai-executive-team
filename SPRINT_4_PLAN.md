# Sprint 4 — reliable skills, inspectable work and a first 3D office

Planned 10 October 2026, after Sprint 3 and the code-maintenance merge. The selected scope is below; implementation progress is recorded at the end. Owner acceptance remains pending.

## Sprint goal

An executive reuses a reviewed procedure on a new fictional task, produces a private deliverable, and shows the owner its evidence, measured quality and recoverable run history. Include a bounded 3D office prototype driven by real recorded activity.

Budget and permitted loss remain €0. No launch, customer contact, public publishing, cloud processing or new paid services are authorized. Planning cards do not authorize execution.

## Selected work

### BE-24 · AI quality benchmarks and prompt versions

Priority: high. Dependencies: Existing practice contracts and feedback (BE-20–22).

Acceptance: Version prompts, model/configuration and rubric. Run ten fixed fictional fixtures three times each locally; show failures and denominators, preserve reports, distinguish deterministic checks from unverified model judgements. Compare only matching rubrics; allow prompt rollback.

### BE-25 · Versioned reusable executive skills

Priority: high. Dependencies: BE-24.

Acceptance: Record procedure versions, prerequisites, permitted task types, limitations and source sample/review IDs. Owner accepts a version after two reviewed examples; test reuse on a third unfamiliar fictional example. Revocation prevents future selection. A skill never grants tools, spending or launch authority.

### BE-26 · Private deliverable workspaces

Priority: high. Dependencies: BE-24 and BE-31 artifact rules.

Acceptance: Create owner-only text/Markdown artifacts with hashes, versions and source/rubric links. Download and compare revisions. Reject traversal, symlink escapes and unsafe active content; never execute generated code. Apply 30-day generated-file retention while preserving durable review metadata and reporting expired content honestly.

### BE-27 · Run inspector and guarded continuation

Priority: high. Dependencies: Existing checkpoints/activity ledger; BE-24 version metadata.

Acceptance: Show step status, duration, error category, pending input and prompt/model version without exposing secrets or raw private prompts by default. Stop and resume disposable local generation without duplicate results. Unknown external outcomes require reconciliation, never automatic replay. Explain laptop sleep and interrupted runs.

### BE-28 · Reviewed workflow templates and research queue

Priority: medium. Dependencies: BE-25–27.

Acceptance: Provide one evidence-to-private-practice template with explicit inputs, outputs and gates. Queue proposed sources separately from fetched records; distinguish buyer evidence from platform documentation. Validate dependencies, reject cycles and unsupported capabilities; retries preserve approvals. No paid search, publishing or customer contact.

### BE-29 · Evidence-linked company knowledge view

Priority: medium. Dependencies: Existing reconciled memory/source registry; BE-25.

Acceptance: Use existing SQLite records to navigate goals, decisions, actions, outcomes, lessons and skills. Explain retrieved sources and timestamps; surface conflicts, expiry and corrections. Generated relationships remain unverified until reviewed. Corrected facts stop influencing current retrieval while historical provenance remains visible.

### BE-30 · 3D office first floor prototype

Priority: low. Dependencies: Existing identity profiles and activity stream; BE-31 asset review.

Acceptance: Render one floor and one existing executive with recorded activity and clear idle/unknown states. Preserve Kai’s specified appearance and approved identities. Pause when hidden; retain accessible 2D fallback. Measure responsiveness on the owner’s Mac. Animation is fictional presentation, never proof of work; full office, all employees and personal-life simulation expansion are later increments.

### BE-31 · Sprint contracts, privacy and reuse review

Priority: high. Dependencies: None; begins Sprint 4.

Acceptance: Map new entities and use cases to existing approvals, memory and checkpoints; avoid duplicate authority ledgers. Define artifact retention and recovery, skill revocation and evaluation comparability. Before copying code/assets or adding dependencies record source commit, license, attribution and vulnerability review. Keep €0 budget and local processing; obtain explicit approval for any cloud or paid change.

### BE-32 · Sprint integration audit and simple owner review

Priority: high. Dependencies: BE-24–31 completed or explicitly deferred by owner.

Acceptance: Audit fixable conceptual, security, privacy and bug issues across the final changes using disposable data. Test authentication, artifact boundaries, recovery, repeated generation and revoked skills; show actual output examples. Provide short ./company instructions. Fix project findings; list upstream limitations separately. Owner review precedes merge.

### BE-33 · Sprint 4 retrospective and next-sprint planning

Priority: medium. Dependencies: BE-32 and owner feedback.

Acceptance: Record intended versus delivered scope, actual test evidence, confusing owner steps, quality failures and improvements. Agree concrete next-sprint actions; never label backlog or prototypes fully complete. Update README and board statuses with review/merge evidence.

## Order and scope

Start BE-31, then BE-24. Build BE-25, BE-26 and BE-27 before BE-28 and BE-29. BE-30 can proceed after its asset/privacy prerequisites; it is a one-floor prototype. Finish with BE-32 and BE-33. All seven research ideas are included; the full versions of the skill ecosystem, workflow editor, knowledge graph and virtual office require later increments.

This is a selected backlog, not a promise that ten stories fit a fixed calendar window. Estimate after BE-31, review capacity and agree any scope change explicitly. Keep incomplete cards visible rather than marking them done to close the sprint.

## Working agreement

- A ready card has a concrete example, acceptance checks, dependency decisions and an owner review path.
- One coherent change per PR; show a representative output early. Preserve current personalities and identities.
- Use existing company records, approvals and checkpoints; avoid introducing a second execution or permission system.
- Verify with disposable data. Keep owner instructions short and retain the existing API key.
- Done means implemented, meaningfully tested, documented and owner accepted; merge evidence belongs in the completion note.
- Keep known upstream advisories visible separately from fixable project defects.

## Research and reuse

Patterns come from [Promptfoo](https://github.com/promptfoo/promptfoo), [Langfuse](https://github.com/langfuse/langfuse), [Hermes](https://github.com/NousResearch/hermes-agent), [OpenHands](https://github.com/OpenHands/OpenHands), [MetaGPT](https://github.com/FoundationAgents/MetaGPT), [LangGraph](https://github.com/langchain-ai/langgraph), [ChatDev](https://github.com/OpenBMB/ChatDev), [Graphiti](https://github.com/getzep/graphiti), [n8n](https://github.com/n8n-io/n8n) and [Three.js](https://github.com/mrdoob/three.js). These are design references, not audited dependencies or evidence of revenue. Review exact code/assets and licenses before reuse; n8n and Langfuse include licensing exceptions/restrictions.

## Development board

The matching planning cards are stored in [docs/planning/sprint-4-cards.json](docs/planning/sprint-4-cards.json). They belong on the separate **Sprint 4 development plan** board. Existing development and company cards are preserved. The old “Create development roadmap” button still imports the historical BE-01–14 template; it does not import this sprint.

## Implementation progress — 10 October 2026

BE-31 contracts and BE-24 benchmark tooling are in Review, pending owner acceptance. See [contracts](docs/SPRINT_4_CONTRACTS.md) and [quality measurements](docs/BE24_QUALITY_BENCHMARKS.md). BE-25 is also implemented for review; BE-30/32–33 were unimplemented at this initial increment. The first measured JSON-mode run passes 24/30 narrow checks; unresolved measurements remain visible.

BE-25 is implemented for review on `codex/sprint-4-skills`; see [review instructions and limitations](docs/BE25_EXECUTIVE_SKILLS.md). BE-26 is implemented for review on `codex/sprint-4-artifacts`; see [private files](docs/BE26_PRIVATE_ARTIFACTS.md). BE-27 is implemented for review on `codex/sprint-4-run-inspector`; see [run inspection](docs/BE27_RUN_INSPECTOR.md). BE-28 is implemented for review on `codex/sprint-4-workflow-queue`; see [workflow patterns and research queue](docs/BE28_WORKFLOW_QUEUE.md). BE-29 is implemented for review on `codex/sprint-4-knowledge`; see [company knowledge](docs/BE29_COMPANY_KNOWLEDGE.md). BE-30 was next at this increment. Owner acceptance and merge evidence is recorded in subsequent updates.

## Owner-added dashboard redesign before BE-30

UX-01 is ready for review: grouped sidebar navigation, a calmer overview, consistent forms and responsive mobile navigation. Business research separates practice, runs and skills while retaining drafts between those tabs. See [DASHBOARD_REDESIGN.md](docs/DASHBOARD_REDESIGN.md). BE-30 remains the next backend item after this layout review.

BE-30 is implemented for review on `codex/sprint-4-office`: [first floor scope and review](docs/BE30_OFFICE_FLOOR.md). It is a CSS perspective room with the existing illustrated Kai; fully modelled bodies and the full office remain future work. UX-01 was accepted by the owner; merge remains pending.

BE-32 integration audit fixes are on `codex/sprint-4-audit`: [findings and verification](docs/BE32_SPRINT4_AUDIT.md). BE-30 was accepted by the owner in chat; PR #46 awaits merge. BE-33 remains the next retrospective after audit review.

## Retrospective — 11 October 2026

BE-33 is ready for review: [Sprint 4 retrospective](SPRINT_4_RETROSPECTIVE.md). It records the complete local audit, the remaining AI quality gap, integration failures and proposed next-sprint actions. Owner acceptance of UX-01 and the bounded BE-30 prototype is recorded; pending PR merges are not Done. Next-sprint priorities remain proposals until agreed.
