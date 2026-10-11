# BE-35 — useful private work, first review batch

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
Production prompts are unchanged.

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

## Review boundary

Review whether the guide helps a beginner perform the three known operations
without needing invented controls. Review whether the reply accurately preserves
the return rule, asks for the missing facts and avoids an invented period start or
approval. Assess every original rubric check separately; contract success does not
record usefulness acceptance.

BE-35 remains In Progress until useful examples and owner assessment satisfy the
story. No spending, publishing, customer contact, model training, execution of
generated code or new company authority was added. Generated evidence remains
private and follows the existing 30-day retention boundary; raw outputs are not
committed. Durable hashes and review findings are separate from those bytes.
