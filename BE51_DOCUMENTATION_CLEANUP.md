# BE-51 — documentation and catalog

11 October 2026. Ready for review.

Eight closed plan/retrospective narratives are retained under [the archive](docs/archive/sprints/README.md). Old paths remain compatibility links. Relative links in moved text were adjusted to preserve their destinations. Active Sprint 6, operating/authority/privacy contracts, fixtures, benchmark snapshots and audit manifests stay at their operational paths. No failure evidence was erased.

The generated catalog is now one row per source module plus literal route lookup, including nested router factories. It is about 46 KB instead of the earlier roughly 74 KB; individual symbol lists no longer duplicate source text. Scoped commands print backend, frontend or tests without rewriting the full saved index. The generator ignores missing cached paths after moves, reads syntax only and imports neither application nor credentials.

```sh
.venv/bin/python scripts/code_catalog.py
.venv/bin/python scripts/code_catalog.py --check
.venv/bin/python scripts/code_catalog.py --scope backend
```

Generation/check passed. Full formatting, link and integration results belong to the final audit. The proposed CI template retains API coverage and the safe test runner; the active workflow is unchanged pending specific approval and an authorized workflow credential.
