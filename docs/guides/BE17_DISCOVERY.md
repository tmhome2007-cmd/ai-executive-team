# BE-17: AI-operated business discovery

Dated technical/research record; results and limitations apply to the versions described. Use [the README](../../README.md) for current status and planning.

Owner direction, 9 October 2026: the AI company should research options and recommend the best fit, then eventually perform the work. The owner supplies oversight and approval, not an assumed professional skill set. No budget is authorized: total spend and permitted loss are both €0. A recommendation does not authorize launching an experiment.

## Existing foundation

| Capability | Existing implementation | Discovery implication |
|---|---|---|
| Persistent mission and planning | `memory/database.py`, `workflows/executive_planning.py` | Goals and tool-free planning already exist. Planning output alone does not establish current market facts or demonstrated competence. |
| Dated source records | `memory/evidence.py` | Research can cite immutable source records and retain gaps, conflicts and freshness. Owner confirmation is not independent verification. |
| Executive deliberation | `workflows/meeting.py` | Executives can compare supplied evidence with tool-free agents; their personalities do not confer tool access or factual authority. |
| Public-page reading | `tools/research_tool.py`, `workflows/daily_research.py` | Bounded public reads exist, but daily research uses fixed technology pages, not a tailored business search. |
| Approval, execution and results | `memory/experiments.py`, `memory/observation_jobs.py` | Action-linked experiments and bounded observation exist. Research should not require a fabricated executable action. |
| Treasury | `memory/database.py` | Funding, spend and refund exist. Sales revenue and realised profit accounting remain a later gap before real commerce. |

Verified on disposable data: the six existing experiment tests pass; experiments require an action; treasury rejects a revenue entry. No application database or credentials were changed.

## Actual next capability

A research brief and capability assessment should connect relevant evidence to a reviewable recommendation. Assess what the agents can do, rather than asking the owner to perform the proposed service.

For each required skill, record one of:

- **Demonstrated:** a dated, inspectable work sample passed defined checks with the available tools.
- **Needs learning/testing:** propose a bounded local exercise and observable pass criteria. Generating instructions or asserting expertise does not establish competence.
- **Missing access:** state the unavailable tool, data, permission or integration and request it separately.
- **Requires owner:** state any human responsibility or judgment the system cannot perform safely.

An agent may draft code or content without yet being able to deliver a reliable service. Learning means producing and evaluating practice outputs, preserving the evidence in existing memory; it does not mean automatically retraining a model or granting new tools.

## Proposed implementation acceptance example — owner review pending

Given an AI-operated, research-only brief with €0 budget and €0 permitted loss:

1. Compare at least three options using relevant dated public sources. Separate evidence of demand from assumptions; report insufficient evidence when necessary.
2. Show required skills, demonstrated samples, learning tests and missing access for each option. Include tools the company actually has and tasks it cannot yet perform.
3. Distinguish upfront spending, contingent fees and owner effort. Reject options requiring payment or an external commitment at this stage. Free access alone does not prove suitability or commercial permission.
4. Recommend one provisional option, or explain why none can yet be selected. Do not invent income forecasts, success probabilities or verified competence.
5. Propose a private, local practice deliverable, its checks and an observation date for owner selection. Passing it establishes only the measured capability, not customer demand or profit.
6. Persist the reviewed brief and evidence without approving an action, activating spending, contacting customers, publishing, registering accounts or calling paid services.

The initial hypothesis should be about demonstrated capability: “The agents can produce a useful deliverable for the selected option using available tools without spending money.” The specific deliverable, checks and observation date depend on the selected option and remain unapproved.

The owner approved implementing the research and practice workflow. The guided workflow is implemented and in Review; a business choice and owner acceptance remain pending. Sales/profit accounting, live delivery integrations and aggregate financial exposure belong to later stories before real commercial activity.
