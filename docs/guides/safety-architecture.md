# Safety architecture


This is the part worth understanding before flipping to Live mode:

- **Sandbox mode (default)**: approving and "executing" an action never
  performs the proposed live operation — it records a simulated result. The
  application still writes its database, logs and backups and can read public sources. Toggle to Live mode from the dashboard banner
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
