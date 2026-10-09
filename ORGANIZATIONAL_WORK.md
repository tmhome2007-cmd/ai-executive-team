# Organizational work — BE-04 through BE-07

Open **Organizational work** in the owner-unlocked dashboard after restarting the
backend and rebuilding/restarting the frontend on `chatgpt/foundation-hardening`.
All APIs below require `X-API-Key`. No feature grants authority through model text,
board assignment, a resource fulfillment note or a discussion message.

## BE-04: dated evidence

Register a source with its title, reference, summary, observation time and optional
expiry. Sources without expiry have **unknown** freshness. Expired sources are stale;
owner confirmation does not turn them into independently verified evidence. Source
contents and links are immutable; register corrections as new sources. Verification
review uses the current source version and rejects stale reviews.

Link sources to a decision, experiment observation or published discussion message
as context, supporting evidence or contradiction. A linked context alone is explicitly
reported as lacking supporting evidence. Missing and conflicting evidence stays
visible. Contradictions are owner-linked; automatic fact checking is not implemented.
References are stored as text and never fetched. URLs with credentials, query strings
or fragments are refused to avoid storing token-bearing links.

Normal new decisions retain their supplied input as unverified context when no
explicit source IDs are given. Observation submissions retain dated, owner-recorded
evidence. Existing legacy decisions are not given fabricated sources. Optional
`source_ids` on meeting/observation APIs link registered records. Structured discussion
prompts include each source's date, freshness and review label. Repeated requests
cannot silently replace their original linked source set.

APIs: `GET/POST /evidence`, `GET/PATCH /evidence/{id}`, `POST /evidence-links`,
`GET /evidence-for/{decision|observation|discussion}/{id}`. Lists are bounded and
paginated; evidence summaries return at most 100 links with a truncation indicator.

## BE-05: reviewed executive plans and workload

Create an active company goal and a **Company** agile board first. On the Plans tab,
ask a selected executive to propose a plan. The existing role, goal and personality
are retained. Planning uses no tools and returns a validated task graph: assigned
executives, acceptance criteria, dependencies and estimated costs. Invalid JSON,
unknown executives, missing dependencies and dependency cycles fail closed.

Review the actual proposal and enter an owner review note before approving it.
Approval creates company cards and scheduled work records atomically. Estimates
must fit available treasury by currency at approval and dispatch; approval does not
reserve or spend money. Separate financial actions still require treasury-aware
approval and their existing role/resource/goal/execution gates.

The scheduler dispatches up to two eligible recommendations every 15 minutes; the
owner can also use **Run approved planning tasks**. Dispatch requires an active goal,
a ready card with matching assignment/goal, available estimated budget, reviewed
completed dependencies and no running work for that executive. Concurrent claims
cannot dispatch a work record twice. A recommendation is persisted as a pending
decision and moves its task to Review. Accepting the work marks the card Done but
**does not approve the decision's direction or any business action**.

Owner edits made during/after reasoning are not overwritten by stale completion or
review. Interrupted/failed claimed work becomes Blocked and is not automatically
replayed. Review it manually and create a new scoped plan/task if another attempt is
needed. Durable successful model steps and persisted plans are reused on exact retries.

APIs: `GET/POST /plans`, `POST /plans/generate`, `GET /plans/{id}`,
`POST /plans/{id}/review`, `POST /planned-work/{id}/review`,
`POST /planned-work/dispatch?max_items=2`, `GET /executive-workload`.
An owner may submit a validated structured proposal directly through `POST /plans`;
that still starts in Proposed and requires review.

## BE-06: published executive discussion rounds

Select participants including the CEO, provide the question and actual evidence,
and optionally link registered sources/an active goal. Each participant publishes a
proposal, a critique and a revision; the CEO publishes the final synthesis. Prior
speeches are explicitly unverified recommendations and are not added to the evidence
guard as new facts. Canonical executive personalities shape each contribution.

The database retains speaker, round, phase, body, capture time, profile snapshot and
source links. These are published task outputs, not recordings of speech or hidden
reasoning. All rounds must complete before a parent decision/messages are published.
A failed round publishes no partial meeting; interrupted/uncertain checkpoints require
review. Exact completed retries reuse the stored discussion. Changed inputs/speakers/
sources cannot reuse the same run key. Generated owner-consent claims are guarded;
the final decision begins Pending and follows normal owner approval.

Open any structured discussion by its decision ID. Legacy meetings without structured
rounds return an explicit empty set. Source links attach to each message; context
links do not establish independent corroboration.

APIs: `POST /discussions`, `GET /decisions/{id}/discussion`.

## BE-07: scoped capability inventory

Start from an approved access/credential/plugin/service/data resource request. Provide
an exact target, explicit scopes and executive roles. Status is **Provided** until a
health check verifies a supported provider. Existing fulfilled notes alone do not
verify access. Provisioning records metadata only; never paste a token into the form.

Supported checks:

- **GitHub:** exact `owner/repository`, scopes `repo.read` and/or `repo.write`, secret
  reference `GITHUB_TOKEN` only. Set the token privately in the backend's environment.
  Verification makes one read-only, five-second HTTPS request to GitHub's fixed API,
  refuses redirects, and checks repository pull/push permissions. No issue, commit,
  purchase or repository mutation is performed. Permission health does not mean a
  GitHub execution tool has been added to an executive.
- **Browser:** exact host, scopes `page.read`/`page.interact`, no secret. It must already
  be configured in `ALLOWED_BROWSER_DOMAINS`. Verification launches/closes local
  Chromium without visiting the target. This establishes runtime readiness and a
  configured host, not successful website login/access or a completed interaction.
  Existing browser safety/role policies continue to apply.
- **Manual:** records other requested/provided connector scopes without claiming a
  implemented adapter or verified health. Manual grants cannot satisfy execution gates.

Checks expire after 30 minutes; the running server refreshes verified grants every
15 minutes. Scope/target/role/reference metadata is immutable; changed access needs a
new resource request. Revocation cannot be undone by a simultaneous health check.
Tokens and provider error bodies are not stored. A keyed credential fingerprint
tracks rotation internally and is excluded from API responses/activity events.

Bind required access to a **pending** action before approving it. The approval seal
covers grant identity/scope/target/role/version/status/fingerprint. Verification
refreshes with unchanged authority do not invalidate it. Rotation, revocation or
changed authority requires renewed verification/approval. Claiming execution checks
health freshness, role/scope, active linked resource/goal and current credentials
again. Browser actions also check the exact host, current configured allowlist and
whether a click requires `page.interact`. Scoped browser resources in preparation
lineage are mandatory even without a manually bound requirement.

Existing actions without inventory-backed requirements retain their existing static
role/owner/resource/execution controls. The inventory is an additional scoped gate;
it does not replace the sandbox, configure arbitrary connectors, grant new executable
roles or inject credentials into shell/file tools. Future provider execution adapters
must consume these gates explicitly.

APIs: `GET/POST /capabilities`, `POST /capabilities/{id}/verify`,
`POST /capabilities/{id}/revoke`, `POST /actions/{id}/capabilities`.

## Storage and verification scope

All new records live in the same private SQLite database and are included in whole-DB
backups. They are not currently part of the cross-machine sync payload. Do not rely
on a sync export to migrate the new organizational records; use the encrypted database
backup/restore process. Existing history is preserved and schema creation is idempotent.
The activity ledger records transitions/identifiers without copying credentials,
prompts, source summaries or discussion bodies.

Checked-in roadmap/new-board templates mark BE-04–07 **Review** after verification.
Existing runtime boards are not overwritten during seeding. Move their cards to Review
when reviewing this implementation against the original test database; Done requires
owner review.

The combined tests use real SQLite, authenticated FastAPI routes and real CrewAI tasks
with synthetic models. They cover source freshness/conflicts, concurrent/dependent
claims, budget/goal/role gates, stale owner reviews, durable model output, personality
snapshots, unsupported consent, failed rounds, scope/host enforcement, credential
rotation, provider declines and verification/revocation races. Provider requests are
mocked; no real credentials or business side effects are used. Real local Ollama answer
quality and live provider permissions still need owner trials with chosen test inputs.

Run the normal full isolated local runner from this branch:

```sh
.venv/bin/python scripts/local_audit.py
```

With the production frontend built/running on `127.0.0.1:3000` and its API base compiled
to `http://127.0.0.1:8001`, the feature UI smoke can run independently of the company
backend:

```sh
.venv/bin/python scripts/organizational_smoke.py
```

It intercepts all API calls into disposable test storage, uses synthetic model
responses, verifies all four owner workflows, checks safe rendering/mobile layout and
asserts that directions stay pending, actions do not execute, and no money moves.
Unresolved upstream advisories remain in their separate register; this sprint does
not clear the production/security release gate or merge main.
