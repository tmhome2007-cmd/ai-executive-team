# Local commands explained

Use this checkout for the new features. Your older `Ai village/AI Executive Team` directory is a separate copy.

## Terminal 1: select the code and start the backend

Stop an older backend with Ctrl+C in its terminal first. Then:

```sh
cd "/Users/alpha/.codex/.chatgpt-projects/g-p-6ac6034a5d7881918e21bf72595bb34b/foundation-hardening"
git switch codex/identity-organization-simulation
git pull --ff-only origin codex/identity-organization-simulation
```

`cd` selects the folder. `git switch` selects the version of the code. `git pull --ff-only` downloads newer commits without creating a merge. Switching branches does not switch or reset your database, virtual environment or `.env` file. If Git reports local changes, keep them and ask for help rather than resetting.

```sh
open -a Docker
open -a Ollama
export SANDBOX_MODE=true
export ALLOW_UNSAFE_RAW_SHELL=false
export CREWAI_DISABLE_TELEMETRY=true
export CREWAI_TRACING_ENABLED=false
export TELEGRAM_BOT_TOKEN=""
export TELEGRAM_CHAT_ID=""
.venv/bin/python -c 'from config import config; print(config.API_SECRET_KEY, end="")' | pbcopy
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

`open` starts the local services. `export` sets safety options for this terminal and the backend it starts. `.venv/bin/python` uses this checkout's Python environment directly, so you do not need `source .../activate`. `uvicorn` starts the backend; leave this terminal open.

The `pbcopy` command copies the configured key to your clipboard without displaying it. Paste it into the dashboard's API Key field. It **does not create a new key**. An empty/missing `API_SECRET_KEY` must be fixed privately in this checkout's `.env` before startup. Never paste the key into a chat or commit `.env`. Environment variables can override `.env`, so copy the key from the same terminal configuration used to start the backend.

## Terminal 2: start the dashboard

Stop an older dashboard with Ctrl+C in its terminal first. Open a new terminal:

```sh
cd "/Users/alpha/.codex/.chatgpt-projects/g-p-6ac6034a5d7881918e21bf72595bb34b/foundation-hardening/executive-dashboard"
export NEXT_PUBLIC_API_BASE=http://127.0.0.1:8001
npm ci
npm run build -- --webpack
npm run start -- --hostname 127.0.0.1
```

`npm ci` installs the exact frontend dependencies. `build` prepares the current branch's dashboard. `start` serves that build at `http://127.0.0.1:3000`. Rebuild after frontend code changes; restarting an old build still shows the old interface.

Open the dashboard, unlock it with the copied key, and select **Organizational work → People & simulation**. Use fictional data. Changing task status or personal-life records does not authorize business execution.

## Terminal 3: run the automated audit

```sh
cd "/Users/alpha/.codex/.chatgpt-projects/g-p-6ac6034a5d7881918e21bf72595bb34b/foundation-hardening"
.venv/bin/python scripts/local_audit.py
```

This runs automated checks using a disposable database and separate frontend copy. Its synthetic audit key is internal to the test; it does not replace your dashboard key. Results are saved under `audit-results/`. `PROJECT CHECKS: PASS` means those checks passed. A separate upstream dependency warning remains visible and is not a clean production security sign-off.

`curl` is a terminal HTTP client for calling individual backend endpoints. You do not need to repeat a long curl script to review the new dashboard features. Keep the three purposes separate: backend, dashboard, automated audit.
