# BE-20–22: private work, evidence and feedback

Status: implemented for owner review; not Done until the owner accepts the visible results. Sprint 3 keeps a €0 spending/loss limit and the existing separate action, resource and launch approvals.

## BE-20: approved work specification

Choose **Business research → Prepared exercise** after a comparison, or enter an audience, supplied facts/unknowns, deliverable format and 2–10 observable checks. Three fixtures cover a task guide with an unspecified interface, a fictional evidence summary and a constrained customer reply. The agents draft the text; the owner assesses its usefulness. For the fictional task-guide fixture, the model selects the exact supplied example texts and drafts FAQ answers. The server visibly renders the three approved function steps rather than allowing it to invent interface instructions. This formatting intervention is labelled in the sample; it is not proof of independent drafting skill.

Approval creates an immutable specification. Every new sample and assessment is bound to that specification. Revision keeps the same input and rubric. To change the task or checks, create a new brief. Existing historical samples remain readable; they are not retroactively assigned an approved structured specification.

Representative checks reject the previously observed empty guide, invented listed controls, missing required sections/test counts and refund/approval claims. These are bounded contract checks, not a universal fact or writing-quality evaluator. Failed generation gets at most one local repair and then retains a review-needed state. An owner can still fail a structurally accepted sample for poor usefulness.

## BE-21: distinguish business evidence

Selected source cards have an owner classification: unknown, buyer, demand, platform, constraint or contradiction; relevant service keys; optional publication date; and relevance note. Saving adds a version rather than overwriting the prior classification. Reading time never becomes a fabricated publication date. New public reads expire from their recorded freshness window after 30 days; that window does not prove continuing accuracy. Owner confirmation is available in the existing Evidence view. Older unknown freshness remains unknown; register a new record to supply an explicit review window. Classification does not confirm a source's truth.

A research claim must quote exact text from a selected immutable source and identify its service and supporting/contradicting relation. Unsupported quotations are withheld with a visible warning and receive no coverage credit; invalid comparison structures still fail generation. Reports retain the source contents, owner classification and verification versions captured when research was claimed. Changes require a new research brief.

The explicit research-priority heuristic requires quotations for a service from at least two distinct source-site groups, owner-confirmed source records, a current recorded freshness window, publication within 365 days and buyer/demand classifications. Owner-classified or quoted contradictions and unresolved attributions block that service; equal coverage blocks a unique selection. Subdomains count once using the last two hostname labels without a network lookup; public-suffix exceptions can conservatively undercount. Distinct groups do not prove independent publishers or real demand. The highest coverage identifies a research candidate only. Costs, commercial eligibility and agent competence remain unresolved until separately evidenced.

Platform-only inputs block business selection and give a concrete step: obtain recent public buyer requests/problems, record dates and relevance, review accuracy and investigate counterevidence. The model may suggest up to five URLs. **Read proposed source** uses the existing protected reader only after an owner click; failed reads create no evidence record. Private briefs are never sent to those sites. New evidence is selected for a new brief, not silently inserted into the original report.

## BE-22: compare exact assessments

**Feedback improvement** shows original/revised sample IDs, the exact feedback review and latest revised assessment, checks improved/regressed and failures remaining. Corrected assessments remain in history. The original feedback is never replaced by a more convenient baseline. Unbound legacy records do not claim a comparable result.

**Repeated practice evidence** groups identical rubrics across distinct supplied fact sets, using the latest assessed sample per brief. Copied facts (case, spacing and punctuation differences included) and repeated revisions do not add examples. New unreviewed revisions remove the old sample from current aggregate results. Two distinct assessed examples establish repeated practice records; passing counts remain separate. Neither grants verified competence, model training, demand or launch authority.

## Owner review

1. Run `./company start`, then open Business research. Existing records remain intact.
2. Create a new comparison, choose the task-guide fixture, choose a future review date and approve the private plan. Check that the generated guide is useful without inventing buttons or reminder functions.
3. Assess every check honestly. Revise a failed sample, assess the revision and inspect **Feedback improvement** and **Sample & review history**.
4. Try the evidence-summary and customer-reply fixtures. Check the preserved counts/unknown cause and the no-refund-promise boundary.
5. With the three starting platform records, verify that business selection remains blocked and the report explains which buyer evidence is missing. Source classification and repeated practice panels should not imply money-making readiness.

`./company audit` runs disposable verification. It does not assess every future model response or record owner acceptance.

## Verification — 10 October 2026

The final disposable audit at `audit-results/20261010-161459` passed all project checks: 178 backend tests including real Docker isolation, 150 foundation regressions, Bandit medium/high checks, voice dependency checks, clean frontend installation/lint/TypeScript/build/npm audit, API policy checks, all eight browser suites, Chromium and local Ollama inference. The updated business browser suite covers source classification, an explicitly clicked proposed-source read, unchanged original brief sources, prepared exercises, assessment correction and exact feedback improvement. The existing image-optimization lint warning remains.

The optional real-model run at `audit-results/sprint3-examples-20261010-161501` passed the structured/source comparison contract and all three representative practice contracts. These are fictional examples without owner acceptance; no action or treasury entry was created. Run `.venv/bin/python scripts/sprint3_practice_smoke.py` to repeat this additional local-model check. Its raw/withheld diagnostic drafts, if any, stay outside Git.

Python dependency scanning still reports the same four known Chroma advisories. They remain visible separately from project check failures; no advisory was ignored or cleared. This implementation and its passing checks do not record launch permission, verified competence or a production release decision.

### Research-card review correction

The prompt no longer supplies an example source URL that the model can copy. Reserved example/test domains are withheld from generated recommendations, and existing reports retain their text while the dashboard removes those source-read controls. The short review now recognizes the legacy “Practice candidate only:” field and the next research step. New reports give explicit prepared-exercise instructions. Verified with 34 business/practice tests, summary and proposal-control tests, frontend lint (one existing image warning), and a production build.

### Task-guide FAQ review correction

Owner review exposed an unsupported task-list interface in a FAQ. Unknown-interface checks now also reject instructions using invented task views, and generation/schema guidance explicitly prohibits assuming a task list or selection control. Source-proposal lines are excluded from action excerpts, including historical placeholder proposals; original reports remain intact. The 34 business/practice tests, summary tests, lint and production build pass. A disposable real local Ollama task-guide run (`audit-results/sprint3-examples-20261010-172953`) produced FAQs without the invented task list and passed structural checks. Usefulness remains an owner assessment.
