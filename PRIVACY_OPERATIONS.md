# Local privacy, retention and recovery operations

The AI Executive Team stores sensitive owner-controlled work in local SQLite,
rotated logs, SQLite backups, JSONL sync exports, and optional screenshots.
Local-only design is **not** encryption at rest. File permissions alone do not
protect against a compromised user account, malicious privileged process, or
unencrypted stolen disk.

## Required deployment controls

1. Use an encrypted system volume (macOS FileVault, Linux LUKS, Windows BitLocker)
   and a dedicated unprivileged operating-system user.
2. Keep database, logs, sync exports, and backup folders out of cloud-synced
   directories unless the cloud encryption and disclosure policy are approved.
3. Restrict backups and all generated files to owner-only permissions, and
   physically separate the encrypted off-device backup key from the backup.
4. Back up the database with SQLite's consistent backup API. Never copy a live
   SQLite database file without checking WAL state.
5. Keep Telegram remote commands and remote LLM usage disabled unless external
   transfer is specifically approved; inspect the data-flow and vendor retention terms.
6. Never assume that deleting a row irreversibly destroys data. Copies in SQLite
   WAL/journal files, OS snapshots, version control, and backups may remain.

## Retention decision matrix

| Data type | Current implementation | Required owner action |
|---|---|---|
| Rotated application logs | 5 MiB files, 3 backups | Review for secrets; configure OS log retention |
| Browser screenshots | Bounded by SCREENSHOT_RETENTION_COUNT | Set count and review collected content |
| Startup database backups | Bounded by backup keep_last | Encrypt volume and test restore |
| JSONL sync exports | Manual export, persistent until removed | Track copies and set owner-led deletion dates |
| Decisions and action outcomes | Durable audit trail, no automatic TTL | Define legal and business retention period before deletion |
| Executive memories and research | Durable and may include private context | Review consent and data minimization |
| Step checkpoints | State-only; no agent prompt payload | Retain alongside business audit evidence |

**Do not automatically prune the decision/action history:** it records human
approvals and execution provenance. A future deletion feature must preserve
referential integrity and explicitly warn that it destroys audit evidence.

## Restore drill

On a disposable test system: take a consistent SQLite backup, verify permissions,
restore into an isolated location, run schema initialization/migrations,
compare row counts and integrity check (`PRAGMA integrity_check;`), and run
`verify_system.py` with external transports disabled. Never point a restore
test at production database paths.

## Security release sign-off

A release needs evidence that encryption is actually enabled on the intended
machine and that backup restoration works, not merely a configuration checkbox.
This document is a deployment procedure, not an assertion that encryption or
retention enforcement has already been completed.
