"""Opt-in authenticated SQLite snapshots; keys stay outside backup artifacts."""

import datetime
import os
import sqlite3
from pathlib import Path
from cryptography.fernet import Fernet


def _private_write(path: Path, payload: bytes) -> None:
    # Refuse existing files and symlinks, and set private permissions at creation.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def backup_encrypted_database(backup_dir: str, key: str, keep_last: int = 7) -> str:
    """Snapshot in memory so an encrypted export never leaves plaintext on disk."""
    from memory.database import get_connection

    if type(keep_last) is not int or keep_last < 1:
        raise ValueError("keep_last must be a positive integer")
    cipher = Fernet(key.encode("ascii"))  # Validate before creating any artifact.
    directory = Path(backup_dir)
    if directory.is_symlink():
        raise ValueError("Backup directory must not be a symlink")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    snapshot = sqlite3.connect(":memory:")
    try:
        with get_connection() as source:
            size = (
                source.execute("PRAGMA page_count").fetchone()[0]
                * source.execute("PRAGMA page_size").fetchone()[0]
            )
            if size > 128 * 1024 * 1024:
                raise ValueError(
                    "Encrypted in-memory backup exceeds 128 MiB limit; use an encrypted-volume backup workflow"
                )
            source.backup(snapshot)
        if snapshot.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Snapshot failed integrity check")
        payload = cipher.encrypt(snapshot.serialize())
    finally:
        snapshot.close()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    output = directory / f"executive_team_backup_{stamp}.db.fernet"
    _private_write(output, payload)
    backups = sorted(
        p
        for p in directory.glob("executive_team_backup_*.db.fernet")
        if p.is_file() and not p.is_symlink()
    )
    for expired in backups[:-keep_last]:
        expired.unlink()
    return str(output)


def restore_encrypted_database(backup_path: str, destination: str, key: str) -> str:
    """Authenticate and validate before creating a new owner-private database.

    Never overwrite a live database. The caller must choose an isolated restore
    location and protect its parent directory.
    """
    plaintext = Fernet(key.encode("ascii")).decrypt(Path(backup_path).read_bytes())
    snapshot = sqlite3.connect(":memory:")
    try:
        snapshot.deserialize(plaintext)
        if snapshot.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Restore failed integrity check")
    finally:
        snapshot.close()
    _private_write(Path(destination), plaintext)
    return destination
