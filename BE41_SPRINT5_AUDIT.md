# BE-41 — final Sprint 5 integration, security and privacy audit

Current status: owner accepted the documented bounded Sprint 5 scope on 11 October
2026; merged via [PR #50](https://github.com/tmhome2007-cmd/ai-executive-team/pull/50). Earlier pending/
not-merged entries below describe their original evidence stage. See
[closure record](SPRINT_5_CLOSURE.md); known security/model-quality limits remain.

11 October 2026. Tested implementation commit:
`3d924cddfc15bd31a5b4c6d07a918d0aa8db9d97`, branch `codex/sprint-5-completion`.
Later closure changes are documentation only. The checked-in
[verification manifest](docs/planning/be41-verification.json) records the checks,
source hashes and private-log hashes. Reports: `audit-results/20261011-183332`.

**33 stages passed; zero project-check failures; one dependency stage remains
UPSTREAM. This is not a clean security release gate.**

- 289 backend tests passed, zero skips, including real Docker integration.
- 150/150 foundation checks passed.
- 15/15 production browser feature checks passed, plus browser startup/runtime.
- Python dependency compatibility, pinned Docker image and code maintenance passed.
- Bandit: zero medium/high findings; 16 low findings remain visible.
- Voice dependency audit passed. Frontend clean install, summary/glob tests, lint,
  production build, API policy and dependency audit passed; npm reports zero
  vulnerabilities. The existing image-performance lint warning remains.
- A separate real tool-free Ollama greeting returned “Hello!” using installed
  llama3.1:latest, digest `46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e`.
  The audit now uses native local HTTP generation after metadata verification,
  avoiding CLI behavior that can implicitly download an absent model. No download,
  cloud fallback, tools or usefulness assessment occurred in this greeting.

## Relationships and boundaries reviewed

Domain tests cover source/rubric snapshots, sample/review lineage, feedback
corrections, accepted procedure support, withdrawal/revocation and model identity
changes before continuation and during generation. Concurrent continuation has one
winner; stale controls refresh current eligibility. Cached output reuse requires
its recorded prompt and model identity. Historical missing identity stays unknown.
Private TXT/Markdown bytes preserve the saved sample; exports do not grant approval.

Authorization, private success/error headers, literal untrusted text, bounded
source reads, mobile navigation, hidden-panel polling and draft retention passed.
The complete private-work scenario preserves earlier bytes and assessments,
requires fresh review after revision and leaves company action/resource/execution/
capital records empty. Existing generated company artifact retention remains 30
days, with durable review/approval provenance preserved; expiry is not forensic
erasure. Tests cover retention and do not use an existing company database.

The audit isolated SQLite, logs, workspace, framework storage, keys and sync data.
Its dashboard was a clean temporary copy on its own loopback port. Existing apps,
keys, identities, voice preferences, company data and the original checkout were
preserved. Owner-only review reports remain local and must stay private; runtime
artifact retention does not certify removal of every developer evidence copy.

## Findings and limits

The Python scan reports four existing Chroma advisories with no reported fix
versions: PYSEC-2026-311, PYSEC-2026-3813, PYSEC-2026-3814, PYSEC-2026-3815. They were
not suppressed. Source records, private-only operation and passing authorization
tests do not remove these dependency findings or authorize production deployment.

A collapsed feedback-panel browser failure was corrected by opening the panel in
the scenario before asserting visible comparison text. The failed report remains
at `audit-results/be37-a31328eda0704dc9a16d1970f7ce4bfa`. A real demo shutdown check also caught a duplicate termination attempt that left
stale runtime metadata after its servers stopped. Commit 3d924cd removes the
duplicate and reaps only owned children; two focused tests and real startup/shutdown
verification passed. The first complete audit and observed cleanup failure remain
at `audit-results/20261011-182520`; the final complete audit was rerun on the fix.
Earlier Sprint 5 model and workflow failures remain in their documented private reports. No check or rubric
was weakened to obtain passing results.

Most generation-path tests use synthetic inference. BE-35 real examples expose
freeform factual/presentation failures despite a 30/30 narrow benchmark result.
Resolved manifest identity and selected settings do not guarantee deterministic
answers, and changes restored between identity observations remain undetectable.
Owner usefulness and new-card clarity acceptance remain outstanding. This audit
is bounded automated evidence, not exhaustive security or a commercial approval.
