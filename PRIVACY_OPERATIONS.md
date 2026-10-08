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

## Optional encrypted backups

Set `BACKUP_ENCRYPTION_KEY` through an owner-managed secret store to a Fernet key
(created with `cryptography.fernet.Fernet.generate_key()`). Do not commit it or
place it in the backup directory. Scheduled and startup backups then use
SQLite's consistent backup API into memory, authenticate/encrypt the snapshot,
and write only `.db.fernet` files with owner-only permissions. Invalid keys fail
without falling back to plaintext. The key is omitted from the Config repr.
Snapshots above 128 MiB fail closed to bound memory; larger databases need an
encrypted-volume backup solution. This does not encrypt the live database,
logs, screenshots or sync exports, and does not remove older plaintext copies.

`restore_encrypted_database(backup_path, destination, key)` authenticates and
checks integrity before exclusively creating a new private destination. It
refuses to overwrite a database. Use an isolated owner-controlled directory;
backup/restore directory ancestors must not be writable by untrusted users.
Keys must be backed up separately: losing the key loses access to the snapshot.

`BACKUP_RETENTION_COUNT` controls scheduled/startup copy count (default 7,
bounded 1–365); plaintext and encrypted backup families retain independently.
`LOG_ROTATION_BYTES` (default 5 MiB, bounded 1 KiB–100 MiB) and
`LOG_RETENTION_COUNT` (default 3, bounded 1–100) configure size-based log retention.
`SCREENSHOT_RETENTION_COUNT` continues to bound browser screenshots. These are
count/size limits, not age-based deletion or forensic secure erasure. Owner-led
retention decisions remain required for live history, sync copies and memories.
