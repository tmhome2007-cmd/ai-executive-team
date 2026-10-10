# Pre-Sprint 3 foundation audit

10 October 2026. Baseline: merged Sprint 2 main `b5fb17f04ed3411e2f37278e5d20bdfcddb782f0`. Audit work is isolated on `codex/pre-sprint-3-audit`. This is a bounded code/design review and reproducible local verification, not proof that every bug or model failure has been eliminated.

## Scope and method

Reviewed the conceptual model, workflow states, owner API/authentication, source provenance, practice history, approvals/treasury/capabilities, recovery, organization/fiction separation, voice assets, startup/audit tooling, logging/retention and browser trust boundaries. Read the relevant modules and existing failure-path tests; added adversarial regressions where the review found gaps. Tested disposable SQLite, synthetic keys and model responses, temporary workspaces and a separate production dashboard. Real Docker confinement and local Ollama inference are included. No real business execution, publishing, customer contact, Telegram messaging or spending is authorized by this audit.

`./company audit` now includes all eight feature browser suites, not just a Chromium launch check. It builds a clean temporary dashboard, chooses a free loopback port, intercepts API traffic into test fixtures/disposable APIs and stops only its own server. Synthetic model tests exercise application controls; the local Ollama smoke checks availability/inference, not every executive's reasoning quality.

## Conceptual findings

The domain map remains in [CONCEPTUAL_SYSTEM_AUDIT.md](CONCEPTUAL_SYSTEM_AUDIT.md). Its original baseline is historical; this audit adds merged BE-18/19 and current verification.

| Context | State/authority invariant | Audit assessment |
|---|---|---|
| Direction | Goal and decision are distinct; direction approval precedes preparation | Existing controls and regression coverage retained |
| Execution | Proposal, action approval, current policy/capabilities/budget, claim and result are separate | No avatar, board movement or model text grants execution authority |
| Evidence | Registered/owner-confirmed sources are not independent corroboration | Provenance/freshness and uncertainty remain visible |
| Practice | Research → approved exercise → sample → owner review → retained revision | No tools, launch, spending or trained-model competence follows from a passing review |
| Recovery | Completion must belong to the current claim; uncertain external effects require reconciliation | Fixed missing completion-version checks for research/initial practice |
| Organization | Capacity assignments are records, not autonomous employees | Employee lifecycle and task/goal checks remain enforced |
| Fiction/presentation | Profiles, relationships and voice preferences do not establish business facts | Separate tables/endpoints; neural voices currently provide fixed auditions only |
| Treasury | Funding, commitments, spending and refunds are distinct | Revenue/profit and customer delivery remain unimplemented |
| Operations | Local single-owner app; awake machine required for scheduling | Launcher preserves key/data; audit now covers complete browser workflows |

### Use-case and acceptance corrections

- UC-07 recovery: a stale successful or failed worker must not replace the current research/practice record or append a sample. Completion now checks its claimed version in the update transaction.
- UC-10 voice comparison: finite duration and advancing playback are checked, rather than player visibility alone. Remote audio remains blocked by CSP. Generated conversations still do not use the neural audition engine.
- UC-11 audit: a healthy browser executable is insufficient evidence that the application flows work. The eight browser suites now run from the same command against the temporary production build.
- UC-12 privacy: test logs must not enter the normal application log directory. Audit sets a temporary `LOG_DIR`; normal runtime retains its existing `logs` default and 30-day generated-artifact policy.

## Fixed findings

| ID | Finding and consequence | Correction / regression |
|---|---|---|
| A-01 | `finish_stage` ignored `claimed_version` for research and first practice generation, unlike revisions | Transactional completion-version guard; stale success/failure leaves state, output and sample history unchanged |
| A-02 | Non-ASCII API-key guesses caused string `compare_digest` to raise in middleware/authentication | Constant-time byte comparison; malformed guesses receive 401/429 and a correct owner key remains usable |
| A-03 | Audit launched Chromium but omitted the application browser suites | Eight feature suites now run against an isolated production dashboard and disposable API data; readiness failures fail the audit |
| A-04 | Test processes could append to the normal application log | Configurable log directory shared with retention; audit uses its disposable directory |
| A-05 | Public-reader malformed ports could escape its error handling; redirects/stream failures could leave responses open | Invalid ports rejected before networking; redirected and failed responses closed; raw transport exception details withheld |
| A-06 | Standalone browser fixtures had stale key/roster assumptions and fixed origins | Current synthetic key and roster shapes, current short-review/full-report controls and per-run dashboard origin, keeping privacy/text-safety assertions |

Authentication coverage tests verify all operational OpenAPI paths refuse unauthenticated requests, including inherited router authentication. Root/favicon and framework-generated documentation remain intentionally public. Secret files are Git-ignored; no `.env`, database, backup or generated log is tracked. Existing `.crewai/` local material is untouched and now ignored, alongside `.env.*` variants (the public `.env.example` stays tracked).

## Privacy and security boundaries retained

- Owner key stays in browser memory, not browser storage or media URLs. Browser tests verify storage/URL privacy and safe rendering of model/source text.
- CrewAI tracing remains forced off before framework use. Telegram is disabled for local audit; no production credentials are copied or printed.
- Source reads validate public URL destinations/redirects and bound content. This is not proof of race-free network confinement against DNS rebinding; dedicated egress controls remain a deployment requirement.
- Optional Kokoro packages are isolated and pinned; fixed model assets are digest-verified. Auditions contain a public sentence, not company conversations. Downloads contact the asset/package hosts; installed local auditions require no cloud speech submission.
- Generated logs, screenshots and registered sync exports use 30-day age retention. Domain/approval histories remain retained; optional encrypted backup exports do not encrypt the live SQLite database. No production encryption key or backup was changed.
- Docker tests verify non-root/offline/read-only execution and host-file/symlink boundaries. They do not certify resistance to every kernel/daemon escape.

## Next-sprint candidates, not audit failures

1. Useful private deliverables: agree on a rubric and representative examples; measure whether revisions improve the specific sample without claiming learned competence.
2. Buyer/demand evidence: platform rules alone cannot select a profitable business. Require relevant evidence and source-backed comparisons within the owner's €0/no-launch constraints.
3. Traceability from demonstrated practice to a proposed business action: define explicit links before adding implementation; preserve separate approval and budget gates.
4. Commercial accounting and delivery: design receipts, fees, refunds, net results and external-effect reconciliation before any commercial launch.
5. Voiced conversations/3D office: separate new scope; current accepted auditions and profiles are not a complete speech/3D system.

Board templates and dated sprint records remain distinct: the seeded initial Development roadmap covers BE-01–14; later Sprint 2 acceptance is in the sprint documents. Creating a board never imports completion authority from Markdown. Do not silently mark live cards Done or overwrite owner-edited records during an audit.

## Residual issues outside present remediation

The dependency scan still reports four ChromaDB advisories with no fix versions in the tested dependency set. They remain visible in raw reports, separately classified only when IDs/package/no-fix status exactly match the known set. New findings or published fixes fail the project checks. No ignore list or incompatible dependency removal is used.

Production deployment isolation, encrypted off-device restore/key management and provider-specific idempotency need verification on their intended target. The audit does not invent evidence for those conditions. They are separate from the fixable local findings above and from the owner's accepted Sprint 2 scope.

## Verification evidence

Final post-fix run: `audit-results/20261010-145734/summary.json`, **PROJECT CHECKS: PASS**. The runner records the baseline Git HEAD and uses the current working tree; fixes were verified before their commit.

- Backend: 167 tests passed, including opt-in real Docker; 150/150 foundation checks passed.
- Python compatibility and medium/high Bandit gate: passed. Low Bandit findings are outside that configured gate.
- Optional voice lock scan: no known vulnerabilities. Main Python scan: four known Chroma findings with no fix versions, not a clean result.
- Frontend: clean install, review-summary/native-glob tests, lint, production webpack build and CSP checks passed. Existing image-optimization lint warning remains. npm audit: zero vulnerabilities.
- Browser: dashboard, agile, experiments, organizational, operating, review, business-discovery and people/voice suites all passed. This includes actual HTML audio duration/playback, remote-media exclusion, history/approval boundaries, safe text, mobile layout and memory-only keys.
- Chromium runtime and local Ollama greeting inference: passed.
- Final diff whitespace and changed-module compilation checks passed.

After the run, the server log filename was separated from the dashboard test log filename to avoid shared output files; documentation and ignore rules were updated. Earlier unsuccessful expanded runs are retained in ignored `audit-results` directories; they revealed fixture drift and are not treated as passing evidence.
