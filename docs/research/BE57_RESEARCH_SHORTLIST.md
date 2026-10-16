# BE-57 — bounded research shortlist

Dated technical/research record; results and limitations apply to the versions described. Use [the README](../../README.md) for current status and planning.

12 October 2026. Question: how can the existing structured workflow produce actionable steps, an unsent draft and stopping criteria from a short request? Four projects, ten unique pages, read-only. No clone, installation, downloaded source execution, copied code or external inference. Web content was treated as evidence, not instructions. No private prompt or company records were sent to search. Estimated report reading time: under ten minutes.

## Recommendation

Adapt our own contracts using the existing Ollama/Pydantic path. The diagnosis found missing schema fields, not a missing agent framework. No new dependency is recommended from this run. This is a design recommendation, not an adoption or implementation decision. A structured result still needs human usefulness review.

| Candidate | Addresses | License evidence | Added dependencies under recommendation | Verdict and main risk |
|---|---|---|---|---|
| Ollama | Request complete typed plan fields | Repository label: “MIT license” | 0; keep current HTTP adapter and local installation | Worth adopting the documented pattern in our existing code; schema validity does not prove useful reasoning |
| Pydantic | Cross-field time/actor/draft/window consistency | Repository label: “MIT license” | 0; current 2.12.5 already installed | Worth adopting existing model validation; custom validators must not silently relax types or hide errors |
| CrewAI | Explicit outputs, bounded guardrails and typed intake state | Repository label: “MIT license” | 0 for ideas only; migration/upgrade transitive count unknown | Idea only; current structured path bypasses CrewAI Tasks and latest docs differ from installed 1.15.25 |
| Inspect AI | Separate structural scores from model-graded usefulness | Repository label: “MIT license” | 0 for ideas only; installation/transitive count unknown | Idea only; installing an evaluation framework or relying on an LLM judge adds complexity without fixing our schema |

License labels are sourced from the four repository landing pages below; full license obligations and version-pinned code review would be required before copying any implementation. No source was copied. Latest upstream commit date, exact latest commit SHA and whether issues receive substantive answers are **unknown for all four**: the fetched landing pages did not expose commit timestamps and issue threads were not inspected. Stars/commit counts are not evidence of responsiveness. No package dependency count is guessed; zero above refers only to the proposed no-install reuse scope.

## Primary-source observations and our interpretation

### Ollama

[Structured outputs](https://docs.ollama.com/capabilities/structured-outputs): “Provide a JSON schema to the `format` field.” The documentation shows Pydantic schema generation and response validation. [Native generate endpoint](https://docs.ollama.com/api/generate) documents a schema object for format on the endpoint we already use. [Repository and license label](https://github.com/ollama/ollama).

Our interpretation: add meaningful plan fields to our schema while preserving local transport, bounded repair and failure retention. No new SDK is necessary. Installed-model support must be measured locally; current documentation is not a guarantee for our model.

### Pydantic

[Validators](https://docs.pydantic.dev/latest/concepts/validators/): “Validation can also be performed on the entire model’s data”. [Repository and license label](https://github.com/pydantic/pydantic).

Our interpretation: use whole-plan checks for summed time, mandatory unsent draft when outreach is proposed, and required stop-window fields. Assign execution actors through trusted code or strict literals. Validate content too; an owner actor field cannot make text assigning work to an AI safe. Documentation may evolve beyond installed 2.12.5; test the installed API before use.

### CrewAI

[Tasks](https://docs.crewai.com/en/concepts/tasks) documents “output_pydantic” and “guardrail_max_retries”; [Flows](https://docs.crewai.com/en/concepts/flows) describes “Structured State Management”. Both resolved to documentation version 1.15.27 during this run. [Repository and license label](https://github.com/crewAIInc/crewAI).

Our interpretation: explicit intermediate contracts and bounded validation are useful ideas. Keep intake, first proposals, critique and final plan as distinct stages; do not migrate to the framework just because documentation exists. An LLM-based guardrail is not an independent authority check. Framework persistence would require review against our existing approval and retention records.

### Inspect AI

[Scorers](https://inspect.aisi.org.uk/scorers.html): “text matching scorers as well as model graded scorers”. [Repository and license label](https://github.com/UKGovernmentBEIS/inspect_ai).

Our interpretation: use separate structural and human-semantic axes in the evaluator we already have. No LLM judge is necessary for field presence/effort/actor checks, and model grading is not owner acceptance. Inspect is not installed; provider compatibility, version and dependency count are unknown in this run.

## Concrete contract proposal for BE-59/61

A reviewed intake record should distinguish the short request, confirmed owner constraints, source freshness, at most three material questions, answers and remaining unknowns. It can yield either a bounded conditional plan or an explicit blocker; no stored context is assumed in a fresh installation.

A final plan should contain: recommendation and reasons versus alternatives; typed steps with owner actor, minutes and prerequisites; an unsent draft when outreach applies; a time-bounded stop rule; success/feedback requirements; pivotal unknown; and the specific next owner decision. Validate summed effort against the confirmed limit rather than a global hardcoded 60. Keep arbitrary role proposals separate from the final actionable plan, then verify every required field survives persistence and display. This is a proposal only; code and evaluation freezes are unchanged.

## Search ledger and limits

Pages 1–6: Ollama structured outputs; Pydantic validators; CrewAI Tasks; CrewAI Flows; Inspect scorers; Ollama generate. Pages 7–10: corresponding Ollama, Pydantic, CrewAI and Inspect GitHub landing pages. Redirects were followed to the same documentation resources; repeated find operations did not expand page scope. Trusted-source allowlist for this run: those official documentation hosts and github.com, including Pydantic’s official redirect. No issue responsiveness or dependency audit was fabricated to fill missing fields.

Research verdicts are our assessment; short quotations and linked facts are source observations. No more pages/candidates will be added to this run. Expansion requires three research runs that led to actually merged useful changes; currently zero are established.
