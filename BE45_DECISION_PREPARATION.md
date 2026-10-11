# BE-45 — decision preparation extraction

11 October 2026. Ready for review; owner acceptance and merge pending.

The preparation endpoint is now a thin authenticated router in api/decisions.py. Its request/response schemas, endpoint URL and original prompt expression have identical ASTs to the pre-extraction versions (apart from the router owner). main.py supplies explicit callbacks per request, preserving original main.run_executive_meeting and main.send_notification test seams.

workflows/decision_preparation.py owns one attempt’s lifecycle, bounded proposal/resource compatibility flow, strict resource parser, provenance validation and meeting context. These responsibilities are separate methods instead of nested helpers in the original large route. Database callbacks retain atomic claims and transactional storage; the service grants no execution or resource access. Domain errors are translated at the HTTP boundary and private middleware remains application-wide.

Eleven SQLite/API characterization tests pass, covering missing decisions, request validation, owner authentication, goal state, provenance for both proposal types, pending authority, bounded resource fallback, printed action refusal, concurrency, retries and sanitized failures. Original evidence, profile handling, return fields and request bounds remain intact.

The foundation checker now follows the actual router/workflow source and verifies the explicit tool-capable binding plus owner-authenticated router assembly. The older comment-based resource retry check now inspects the retry call itself; dynamic tests assert its exact bounded call count and pending outcome. This avoids retaining a misleading comment solely to satisfy a text search.

This extracts one domain, not every route in main.py. Full Sprint 6 evaluation, audit, owner usefulness review and merge remain later items.

## Complete local verification

Audited implementation c98c3697abad13a324f278ed3a3380955a9ad1b7 passed 33 project stages: 312 backend tests including real Docker with zero skips, 150 foundation checks, 15 production browser feature checks, formatting/catalog, Bandit, frontend build and a real tool-free local model greeting. Report: audit-results/20261011-202326. The four known Chroma advisories remain an UPSTREAM release finding; dependency scan is not clean. This is an integration check of the selected changes, not final Sprint 6 completion or proof of model usefulness.

The earlier complete audit at 25e3014 retained 32 PASS, one FAIL and one UPSTREAM finding. Three foundation assertions still read preparation contracts from main.py; updated them to follow the actual router/workflow paths. The 305 backend tests and browser checks had passed in that run. No failed evidence was removed.
