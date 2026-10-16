# Manual checks

These scripts are opt-in examples, separate from tests/. Importing them initializes no agents, configuration, database or transport.

- `python scripts/manual_checks/test_config.py` inspects settings and reports whether a token is present; it never prints token characters.
- `python scripts/manual_checks/test_crew.py --run-local` runs real local CEO/CFO generation against temporary records. Telegram is disabled; the example budget is fictional. This does not approve spending.
- `python scripts/manual_checks/test_cso_tool.py --allow-web` runs real local CSO generation and reads the fixed public Wikipedia page. The flag explicitly opts into this web demo. Telegram is disabled and records are temporary.
- `python scripts/manual_checks/test_first_user_api.py --run-local --source-run audit-results/sprint7-independent/run-<retained-id>` checks one retained fictional silent-contact case through actual intake/generation/history with the local default model and disposable records. It retains all native attempts privately, including the existing one-repair-per-role behavior, and verifies saved-result replay if successful. No scheduler, notification, approval or execution occurs. This is a development integration check, not a held-out or owner-usefulness score. Run model experiments sequentially.

Use the checkout’s .venv Python. These generation demos are not run by `./company test`, test discovery or CI. Their guarded entry points parse arguments before application imports. Application environment settings may load for the config inspection; generation demos override credentials and paths before loading application configuration.
