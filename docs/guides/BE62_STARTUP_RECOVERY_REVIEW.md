# BE-62 startup recovery and BE-64 retention prerequisite

Dated technical/research record; results and limitations apply to the versions described. Use [the README](../../README.md) for current status and planning.

13 October 2026. Bounded implementation ready for review, not full acceptance or merge. Source through b9dff00 on codex/sprint-7-actionable-schema. No actual V2CHAT environment file or company database was created, copied or pruned.

## Startup and recovery

Explicit `./company init-local` creates private local configuration only in an empty installation. It refuses existing configuration, databases (including legacy vector databases), workspace artifacts and symlink destinations. Existing credentials are preserved. Normal `./company start` remains the launcher; initialization is never automatic. Placeholder keys are rejected. Port preflight distinguishes active listeners from closed connections.

An uncertain decision request now offers Refresh Decision History and explains that generation may still be running or already saved. Refresh never resubmits a decision. This is recovery guidance, not durable request identity, idempotency, cancellation or a complete job-status implementation.

The isolated launcher test exercised the real doctor/start/key paths with a fresh temporary configuration, production frontend and actual API database validation. Its clipboard callback was mocked, ports were changed because normal ports were occupied, and scheduling was deliberately omitted. It used disposable data and stopped only its own processes. Summary: audit-results/be62-startup/be3644a898e54e34aae2a281123d1abc/summary.json (source c7cf789). Two preceding failed test attempts remain retained. This does not certify real clipboard behavior, normal occupied ports, scheduled jobs or owner acceptance.

Production browser checks on 8a85a5c injected a network interruption and HTTP 500 into decision submission, then verified history recovery without another POST, unchanged pending decisions, mobile/key/XSS behavior. Evidence: audit-results/be37-491ec6ec2f1548f9a78d2f1659cf6ec7. Existing image-performance warning remains.

## Private experiment retention

Sprint 7 inputs, raw samples, semantic assessments and private logs now use existing 30-day retention primitives. Only recognized experiment folders and filenames are selected; ownership, symlink, hardlink and race guards apply. Summary/protocol metadata and hash receipts remain. Temporary-fixture tests verify expired byte deletion and preserved provenance, fresh files and unrelated artifacts. No pruning was run against real project files. Transfer sample selectors are reserved for the frozen protocol, not evidence of a completed transfer evaluation. Retention requires the existing pruning runner to execute; expiry is not forensic erasure.

## Verification and remaining work

Final backend suite on b9dff00: 374 tests, real Docker, no skips, all pass. Formatting, current catalog, diff checks and targeted Bandit medium/high pass. This is not a fresh full integration/dependency audit. Long-running request identity/status, scheduler checks, owner terminal/browser acceptance, final usefulness assessment and active-CI/known Chroma release dependencies remain open. BE-62 is partial review; BE-64 remains backlog with this prerequisite implemented.
