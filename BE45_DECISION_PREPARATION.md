# BE-45 — decision preparation extraction

11 October 2026. In progress; final local integration audit pending.

The preparation endpoint is now a thin authenticated router in api/decisions.py. Its request/response schemas, endpoint URL and original prompt expression have identical ASTs to the pre-extraction versions (apart from the router owner). main.py supplies explicit callbacks per request, preserving original main.run_executive_meeting and main.send_notification test seams.

workflows/decision_preparation.py owns one attempt’s lifecycle, bounded proposal/resource compatibility flow, strict resource parser, provenance validation and meeting context. These responsibilities are separate methods instead of nested helpers in the original large route. Database callbacks retain atomic claims and transactional storage; the service grants no execution or resource access. Domain errors are translated at the HTTP boundary and private middleware remains application-wide.

Eleven SQLite/API characterization tests pass, covering missing decisions, request validation, owner authentication, goal state, provenance for both proposal types, pending authority, bounded resource fallback, printed action refusal, concurrency, retries and sanitized failures. Original evidence, profile handling, return fields and request bounds remain intact.

The foundation checker now follows the actual router/workflow source and verifies the explicit tool-capable binding plus owner-authenticated router assembly. The older comment-based resource retry check now inspects the retry call itself; dynamic tests assert its exact bounded call count and pending outcome. This avoids retaining a misleading comment solely to satisfy a text search.

This extracts one domain, not every route in main.py. Full Sprint 6 evaluation, audit, owner usefulness review and merge remain later items.
