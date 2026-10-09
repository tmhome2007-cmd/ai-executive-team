# Terminal audit on the hardening branch

Run this in a new Mac terminal. It uses the separate hardening checkout, not the
original main checkout. The runner verifies the branch and runs against disposable
SQLite/workspace/CrewAI storage with Telegram, remote models and tracing disabled.
It never starts automatic research or grants owner approval. Action-gate tests
perform synthetic file effects only in temporary test workspaces.

## Setup from scratch

```bash
cd "/Users/alpha/.codex/.chatgpt-projects/g-p-6ac6034a5d7881918e21bf72595bb34b/foundation-hardening"
git switch chatgpt/foundation-hardening
git pull --ff-only origin chatgpt/foundation-hardening

/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt pip-audit bandit
.venv/bin/python -m playwright install chromium

node --version
open -a Docker
open -a Ollama
```

Node 22.17+ or 24 is required. Wait for Docker Desktop to finish starting.
`ollama list` should include llama3.1. If it is missing, run `ollama pull llama3.1`
once. No production .env or Telegram credentials are needed. Do not force a Git
pull/reset if Git reports your local changes need attention.

If the checkout is missing, clone the branch first:

```bash
git clone --branch chatgpt/foundation-hardening \
  https://github.com/tmhome2007-cmd/ai-executive-team.git \
  "/Users/alpha/.codex/.chatgpt-projects/g-p-6ac6034a5d7881918e21bf72595bb34b/foundation-hardening"
```

## Run every automated check

```bash
.venv/bin/python scripts/local_audit.py
```

This runs pip compatibility, pinned Docker image preparation, all security tests
with real Docker enabled, the 150-check foundation verifier, Bandit medium/high,
Python dependency audit, frontend clean install/native-glob/lint/production build,
CSP/API-origin regression check, full npm audit, Chromium launch/rendering and
local Ollama inference.
The frontend is built in a temporary copy: an open dashboard and its build remain
untouched. It uses Webpack for the local build. It does not open or change browser
sessions, restart the API, modify production credentials or merge main.

Wait for the final report. Do not start another audit while the first runs.
Expected summary:

```text
PROJECT CHECKS: PASS
UPSTREAM: Chroma advisories still present; tracked separately from project check failures.
```

The upstream line is not an ignored scan or a clean dependency result. The raw
pip-audit JSON and all findings are saved. Only the four currently known Chroma
advisories with no fix versions are categorized separately. New findings or
published fixes require review and cause a project-check failure.

Logs and summary.json are saved under the printed `audit-results/<timestamp>`
folder, which is excluded from Git. Exit status zero means automated project checks
passed; it does not certify model reasoning or production deployment. Bandit low
findings remain outside its configured medium/high gate. Human review, deployment
confinement and real external-service recovery cannot be exhaustively verified by
this command. No real external side effects are tested.

Share the final summary and any failed stage's log, keeping credentials private.
Do not share .env files. A missing Docker/Ollama/runtime is a setup failure, not a
reason to disable a security check. There is no need to repeat dashboard tests #2–#6.
