# Sprint 2 planning proposal — 9 October 2026

Owner-selected scope: BE-15 and BE-16. Both are implemented for Review on `codex/sprint-2-local-review`; owner acceptance and merge remain pending. BE-17–19 remain Backlog.

Sprint goal: make the company easier to run locally and its recommendations easier to review. The owner chooses the final sprint scope; these items begin in Backlog, not as a commitment to deliver all five.

| ID | Priority | Story | Acceptance examples |
|---|---|---|---|
| BE-15 | High | Simple local startup and testing | One documented entry point checks checkout, branch, services and ports; explains next commands; preserves existing database and key; never prints secrets. Owner can restart and audit without piecing together a large command block. |
| BE-16 | High | Short, evidence-first AI results | Findings, unknowns and next action are visible first; details expand on demand. Empty/conflicting evidence and missing prerequisites stay explicit; no invented owner approval. Owner reviews a fixed set of examples for readability. |
| BE-17 | Medium, discovery first | A measurable business experiment using existing goals/treasury/experiments | First map the existing workflow and identify any actual missing capability. Define one owner-chosen hypothesis, cost/risk cap, dated observation and success measure. Funding, forecasts and observed profit remain distinct. No real spending or external action during discovery. Implementation ticket only after the gap and acceptance example are agreed. |
| BE-18 | Low | Character presentation reflects existing identities | Review existing character profiles with owner; represent women and other established identities deliberately instead of assuming gender from a name. Preserve personality and Kai's appearance. Owner reviews every character in face and full-body views. |
| BE-19 | Low | Better character voice quality | Compare candidate voice solutions with a short sample and owner feedback before integration. Record quality, privacy, local/cloud behavior, installation and cost. Provider/egress choice remains explicit; no paid service or remote prompt transmission without authorization. |

Suggested first commitment: BE-15 and BE-16. Groom BE-17 alongside that work if capacity permits. BE-18/19 remain low priority as requested. 3D animation, autonomous employee tools and personal-life AI generation are separate future stories.

Work one coherent story at a time. Review acceptance examples before coding, verify with disposable data, and prefer a separate PR per feature. At the next retrospective record setup assistance needed, owner readability feedback and scope changes. Do not invent velocity or estimated completion dates from the previous sprint.

Implementation and acceptance steps: [SPRINT_2_LOCAL_REVIEW.md](SPRINT_2_LOCAL_REVIEW.md).
