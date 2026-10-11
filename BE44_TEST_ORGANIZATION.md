# BE-44 — safe backend test discovery

11 October 2026. Ready for review; owner acceptance and merge remain pending.

All backend regression modules remain in tests/. The three root test-named files were manual examples, so they now live under scripts/manual_checks/ with guarded entry points and application imports inside run functions. Generation examples require explicit opt-in, use temporary records and disable Telegram. We did not run real generation or the web demo.

`./company test` uses scripts/run_tests.py to discover tests/ after applying disposable database, workspace, log, framework-storage and sync paths. Inherited owner credentials and remote-control settings are replaced before application imports. A temporary environment is removed after exit. `--list` discovers without running tests; `--pattern` limits discovery within tests/; `--docker` opts into the real existing pinned-image check without pulling it.

The launcher dispatches without loading the company environment. The local full audit now uses this runner with Docker and accepts Sprint 6 branches. The foundation checker follows the moved config inspection script. README, developer guide and command guide describe the entry point; JavaScript and vendor tests stay in their packages.

The checked-in docs/ci/security.yml proposal uses the same runner. Active .github workflow commands still use supported tests/ discovery; publishing a workflow replacement requires suitable repository workflow permission and is a BE-53 integration dependency. No remote CI run is claimed for these local changes.

## Verification

- Full discovery lists 303 cases and executes none.
- Full backend run: 303 passed with real Docker, zero skips.
- Foundation: 150/150 passed with DNS available.
- Five new entry-point checks cover safe launcher dispatch, environment/path restoration, imports/help that block all application imports, explicit generation opt-in, and discovery in a clean temporary copy without Git, .env, database or manual scripts.
- Existing backend behavior and the nine new preparation checks remain covered; Black/Prettier and catalog checks pass.

The first restricted run could not create a Unix socket and could not resolve a public hostname. Its failures remain retained alongside the permitted rerun; they were not hidden or counted as passes. This verifies the backend and test entry point, not the complete final Sprint 6 browser/security audit. Known upstream dependency findings remain open.
