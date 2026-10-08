# AI Executive Team

A local-first multi-agent system where AI "executives" (CEO, CFO, COO, CSO, CMO,
CTO, CHRO, General Counsel, CPO, Board Director, CCO) research real information,
hold structured meetings, and — with human approval — take real actions on your
machine: running commands, editing files, and navigating web pages.

This repo only contains source code. `venv/`, `node_modules/`, and `.env` are
intentionally excluded (see `.gitignore`) — follow the steps below to rebuild
them on any machine.

## Prerequisites

- **Python 3.12** (not 3.13/3.14 — CrewAI's dependency chain has had build
  issues on newer Python versions). On macOS: `brew install python@3.12`
- **Node.js** (for the dashboard) — any recent LTS version
- **Ollama**, with the `llama3.1` model pulled:
  ```bash
  ollama pull llama3.1
  ```
  Do NOT use plain `llama3` — it does not reliably support tool-calling,
  which the CSO's research tool and every action-proposal tool depend on.
- **Playwright browsers** (for browser actions):
  ```bash
  playwright install chromium
  ```
- A **Telegram bot token** and your **chat ID** (see "Getting a Telegram bot"
  below if starting fresh)

## Backend setup

```bash
git clone <your-repo-url>
cd "AI Executive Team"

# Create and activate a Python 3.12 virtual environment
/opt/homebrew/bin/python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Configure secrets

```bash
cp .env.example .env
```

Edit `.env` and set:

| Variable | What it's for |
|---|---|
| `OLLAMA_MODEL` | `llama3.1` |
| `TELEGRAM_BOT_TOKEN` | From @BotFather on Telegram |
| `TELEGRAM_CHAT_ID` | Your personal chat ID (see `getUpdates` method) |
| `API_SECRET_KEY` | Long random owner-control key — generate one with `openssl rand -hex 32`. Required for protected API access. |
| `OPENAI_API_KEY` | Any non-empty placeholder string, e.g. `ollama-local-not-a-real-key` — required by CrewAI's OpenAI-compatible client even though Ollama never checks it |
| `SANDBOX_MODE` | `True` to start. Can also be toggled live from the dashboard (see below) — no manual editing needed after initial setup. |
| `WORKSPACE_ROOT` | `./workspace` by default. Every file operation and shell command touching a path is confined here — see Safety Architecture below. |
| `ALLOWED_BROWSER_DOMAINS` | Optional. Comma-separated domain allowlist for browser actions (e.g. `wikipedia.org,github.com`). Empty = any public http/https domain allowed; internal/private addresses remain blocked. |
| `CREWAI_DISABLE_TELEMETRY` | `true` by default for local-first privacy. |
| `SYNC_HMAC_KEY` | Recommended dedicated shared key for authenticated cross-machine JSONL sync. If empty, the API secret is used. |
| `ALLOW_UNSAFE_RAW_SHELL` | `False` by default. Live shell uses the isolated Docker worker if explicitly enabled; Docker must be installed with the pinned Alpine image digest pre-pulled. |
| `BIND_HOST` | `127.0.0.1` by default. Keep the API loopback-only unless you deliberately deploy a protected remote transport. |
| `ALLOW_INSECURE_REMOTE_HTTP` | `False` by default. A non-loopback plaintext HTTP bind fails startup unless you explicitly accept that transport risk. |
| `TELEGRAM_INCLUDE_SENSITIVE_DETAILS` | `False` by default. Action descriptions/details, paths, commands, URLs, errors, and transport details remain local unless explicitly enabled. |
| `TELEGRAM_ALLOW_REMOTE_CONTROL` | `False` by default. Telegram is notification-only unless the owner explicitly enables remote Approve/Reject/Execute. |
| `ALLOW_REMOTE_LLM` | `False` by default. Non-loopback model endpoints are blocked unless explicitly enabled; enabled remote endpoints must use HTTPS. |
| `SCREENSHOT_RETENTION_COUNT` | Number of private browser screenshots retained in the workspace (default `50`). Oldest action screenshots are pruned. |

### Verify the setup

```bash
python test_config.py
python verify_system.py
```

`verify_system.py` runs 140+ regression/security checks covering agent roster integrity,
endpoint auth, state-machine gates, treasury authority, signed sync, privacy,
workspace/file safety, browser/research SSRF boundaries, autonomous retries,
executive memory evidence separation, meeting types, and more. Run this after *any* code change, especially AI-generated ones — it has
repeatedly caught real regressions during development that looked fine at a
glance.

### Run the backend

```bash
python main.py
```

Runs on `http://localhost:8000`. On startup it:
- Checks whether daily research has already run today and catches up if not
  (no exact wake time needed — works across machines, whichever one is open
  first after 9 AM runs it)
- Starts the interactive Telegram listener (see below)

## Frontend setup

```bash
cd executive-dashboard
npm install
npm run dev
```

Open `http://localhost:3000`. You'll be prompted for the `API_SECRET_KEY`
from your `.env`. The dashboard keeps it in browser memory only; refreshing
the page intentionally requires re-entry so a future XSS cannot recover a
persisted control-plane credential.

The dashboard shows: daily research status, a live Sandbox/Live mode toggle,
pending actions (approve/reject/execute), full action history, an ad-hoc
decision form (pick any subset of the 11 agents), and decision history.

## Getting a Telegram bot (first-time only)

1. Message **@BotFather** on Telegram, send `/newbot`, follow the prompts.
2. Send any message to your new bot.
3. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser —
   your chat ID appears in the JSON response.

Once running, action proposals arrive as interactive Telegram messages with
real **Approve / Reject / Execute** buttons — no need to open the dashboard
for routine approvals.

## What the executive team can actually do

Beyond discussing and deciding, agents can **propose real actions**, which
require your explicit approval before anything happens:

| Capability | Tool | Who has it | What it does |
|---|---|---|---|
| Shell commands | `propose_action` | COO, CTO | Proposal path retained for compatibility/testing. Live shell is disabled by default; opt-in requires a constrained, network-disabled Docker worker. |
| File read/write/append | `propose_file_operation` | COO, CFO, CTO, General Counsel | Structured file I/O — no shell involved, safer than a raw command |
| Browser navigate + click | `propose_browser_action` | COO | Navigates to a URL and optionally clicks one element, screenshots the result |

Every proposal is logged to the database and sent via Telegram (with
buttons) regardless of mode. **Nothing executes until a human approves it.**

## Safety architecture

This is the part worth understanding before flipping to Live mode:

- **Sandbox mode (default)**: approving and "executing" an action never
  touches your real filesystem, shell, or browser — it logs what *would*
  happen and notifies you. Toggle to Live mode from the dashboard banner
  (requires confirmation) when you're ready for real execution.
- **Danger-pattern blocklist**: known catastrophic commands (`rm -rf /`,
  fork bombs, `curl | bash`, `sudo`, etc.) are blocked outright, in both
  sandbox and live mode.
- **Structured workspace confinement**: file operations resolve paths inside
  `WORKSPACE_ROOT`; writes are atomic and owner-only. Raw shell path parsing
  remains heuristic defense-in-depth and is therefore **not** considered a
  security sandbox.
- **Live raw shell default-off**: host shell could access OS resources in ways
  string/path inspection cannot reliably model. Live shell execution fails
  closed unless the owner explicitly sets `ALLOW_UNSAFE_RAW_SHELL=True`; enabled commands run only inside the constrained Docker worker.
- **URL/network safety**: browser actions validate every HTTP(S) request,
  including redirects and subresources, block service workers/downloads, and
  reject loopback/private/link-local targets. Research revalidates redirects,
  restricts ports/content types, and caps response bodies.
- **Execution lock**: only one heavy CrewAI run (a meeting or research cycle)
  executes at a time, system-wide — prevents a scheduled run and a manual
  one from overlapping and doubling CPU/heat load.
- **Duplicate-proposal guard**: if an agent calls the same proposal tool
  with the same arguments repeatedly within 90 seconds (a known local-LLM
  failure mode — one incident produced 13 identical proposals before this
  existed), only the first call creates a proposal; the rest are rejected
  and the agent is told to stop.
- **`max_iter=5`** on every agent: a hard cap on reasoning/tool-call
  iterations per task, independent of the guard above.
- **Reasoning is tool-free**: daily research, ad-hoc decisions, and autonomous
  reasoning use `EXECUTIVE_AGENTS_NO_TOOLS`. Tool-capable executives are used
  only after the owner approves a decision and explicitly starts preparation;
  resulting actions/resources still require their own owner gates.
- **In-progress guard**: daily research cannot run twice concurrently, even
  if two triggers land close together (a real race condition this project
  hit once, now structurally prevented).
- **Auth**: sensitive read and write API surfaces require `X-API-Key`.
  The backend binds loopback by default and CORS is restricted to the local
  dashboard origins. Invalid guesses are rate-limited without allowing an
  attacker to lock out a request that presents the correct owner key.
- **External-channel privacy**: Telegram is notification-only by default.
  Remote Approve/Reject/Execute requires explicit opt-in, and action
  descriptions/paths/commands/URLs/errors stay local unless sensitive-detail
  egress is separately enabled. Transport-library exception details and
  unauthorized sender identifiers are suppressed from logs.
- **Filesystem race resistance**: structured file I/O walks the workspace using
  descriptor-relative `O_NOFOLLOW` operations, rejects special/multi-hard-link
  targets, caps reads/writes, and preserves atomic owner-only writes.
- **Runtime artifact privacy**: database/backups/sync/logs/screenshots are
  owner-only where supported; screenshot serving refuses symlink escapes and
  rotated logs are hardened back to mode `0600`.
- **Telegram owner identity**: action buttons are accepted only from the
  configured owner's private Telegram chat/user. Telegram uses the same
  treasury/goal-aware action-control functions as the API.
- **Local-first telemetry/model transport**: CrewAI telemetry is disabled by
  project default. A non-local Ollama URL fails startup unless the owner
  explicitly enables remote LLM transport, and remote model endpoints must
  use HTTPS because prompts/context may leave the machine.
- **Authenticated sync, local authority**: JSONL sync rows are HMAC-signed.
  Remote approved/executing actions do not import as local execution
  authority, and remote active reservations do not import as local spending
  authority.

## Project structure

```
agents/executive_agents.py       — 11 executive agent definitions, plus tool-less clones for daily research
workflows/meeting.py             — multi-agent sequential meeting logic (CEO always synthesizes last)
workflows/daily_research.py      — research → verify → meeting → log → notify pipeline (async)
workflows/action_executor.py     — executes approved actions: shell, file operations, browser actions — with all safety guards
workflows/execution_lock.py      — system-wide lock preventing overlapping heavy runs
tools/research_tool.py           — web page reading tool (requests + BeautifulSoup)
tools/action_proposal_tool.py    — propose_action (shell commands)
tools/file_operation_tool.py     — propose_file_operation (read/write/append)
tools/browser_action_tool.py     — propose_browser_action (navigate + click)
tools/_dedupe_guard.py           — shared duplicate-call protection for all propose_* tools
memory/database.py               — SQLite: decisions, action queue, full action history
notifications/telegram_bot.py    — Telegram notifications (HTML parse mode)
notifications/telegram_interactive.py — interactive Approve/Reject/Execute buttons
main.py                          — FastAPI backend, scheduling, auth, sandbox toggle
verify_system.py                 — smoke test for core invariants — run after any code change
executive-dashboard/             — Next.js dashboard (separate npm project)
```

## Known limitations

- `llama3.1:8b` running locally has inconsistent native tool-calling — the
  research workflow has a built-in retry guard (3 attempts) that detects and
  retries when the CSO fabricates tool output instead of genuinely calling
  the tool. If it fails all 3 attempts, it logs an honest failure rather than
  fake research.
- Scheduling requires the laptop to actually be running — there's no
  wake-from-sleep. The catch-up check means whichever machine you open first
  after 9 AM runs it, but two machines with separate local databases won't
  know what the other already did (occasional duplicate research on days you
  switch machines — a minor inefficiency, not a bug).
- Browser actions support navigate + click only — no form-filling. Typing
  into a field (e.g. a login form) is a meaningfully bigger trust question
  than clicking a public button, and was deliberately left out of scope.
- Fine-tuning (originally planned) requires an NVIDIA GPU and hasn't been
  pursued given Apple Silicon hardware — current quality relies on
  prompt/backstory engineering and `max_iter` tuning instead.
- Shell execution remains default-off; when enabled, it uses Docker rather than the host process.
  default. The intended long-term execution boundary is a disposable local
  container/VM sandbox for side-effecting activities, while the executive
  control plane remains on the host.
- SQLite state, backups and sync exports are owner-permission protected and
  sync exports are integrity-authenticated, but they are not application-level
  encrypted at rest. Use full-disk encryption now; add authenticated encrypted
  exports/backups later rather than inventing custom crypto.
- Durable business state is persisted, but long multi-step executive workflows
  are not yet checkpointed at every step. The next foundation milestone should
  add explicit run/step checkpoints plus idempotency keys so a crash/resume
  never repeats a completed side effect.

## Automated security checks

GitHub Actions runs the **Security and Foundation Checks** workflow on pull
requests and pushes to `main`. It uses the supported Python 3.12 runtime,
compiles the backend, runs Bandit, audits Python dependencies with
`pip-audit`, and runs the frontend lint/build plus `npm audit`. Dependabot
also watches Python, npm, and GitHub Actions dependencies. CrewAI remains
deliberately protected from automatic major/minor upgrades because runtime
stability and tool behavior must be revalidated manually.

## Foundation audit

See [FOUNDATION_AUDIT.md](FOUNDATION_AUDIT.md) for the pre-frontend security/privacy audit, residual risks, and architecture lessons from comparable agent systems.
