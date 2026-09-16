# AI Executive Team

A local-first multi-agent system where AI "executives" (CEO, CFO, COO, CSO, CMO,
CTO, CHRO, General Counsel, CPO, Board Director, CCO) research real information,
hold structured meetings, and log decisions — with human oversight via Telegram
and a web dashboard.

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
  which the CSO's research tool depends on.
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

Copy the example env file and fill in real values:

```bash
cp .env.example .env
```

Edit `.env` and set:

| Variable | What it's for |
|---|---|
| `OLLAMA_MODEL` | `llama3.1` |
| `TELEGRAM_BOT_TOKEN` | From @BotFather on Telegram |
| `TELEGRAM_CHAT_ID` | Your personal chat ID (see `getUpdates` method) |
| `API_SECRET_KEY` | Any long random string — generate one with `openssl rand -hex 32`. Required for `/decisions/trigger` and `/workflows/daily-research/trigger`. |
| `OPENAI_API_KEY` | Any non-empty placeholder string, e.g. `ollama-local-not-a-real-key` — required by CrewAI's OpenAI-compatible client even though Ollama never checks it |
| `SANDBOX_MODE` | `True` (keep this until you deliberately want real-world actions) |

### Verify the setup

```bash
python test_config.py
python verify_system.py
```

`verify_system.py` should show all static checks passing before you trust
anything else works. If Ollama isn't running yet, start it separately
(`ollama serve`, or just open the Ollama app) before testing further.

### Run the backend

```bash
python main.py
```

Runs on `http://localhost:8000`. On startup, it will automatically check
whether daily research has already run today and catch up if not — no exact
wake time needed, works across machines as long as the SQLite database
(`memory/executive_team.db`, not tracked in git) travels with you or the app
runs at least once a day on whichever machine is open.

## Frontend setup

```bash
cd executive-dashboard
npm install
npm run dev
```

Open `http://localhost:3000`. You'll be prompted for the `API_SECRET_KEY`
from your `.env` — this is stored only in the browser's `sessionStorage` for
that tab, not persisted anywhere.

## Getting a Telegram bot (first-time only)

1. Message **@BotFather** on Telegram, send `/newbot`, follow the prompts.
2. Send any message to your new bot.
3. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser —
   your chat ID appears in the JSON response.

## Project structure

```
agents/executive_agents.py     — the 11 executive agent definitions
workflows/meeting.py           — multi-agent sequential meeting logic (CEO always synthesizes last)
workflows/daily_research.py    — research → verify → meeting → log → notify pipeline (async)
tools/research_tool.py         — web page reading tool (requests + BeautifulSoup)
memory/database.py             — SQLite decision audit trail
notifications/telegram_bot.py  — Telegram notifications
main.py                        — FastAPI backend, scheduling, auth
verify_system.py               — smoke test for core invariants — run after any code change
executive-dashboard/           — Next.js dashboard (separate npm project)
```

## Known limitations

- `llama3.1:8b` running locally has inconsistent native tool-calling — the
  research workflow has a built-in retry guard (3 attempts) that detects and
  retries when the CSO fabricates tool output instead of genuinely calling
  the tool. If it fails all 3 attempts, it logs an honest failure rather than
  fake research.
- Scheduling requires the laptop to actually be running — there's no
  wake-from-sleep. The catch-up check (see `main.py`) means whichever
  machine you open first after the scheduled time will run it, but two
  machines with separate local databases won't know what the other already did.
- Fine-tuning (originally planned) requires an NVIDIA GPU and hasn't been
  pursued given Apple Silicon hardware — current quality relies on
  prompt/backstory engineering instead (see agent backstories).
