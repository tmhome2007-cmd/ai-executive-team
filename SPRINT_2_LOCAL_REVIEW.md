# BE-15 and BE-16 — local workflow and short AI review

These two owner-selected Sprint 2 stories are implemented for review on `codex/sprint-2-local-review`. They are not marked Done or merged until owner acceptance.

## BE-15

`./company` is the single checkout-aware entry point for doctor/start/audit/key/help. It uses this checkout's Python, enforces local sandbox settings, preserves existing key/data, builds the current dashboard and owns only the two child process groups it starts. It refuses occupied ports instead of stopping unrelated servers. Clipboard copy uses the existing configured key and never prints it. Setup issues produce specific next steps; see [LOCAL_COMMANDS.md](LOCAL_COMMANDS.md).

Loopback Ollama probes reject remote endpoints, credentials, query strings and unexpected paths; redirects and proxies are disabled for probes. Child audit Python is explicitly selected, avoiding confusion from another terminal's active virtual environment. Dashboard builds use system fonts rather than downloading fonts from Google.

The existing local app was left running during verification. Its occupied ports were correctly reported. Cold-start process ownership/readiness/interrupt behavior is tested with synthetic child processes, not by restarting the owner's company. Owner cold-start review remains necessary.

## BE-16

Decisions, final meeting results, preparation reports, recorded contributions, discussion rounds, virtual-office meeting reports and next recommendations now share an evidence-first short view. Up to three literal excerpts per section show reported findings, unknowns and the proposed next action. Full original text remains expandable. No additional model call fabricates a summary; original database records/personality/approval state are unchanged.

Legacy/unstructured text is not reclassified as verified evidence; the display explicitly says when a section is absent. Excerpts are labelled as AI report claims and can omit additional detail, so full/source review remains necessary before approval. Blocking instructions, missing prerequisites, source conflict notices and owner-consent claims receive visible warnings. These format/phrase checks cannot establish truth or detect every misleading claim. Existing backend quality warnings remain visible.

The shared generation policy requests concise sections without omitting source quotations or safety prerequisites. Required role/meeting contracts still take precedence. Short rendering does not guarantee every future model response will be concise or evidence-supported.

## Acceptance review

1. Stop old apps yourself, run `./company doctor`, then `./company start`. Both services should run in one terminal and the existing key should unlock the dashboard. Stop with Ctrl+C and confirm unrelated apps remain untouched.
2. Open Decisions or a discussion round. Reported findings, unknowns and next action should be easy to locate; expand the full report to inspect the original evidence/details.
3. Try supplied-evidence, conflicting-evidence and missing-prerequisite examples. A missing detail must remain missing, a conflict must remain a conflict, and a blocked test must not be presented as executable.
4. An AI sentence claiming owner approval must not change the recorded approval status. Unsupported/legacy reports must not acquire a false “verified” label.

Automated checks cover launcher preservation/process safety, fixed review fixtures, mobile layout, text/key safety and approval-state invariance using disposable records. The Chromium feature test is `scripts/review_smoke.py`. The full local audit now includes `npm run test:review-summary`, also added to CI.

## Verified results — 9 October 2026

`./company audit` completed successfully with 130 tests (including real Docker), 150/150 foundation checks, pip compatibility, Bandit medium/high, frontend review fixtures/lint/build/npm audit, Chromium and local Ollama. Report: `audit-results/20261009-210113/summary.json`. Four unchanged unpatched Chroma advisories remain separate; no production sign-off. The existing screenshot image lint warning remains.

The separate `scripts/review_smoke.py` browser/API/SQLite test passed evidence and missing-prerequisite visibility, conflict/consent warnings, legacy/full-report access, unchanged approval status, mobile layout and text/key safety. A mobile badge-layout fix and prototype-heading guard were subsequently checked with the feature smoke/fixture test and lint. Local doctor confirmed the existing services and correctly identified occupied ports without stopping them.
