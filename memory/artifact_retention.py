"""Age retention for generated artifacts; durable approval history is untouched."""
import os
import re
import stat
import time
from pathlib import Path
from config import config
from memory.database import get_connection


def _init_registry(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS generated_sync_exports (
                    filename TEXT PRIMARY KEY, generated_at REAL NOT NULL)''')


def register_sync_export(path: str) -> None:
    directory = Path(config.SYNC_EXPORT_DIR).absolute()
    target = Path(path).absolute()
    # Only files directly in the explicitly designated export directory.
    if target.parent != directory or directory.is_symlink() or target.is_symlink():
        return
    with get_connection() as conn:
        _init_registry(conn)
        conn.execute('INSERT OR REPLACE INTO generated_sync_exports VALUES (?, ?)',
                     (target.name, time.time()))
        conn.commit()


def _prune_directory(directory: str, permitted, cutoff: float) -> int:
    directory = os.path.abspath(directory)
    if os.path.realpath(directory) != directory or not os.path.isdir(directory):
        return 0
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    deleted = 0
    try:
        metadata = os.fstat(fd)
        if metadata.st_uid != os.getuid() or metadata.st_mode & 0o022:
            raise ValueError('Retention directory must be owner-controlled')
        for name in os.listdir(fd):
            if not permitted(name):
                continue
            try:
                metadata = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                        or metadata.st_uid != os.getuid() or metadata.st_mtime >= cutoff):
                    continue
                os.unlink(name, dir_fd=fd)
                deleted += 1
            except FileNotFoundError:
                continue
    finally:
        os.close(fd)
    return deleted


def prune_generated_artifacts(*, now: float | None = None) -> dict:
    """Delete only expired rotated logs, screenshots and registered sync exports."""
    days = config.ARTIFACT_RETENTION_DAYS
    if type(days) is not int or not 1 <= days <= 3650:
        raise ValueError('Artifact retention must be 1–3650 days')
    current = time.time() if now is None else now
    from logging_config import rotate_aged_active_log
    rotate_aged_active_log(now=current)
    cutoff = current - days * 86400
    with get_connection() as conn:
        _init_registry(conn)
        names = {row[0] for row in conn.execute(
            'SELECT filename FROM generated_sync_exports WHERE generated_at < ?', (cutoff,))}
    from workflows.conversation_audio import prune_audio
    audio_deleted = prune_audio(now=current)
    return {
        'conversation_audio': audio_deleted,
        'logs': _prune_directory(os.getenv('LOG_DIR', 'logs'), lambda name: re.fullmatch(r'app\.log\.[1-9][0-9]*', name) is not None, cutoff),
        'screenshots': _prune_directory(os.path.join(config.WORKSPACE_ROOT, 'screenshots'),
                                      lambda name: re.fullmatch(r'action_[A-Za-z0-9_-]+\.png', name) is not None, cutoff),
        'sync_exports': _prune_directory(config.SYNC_EXPORT_DIR, lambda name: name in names, cutoff),
    }
