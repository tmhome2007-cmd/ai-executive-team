# Sprint 3 planning proposal

10 October 2026. Baseline: merged pre-Sprint 3 audit PR #34, main `505eac5639b4d17783a0071be509828acb7be83f`.

Status: owner selected BE-20–22. Implementation is in review; BE-23 is deferred. See [SPRINT_3_PRACTICE_EVIDENCE.md](SPRINT_3_PRACTICE_EVIDENCE.md) for the implementation and owner checks. [PRE_SPRINT_3_AUDIT.md](PRE_SPRINT_3_AUDIT.md) identifies the evidence and design gaps. BE-15–19 are completed Sprint 2 history.

## Sprint goal

The agents produce useful private work, explain which business options the evidence supports, and demonstrate whether owner feedback improves subsequent work. The owner reviews and approves; the owner is not expected to draft the professional deliverable. Spending and permitted loss remain €0. No publishing, customer contact, paid services or business launch.

## Proposed Development board

| ID | Priority | Story | Observable acceptance | Dependencies |
|---|---|---|---|---|
| BE-20 | High | Useful private deliverables and review rubrics | An approved exercise has clear audience, supplied facts, expected deliverable and 2–10 observable checks. At least three representative fixtures include a task guide with unspecified UI, an evidence summary and a constrained draft. Output provides the requested deliverable instead of advice to write it. Unsupported features/approval claims fail checks or are visibly flagged; missing facts remain unknown. Owner reviews one representative sample early, then the remaining examples. | Existing BE-17 practice/history and BE-16 review UI |
| BE-21 | High | Evidence-backed business option comparison | Distinguish demand/buyer evidence from platform rules and implementation constraints. Agents propose/read bounded public sources within the existing safety policy; inaccessible sources stay missing. Comparisons link claims to dated records and show contradictions, unknowns, costs and agent capability gaps. Hosting products do not become service businesses. If evidence is insufficient, selection stays blocked with a concrete next research step. No guaranteed profit or invented demand. | BE-04 evidence and existing BE-17 comparison; reuse BE-20 usefulness checks |
| BE-22 | High | Measure improvement from recorded feedback | Link each revision to the exact sample/review/rubric version. Display before/after owner assessments and unresolved failures; changed rubrics cannot silently count as improvement. Preserve failed samples and corrected assessments. At least two separate assessed examples are needed before displaying repeated practice evidence; no aggregate evidence grants launch, execution authority or verified professional competence. | BE-20; existing retained practice history |
| BE-23 | Optional | Actual local voiced executive conversations | Owner explicitly requests synthesis of a selected published contribution with a saved available local neural voice. Playback loads duration, plays and stops; failures/reload are clear. Bound text/work/time/cache use, protect media with owner auth, keep keys out of URLs and exclude company text from cloud services. Cache/history are linked to contribution/profile versions. Agree generated-audio retention before implementation. Auditions remain distinct. | Existing BE-19 auditions/preferences; separate scope choice |

Selected commitment: BE-20–22. BE-23 is optional; full 3D offices, autonomous employee tools, cloud voices, model training and commercial delivery remain future work. These IDs are planning records, not evidence that live dashboard cards were created or approved.

## Conceptual design before coding

For BE-20 define exercise specification and rubric version separately from sample and owner assessment. Avoid treating a model self-check as an owner result. Keep raw output and any published intervention distinguishable.

For BE-21 define source classification and claim-to-source links; classification is not independent verification. Record publication date when supplied, fetch time separately, missing date as unknown. Define ranking criteria explicitly, with evidence sufficiency independent from option preference. Treat read pages as untrusted data, not instructions.

For BE-22 improvement is a comparison of assessments under a consistent rubric, not changed model weights. One corrected sample is not repeated competence. Reuse existing history rather than create a second contradictory review ledger.

BE-23 needs its own private text-to-audio path; the fixed public audition pack is insufficient. Define concurrency, cache limits, cancellation and retention before synthesis. Provider choice remains local; new downloads/dependencies require normal privacy/security verification.

## Working agreement from Sprint 2

1. Work one coherent story at a time with a separate feature PR where practical.
2. Show one representative visible/audible result early, before expanding the implementation.
3. Verify complete interactions and negative cases using disposable data. Use `./company start` for owner review and `./company audit` for verification; keep restart instructions short.
4. Owner review contains the result, known issues and a few specific checks. Passing automated tests does not substitute for usefulness or sound-quality acceptance.
5. Done means acceptance criteria met, relevant failure paths tested, privacy/authority preserved, documentation current and owner acceptance recorded. Scope and merge approval are separate.

## Sprint completion and retrospective

Record which examples the owner assessed, their actual check results, revision comparisons, defects and remaining unknowns. No velocity, revenue, hours saved or quality percentages without measured records. Retrospective asks whether review became easier and whether the work became more useful. Finish with the fixable security/privacy/bug review for changed surfaces, retaining upstream findings separately.
