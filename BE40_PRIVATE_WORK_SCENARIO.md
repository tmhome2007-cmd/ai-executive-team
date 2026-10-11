# BE-40 — complete fictional private-work scenario

Run `./company review` for exact navigation and sample data, `./company review
--check` for the disposable automated scenario, or `./company review --demo` for
the four fictional recovery cases. These commands do not read, generate, replace
or display a company key. The existing configured company still uses its original
key via `./company start` or `./company key`. No database reset is needed.

The complete scenario uses [frozen fictional data](docs/planning/be40-scenario.json)
and the actual generation-stage, assessment, artifact and skill domain functions.
Only inference and assessments are synthetic; they never represent owner consent.

| Transition | Verified evidence |
|---|---|
| Supplied facts → approved exercise → draft | Frozen facts/rubric, saved sample, no prefilled assessment |
| Draft → failed exact-rubric assessment | Specific missing-unknown feedback retained |
| Feedback → revision | New sample references the first sample and exact feedback; facts/rubric unchanged |
| Original/revised exports → comparison | Original bytes unchanged; TXT/Markdown diff available |
| Revision → fresh passing assessment | Improvement uses the same rubric and the recorded failure |
| Two distinct passing exercises → proposed procedure | Unassessed/proposed work cannot be bound as an accepted skill |
| Explicit synthetic acceptance → third exercise | Accepted procedure can be reused, but its new sample is still unassessed |

The test verifies zero action, resource, execution and capital records wherever
those tables exist. No model downloads, cloud inference, websites, customer
contact, spending, publishing or generated-code execution occur in this scenario.
The separate browser scenario covers the owner-facing research/practice flow.
Earlier real local generation examples remain labelled in BE35_PRIVATE_WORK_REVIEW.md.

Validation: the complete scenario passed; all 17 targeted guidance, launcher and
scenario tests passed. Two additional audit-model tests verify that an unavailable
model cannot initiate generation and the greeting uses bounded native loopback
HTTP without proxies or redirects. Full integration results are recorded separately.

The demo uses temporary frontend/data, synthetic inference and no scheduler. Its
only allowed mutations are the four example continuation controls. Ctrl+C stops
its owned process groups and cleans temporary files; live company apps and data
are untouched. Failed startup logs are private under audit-results. The guide and
demo are review aids, not usefulness acceptance, permission renewal or a merge.
