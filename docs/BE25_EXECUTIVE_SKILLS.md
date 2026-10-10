# BE-25 — versioned executive procedures

Executives can draft reusable private text procedures. Each proposed version references two exact passing owner reviews from separate structured exercises with the same rubric and different supplied facts. The owner accepts that version separately. A skill is a procedure reference, not model training, general competence, a capability grant or launch permission.

## Review locally

Stop your existing app terminal with Ctrl+C, then run `./company start` from this checkout. Your existing database and dashboard key are preserved; startup creates the three new skill tables.

In **Business research**, scroll to **Executive skill library**:

1. Select two passing reviews with matching rubric IDs. They must be separate exercises with different facts; multiple revisions of one exercise do not count.
2. Enter a short key (for example `private-summary`) and a name. Choose **Ask CSO to draft a proposed procedure**, or write and save one yourself.
3. Open **Procedure, prerequisites and exact rubric**. Inspect the actual source samples in their saved research histories. Accept the private procedure version if it is useful.
4. Open a new research-ready brief. Choose **Refresh accepted procedures**, then select the procedure. Its service, format and checks are filled in; supply a new audience/exercise and different facts.
5. Approve that private practice plan, generate the sample and review every check. Generation alone is not a passing result.
6. **Revoke version** blocks future generation/revision and publication. Earlier samples and reviews remain available.

Changing the key's procedure creates another version rather than overwriting the accepted one. A corrected source review makes the old version unavailable for future use, even if the correction still passes; propose and accept a fresh version referencing the corrected evidence.

The UI pages procedure versions in batches of 100; the practice selector can load older versions too. It lists the newest 200 eligible-review candidates. Existing records remain stored, and a saved practice plan keeps its exact version reference.

## Data and runtime boundaries

- `executive_skill_versions`: immutable procedure, prerequisites, limitations, exact review/sample/brief IDs, service, format, rubric and version.
- `executive_skill_decisions`: append-only proposed/accepted/revoked state decisions with UTC time and optimistic state version. These control private procedure reuse only; action approvals remain in the existing ledger.
- `practice_skill_bindings`: immutable association between a newly approved exercise and one exact accepted version.

Practice approval and the skill binding commit in one transaction. Rejected/stale/incompatible bindings leave the brief research-ready. The generator receives the procedure as a method hint; the approved new facts and specification remain authoritative. Existing local tool-free CSO inference, output validation, step checkpoints and execution lock remain in use. Source sample text is not copied into the new practice prompt. The procedure is rechecked on claim, before inference and before publishing a generated sample; revocation during inference prevents publication. Cleanup still records interrupted/failed work without publishing it.

Already running local inference cannot always be cancelled immediately, but its result is withheld after revocation. Previously recorded output remains private historical evidence. Skill definitions and decisions are durable company records, unlike transient generated audio/files. No cloud provider, new dependency or upstream code is introduced; budget and permitted loss remain €0.

## Owner-authenticated API

- `GET /skills?limit=50&offset=0`, `GET /skills/{id}`
- `GET /skills/evidence` — recent bound passing review candidates
- `POST /skills` — manual proposed version
- `POST /skills/draft` — local CSO proposed version; never accepted automatically
- `POST /skills/{id}/decision` — expected state version, accepted/revoked, note
- Existing `POST /business-discovery/{id}/practice-plan` accepts optional `skill_version_id`.

Routes inherit owner authentication and private-cache headers. Inputs are strict and bounded; SQLite values are parameterized. Definitions, bindings and decisions cannot be updated/deleted. Reuse does not change budget, resources, action state or owner approval records.

## Verification — 10 October 2026

- Eight focused skill tests cover source corrections, immutable versions, state conflicts, authentication, incompatible/repeated examples, atomic plan rollback, in-flight revocation and actual prompt binding and revocation before repair inference.
- Backend suite: 201 tests, passing with one existing real-Docker test skipped; after the final repair guard, all 44 focused skill/business/practice tests pass. Foundation regression: 150/150 checks pass with local DNS access.
- Real Chromium with disposable SQLite/FastAPI records verified CSO proposal, separate acceptance, third-exercise reuse, preserved sample after revocation and mobile width. Model calls were stubbed in this deterministic browser test; all API requests were intercepted into the disposable backend.
- A separate real local `llama3.1` call generated a third fictional sample using a test procedure and simulated fixture-only acceptance. It remains unassessed; the answer unnecessarily listed “external action (if any)” as unknown despite the supplied fact that none occurred, so this is runtime evidence, not quality or competence evidence. No real owner review was fabricated in the company database.
- Frontend lint has no errors (one existing image warning); production build/TypeScript pass. Focused Bandit medium/high checks and formatting/catalog checks pass.

Developer browser test: `.venv/bin/python scripts/skills_smoke.py`, against a temporary built dashboard at port 3002 (override `DASHBOARD_SMOKE_URL` if needed). This uses synthetic keys/data, intercepts API requests and starts no company scheduler.
