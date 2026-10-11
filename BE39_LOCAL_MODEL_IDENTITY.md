# BE-39 — local model identity

Implemented for owner review on 11 October 2026; not Done or merged.

New supported private research, practice and revision runs record the resolved
local Ollama manifest digest and configured tag, endpoint, temperature, token
limit, timeout and response mode. Structured revision/task-guide calls record
their effective overrides. Only these allowlisted settings are retained; prompts,
API keys and arbitrary SDK parameters stay out of inspection metadata.

The resolver uses the read-only [Ollama model-list API](https://docs.ollama.com/api/tags).
It accepts loopback HTTP only, disables proxies and redirects, bounds response
size/time and handles CrewAI's `/v1` endpoint normalization. Lookup does not perform
inference, download a model or fall back to a cloud provider.

Continuation resolves identity before claiming another attempt. A changed digest,
tag or recorded configuration, or an unavailable model, produces a fixed reason
and leaves the old brief/version, samples and checkpoint intact. Identity is checked
again before generation, repair or cached reuse, and after checkpoint completion
before publication. New metadata appears under Prompt and model versions.

Existing rows receive nullable schema columns only. Their identity remains unknown;
continuation and the cached-result helper reject reuse without recorded identity.
No current digest is backfilled into historical runs.

## Actual verification

- 63 targeted backend tests passed: resolver validation, missing/ambiguous digests,
  secret-bearing/nonlocal endpoints, unavailable daemon, `/v1` normalization,
  changed tag/digest/configuration, unavailable continuation, legacy migration,
  retained metadata, cached recovery and a retag during inference blocking publication.
  Previous interruption, permission-change, stale-control and concurrency checks passed.
- Production build, run-inspector browser check and business-discovery browser check
  passed with disposable SQLite and explicitly synthetic identity/inference.
- A separate real read-only lookup resolved `llama3.1:latest` to
  `46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e`.
  This was metadata inspection, not a new generation or usefulness assessment.
- Repository formatting/catalog and whitespace checks passed; targeted Bandit
  found no medium/high findings. Full Sprint 5 audit remains outstanding.

The initial real lookup caught the SDK's `/v1` normalization mismatch. A production
browser failure caught a synthetic fixture missing an identity mock. Both failures
are retained alongside the corrected results in the private evidence record.

A recorded identity is provenance, not a guarantee of identical generated text.
Unspecified settings remain SDK/server defaults. Tag checks are observations before
and after work, not an atomic lock on Ollama's model registry; a tag changed and
restored between observations cannot be detected by this mechanism.

See `docs/planning/be39-verification.json` for implementation identity and private
report locations. Owner usefulness review, implementation PRs, merges and Done
status remain pending. BE-36 concise owner review precedes the BE-40 acceptance flow.
