# Local commands explained

Use this checkout rather than the older `Ai village/AI Executive Team` copy. From any terminal:

```sh
cd "/Users/alpha/.codex/.chatgpt-projects/g-p-6ac6034a5d7881918e21bf72595bb34b/foundation-hardening"
./company doctor
./company start
```

`cd` selects the checkout. `doctor` checks the current Git branch, this checkout's Python 3.12 environment, configured key, Node/npm, Docker, local Ollama and both application ports. It does not change files, fetch commits, switch branches or stop apps. Open Docker Desktop and Ollama if it reports they are unavailable.

`start` builds the current branch's dashboard, starts the backend on 8001 and dashboard on 3000, then copies your **existing** API key to the macOS clipboard. Open `http://127.0.0.1:3000` and paste the key. Keep this single terminal open. Ctrl+C stops only the apps this launcher started.

If older apps already occupy those ports, stop them with Ctrl+C in their own terminals first. The launcher refuses to kill or silently reuse them. It always rebuilds the current dashboard; it installs exact npm dependencies only if `node_modules` is missing. The first install requires internet access; the build no longer downloads Google fonts.

## Other commands

| Command | Purpose |
|---|---|
| `./company doctor` | Diagnose local setup without starting apps |
| `./company start` | Build and run both apps in one terminal |
| `./company key` | Copy the configured key again, without displaying or replacing it |
| `./company audit` | Run automated checks using disposable data and a separate frontend copy |
| `./company help` | Show command choices |

The launcher enforces local sandbox settings, disables raw shell, remote LLMs, Telegram and framework telemetry for its children. It preserves your `.env`, database, goals, existing key and unrelated processes. Existing approved local schedules still run under sandbox settings. It does not make a fresh test company or reset the current one. The audit's disposable internal key never replaces your dashboard key.

A missing/short `API_SECRET_KEY` must be set privately in this checkout's `.env`; the launcher will not generate one silently. Environment variables override `.env`, so use the same launcher/terminal configuration for start and key copy. Never paste keys into chat or commit `.env`.

## Git, separately

Git selects code; it does not select/reset your database or `.env`. To test this feature branch after it is pushed:

```sh
git switch codex/sprint-2-local-review
git pull --ff-only origin codex/sprint-2-local-review
./company start
```

`switch` chooses a branch. `pull --ff-only` downloads commits without creating a merge. If Git reports uncommitted changes, preserve them; do not reset. Stop/restart the apps after changing branches. After an approved merge, select `main` instead.

For initial environment installation or a broken dependency environment, follow the repository installation instructions. The launcher diagnoses setup; it does not upgrade Python, replace `.venv`, reinstall Docker or rewrite credentials. `curl` calls individual HTTP endpoints but is no longer necessary merely to start and review the dashboard.

Audit results live under `audit-results/`. `PROJECT CHECKS: PASS` applies to the automated checks; separate upstream advisories remain visible. It does not certify every AI answer or production deployment.

## Earlier browser checks

After a UI change, run `./company check-ui` for the navigation, run inspector,
calendar/experiment and business checks. Use `./company check-ui runs experiments`
to select affected features, or `./company check-ui --all` for all 15 features.
This builds a production dashboard on its own loopback test port and uses disposable
data and synthetic API reads. It preserves company keys, records and running apps.
Development dependencies must already be installed. Logs stay under `audit-results/`.
The complete `./company audit` remains the final integration gate.

## Fictional AI quality measurement

With Ollama open: `./company quality`, then `./company quality summary`. See [BE24_QUALITY_BENCHMARKS.md](docs/BE24_QUALITY_BENCHMARKS.md) for limitations, prompt replay and comparisons. This uses fictional data and preserves your existing key and company records.

## Sprint 5 review

`./company review` prints [exact steps and fictional input data](COMPANY_REVIEW_GUIDE.md)
without loading a company key. `./company review --check` tests the complete private
work/feedback/files/procedure-reuse chain with disposable data and synthetic
inference. `./company review --demo` launches the four fictional recovery cases,
prints its own URL/demo key, and cleans its owned temporary apps on Ctrl+C.
Your existing configured company still uses `./company start` and its existing key.
