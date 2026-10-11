# BE-34 — retained quality baseline and failure analysis

11 October 2026. Prepared for owner review; not Done or merged.

The retained JSON-mode baseline has 24 passed, 6 failed, 0 transport errors and
0 incomplete attempts out of 30. All six failures were inspected. Three are
literal wording mismatches; three substitute policy language for the supplied
fact. These are two repeated output patterns, not six distinct failure modes.

## Exact failures

| Attempts | Fixture / repeats | Checker finding | Analysis |
|---|---|---|---|
| 1, 2, 3 | task-results / 1–3 | Supplied fact not covered: four passed | Findings say “Four out of five checks passed”. The numerical meaning is preserved, but the required contiguous phrase is absent. Keep all three failures under the frozen rubric; semantic adequacy is a separate human assessment. |
| 7, 8, 9 | support-draft / 1–3 | Supplied fact not covered: 14 days | Findings repeat instructions about citing records, causal conclusions and quotations. The 14-day rule appears only in unknowns. The answer does not present the supplied rule as a finding. This is evidence displacement, not just alternate wording. |

All six have valid bounded JSON and preserve the named unknown. None has an
additional recorded checker issue. This does not establish that their proposed
next actions are useful or that all passing answers are correct. For example,
the first pattern recommends reviewing system logs that were not supplied.

The shared quality policy dominating the support response is a plausible prompt
interference hypothesis. It is not a proven causal diagnosis. BE-35 should test
clear separation of instructions and supplied facts against the frozen baseline,
then assess usefulness separately. Do not change required phrases or move
coverage checks across fields to raise this score.

## Evidence and reproducibility

Work starts from plan commit `269a92a6b59f70c5df8f370e654c798621300dc7` in a
separate workspace checkout, branch `codex/sprint-5-be34`. GitHub PR #49 was
verified open and unmerged, based on main `49f20ff0266118e41115b0ab33eea07451e68aec`.
The older nested checkout and active company's credentials/database were preserved.

Both original reports and their 60 per-attempt snapshots were found in the
development checkout. Every snapshot matches its report entry. All attempt
identities are distinct and cover ten fixtures with three repeats. Dataset,
prompt and model identities match the planning summary. Reassessment reproduces
every saved error. Private copies remain ignored under `quality-results/`, with
owner-only file/directory permissions and the existing 30-day retention boundary.
They are not committed or promoted into durable raw-output storage.

The original reports use checker hash
`9e1c5e14157ab56ba8e1a7af689ce9ef05911e81edcc3789c40e71cb7a367495`.
The planning summary uses current hash
`5d3360ce26f9e52d8da1b24c87c1efdecc22c963f65717ffb3d6fa3d5a17e426`.
Previously retained derived reports `7354f08a21c0432b8a60347c0481b5ea` and
`120c1af4dd0c4542b4f8546c2b7a3c90` explain that provenance: they identify the
original source runs and use the current checker. Original reports were not edited.

Fresh rechecks on 11 October retained the same results:

| Mode | Passed | Failed | Errors | Incomplete | Denominator |
|---|---:|---:|---:|---:|---:|
| Unconstrained retained outputs | 0 | 30 | 0 | 0 | 30 |
| JSON-mode retained outputs | 24 | 6 | 0 | 0 | 30 |

The two new derived runs share dataset, checker and rubric identities. Prompt
and model are unchanged; response-format configuration differs, as intended.
This is a comparable **reassessment of retained answers**, not a new inference
baseline. Loopback Ollama was unavailable (`URLError`), so no fresh generation
or current installed-model verification was performed. No model was downloaded.

The frozen rubric is `fictional-json-contract-v1`. Model identity is the recorded
`llama3.1:latest` digest
`46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e`.
Recorded settings: temperature 0, prediction limit 400, context 4096. Repeated
answers at temperature 0 do not establish broad reliability.

Machine-readable hashes, report checksums, attempt classifications and recheck
references: [be34-failure-analysis.json](docs/planning/be34-failure-analysis.json).
The dataset, checker, prompt snapshot and original reports remain unchanged.

## Validation and next step

Six existing benchmark regression tests passed. These cover comparability,
local-only transport, immutable private snapshots, interruption and prompt replay.
No production prompt or executable company workflow changed.

This analysis is available for review; BE-34 remains In Progress. A fresh baseline
remains pending local Ollama availability. BE-35 can use the retained comparator
with that limitation explicit, but must obtain real local outputs before claiming
prompt improvement. Owner usefulness assessment, acceptance and authorized merge
remain required. Budget and permitted loss stay €0.
