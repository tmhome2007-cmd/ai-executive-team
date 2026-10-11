# BE-35 — useful private work, first review batch

Current status: owner accepted the documented bounded Sprint 5 scope on 11 October
2026; merged via [PR #50](https://github.com/tmhome2007-cmd/ai-executive-team/pull/50). Earlier pending/
not-merged entries below describe their original evidence stage. See
[closure record](SPRINT_5_CLOSURE.md); known security/model-quality limits remain.

11 October 2026. Development evidence; owner usefulness assessment pending.

## Comparable benchmark experiment

The new facts-handling prompt passed 30/30 narrow JSON-contract checks versus
24/30 for the fresh frozen baseline. Both runs have zero transport errors and
zero incomplete attempts. Dataset, checker, rubric, model digest and generation
settings are identical; only the prompt changed. The checker was not weakened.

Baseline run: `3740c7d768bb47e3ab44125213251b04`.
Candidate run: `a6a8f2ff8dd84d5a842b949f7f6dd0d0`.

The candidate explicitly distinguishes instructions from task evidence, requests
supplied fact wording in findings, and limits next actions to private review or
specific missing-information questions. This directly targets the two BE-34
patterns. A single paired run with three temperature-zero repeats per fixture
does not establish general competence or semantic usefulness.

The candidate is a benchmark-only snapshot in
[be35-benchmark-prompt.txt](docs/planning/be35-benchmark-prompt.txt).
Comparison identities and settings are in
[be35-comparison.json](docs/planning/be35-comparison.json).
The benchmark prompt remains separate from production. Subsequent reply-workflow
changes are described below; the benchmark dataset and checker are unchanged.

## Real deliverable failures remain visible

Two frozen examples use exact existing task-guide and support-draft rubric
wording. The second supplies a new fictional ceramic-bowl scenario, including an
unspecified start event for the 14-day period. It is a small transfer probe within
return-policy drafting, not evidence of competence in an unfamiliar profession.
See [facts and checks](docs/planning/be35-examples.json).

Tool-free freeform local drafts, one feedback revision each, and a separate
facts-first prompt experiment were retained in private run
`58b1562dccc345cb9d969b6033f3a381`. Original requests, responses, feedback,
revision ancestry, configuration and model-identity checks remain available.
No owner assessment was manufactured.

| Example | Initial draft | Revision | Facts-first experiment |
|---|---|---|---|
| Task guide | Invented field, control and active-list removal; unhelpful FAQ selection | Invented completed-task editing restriction; still used an unknown control | Speculated about completed-task editing and batch creation |
| Return draft | Preserved policy and requested date/condition, but retained signature placeholder and omitted unknown period start | Same shortcomings remained | Same shortcomings remained |

The shared general text checker found no issues in those texts. Inspection still
found unsupported statements and unfinished content. This is concrete evidence
that narrow automatic checks cannot replace useful-work review. The 30/30
benchmark score must not hide these failed deliverable experiments.

## Supported workflow comparison

The existing structured task-guide workflow was tested separately on disposable
data with real local generation. It passed its deliverable contract and produced
the same-task create/edit/complete sequence, three FAQ answers, and explicit
unknown controls/reminders. Output:
`audit-results/sprint3-examples-20261011-132028/task_guide.txt`.

The guide labels its intervention: the server renders approved function steps;
the model supplies example text and FAQ answers. This is an assisted workflow
result, not independent freeform drafting success. Research was skipped with a
labelled fictional comparison to isolate practice generation. No action-queue or
treasury entry was created, and no company database or key was used.

`scripts/sprint3_practice_smoke.py --fixture support_draft --skip-research
--sprint5-transfer` tests the ceramic-bowl facts in that existing production
practice path. It rejects any mismatch with the exact existing support rubric.
Transfer results and owner review are recorded separately from the benchmark.

The real ceramic-bowl workflow probe at
`audit-results/sprint3-examples-20261011-132139` failed after its single bounded
repair. Both withheld drafts are preserved. The checker rejected the wording
“Whether a refund has been approved or issued” in its unknowns section. The text
also retains a signing placeholder and suggests purchase date could establish
whether the period has started despite the unspecified start event. The checker
finding and these separate review findings must be addressed without treating a
question as evidence of actual approval or accepting the unfinished reply.

Validation: 21 focused practice/benchmark/example tests passed with disposable
framework storage. An initial invocation could not create framework storage
outside the workspace; rerunning with explicit temporary storage passed. Both
real workflow probes separately verified zero action and treasury records. No
full Sprint 5 audit or production release clearance is claimed.

## Return-draft correction and final local evidence

The private reply prompt now asks for the actual reply, preserves an unspecified
period start and supplied negative approval facts, and omits unsupplied signing
identities. A bounded repair receives the failed draft before the final error and
correction instruction, so the old draft is explicitly treated as unsuccessful
material rather than evidence. The existing one-repair limit remains.

Reply validation rejects signing placeholders, an omitted explicitly unspecified
period start, a claim that purchase/delivery date can determine that start, and
omission of the supplied no-refund-approved-or-issued fact. These are additional
deliverable checks; the frozen owner rubric and benchmark checker were not
changed. Existing positive approval/refund statements still fail closed.

The first corrected run passed its then-current checks but omitted the supplied
no-refund fact. Its output is retained at
`audit-results/sprint3-examples-20261011-132510`. A new regression check caught
that omission. Final local run
`audit-results/sprint3-examples-20261011-132728` passed after one repair and
preserves the no-refund fact, policy, requested date/condition and unknown start
event without a signing placeholder. Its specification and both raw drafts were
retained with owner-only permissions. It created no action or treasury entry.

The supported workflow's model record remains tag-based; the digest identity in
the benchmark comparison does not retroactively certify workflow continuation.
BE-39 covers that separate limitation.

Latest verification: 45 focused practice, business-discovery, example-runner and
benchmark tests passed. Repository Black/Prettier formatting and generated-code
catalog checks passed. The new clone used the existing installed maintenance
tools without copying credentials or company data. No frontend feature changed;
the complete integration audit remains BE-41.

The supported task guide and final reply are available for owner usefulness
review. The final reply still uses an unrequested report heading and groups the
known no-refund status under remaining unknowns; assess that presentation honestly.
Contract success does not mean every wording choice is useful or establish broad
transfer competence.

## Unfamiliar scenario probe: fictional greenhouse inspection

The additional greenhouse-controller exercise uses a different scenario and the
exact existing evidence-summary rubric. Its frozen facts include five expected
checks, four passes, a missing inspection reminder and unknown cause, due time
and reproduction steps. Crop condition, watering results and sensor accuracy
are not supplied; no controller action is authorized. This is one bounded
scenario transfer, not certification of greenhouse expertise.

The first run (`20261011-132918`) passed its narrow checks but echoed an unrelated
14-day policy from a return-specific instruction included in every practice
prompt. That output is retained as a review failure. The instruction is now
limited to replies. A regression rejects this observed policy contamination in
evidence summaries unless that duration is actually supplied.

The next run (`20261011-133036`) failed the unchanged explicit-cause-unknown check
after one repair: it listed the cause beneath Unknowns without an explicit
unknown statement. Both raw failures remain saved. Evidence-summary prompting
now requests explicit statements for unknowns without weakening that check.

Final local run `audit-results/sprint3-examples-20261011-133147` passed on its first
draft. It preserves counts and the missing reminder, explicitly labels the cause,
due time and reproduction steps unknown, and requests those details for private
review before another test. It adds no controller action or crop/sensor finding.
Its specification and raw response are retained privately. No action or treasury
entry was created. A self-evaluation note remains a presentation issue for owner
review; it is not evidence of correctness.

Final focused verification: 48 tests passed. This includes a generation-path
regression asserting that evidence prompts exclude the reply-period instruction,
preserve the summary contract and still produce a reviewable sample. Targeted
Bandit medium/high findings: none. Final repository Black/Prettier formatting,
generated-code catalog and whitespace checks passed after the final prompt additions.

## Review boundary

Review whether the guide helps a beginner perform the three known operations
without needing invented controls. Review whether the reply accurately preserves
the return rule, asks for the missing facts and avoids an invented period start or
approval. Assess every original rubric check separately; contract success does not
record usefulness acceptance.

BE-35's examples are prepared for owner review; the story is not Done. The
ceramic-bowl probe transfers within support; the separate greenhouse scenario is
the unfamiliar-scenario example. Owner assessment determines usefulness under
the preserved exact rubrics; neither scenario establishes general competence.
No spending, publishing, customer contact, model training, execution of
generated code or new company authority was added. Generated evidence remains
private and follows the existing 30-day retention boundary; raw outputs are not
committed. Durable hashes and review findings are separate from those bytes.
