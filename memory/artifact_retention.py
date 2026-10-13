"""Age retention for generated artifacts; durable approval history is untouched."""

import os
import re
import stat
import time
import hashlib
import json
from pathlib import Path
from config import config
from memory.database import get_connection


def _init_registry(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS generated_sync_exports (
                    filename TEXT PRIMARY KEY, generated_at REAL NOT NULL)""")


def register_sync_export(path: str) -> None:
    directory = Path(config.SYNC_EXPORT_DIR).absolute()
    target = Path(path).absolute()
    # Only files directly in the explicitly designated export directory.
    if target.parent != directory or directory.is_symlink() or target.is_symlink():
        return
    with get_connection() as conn:
        _init_registry(conn)
        conn.execute(
            "INSERT OR REPLACE INTO generated_sync_exports VALUES (?, ?)",
            (target.name, time.time()),
        )
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
            raise ValueError("Retention directory must be owner-controlled")
        for name in os.listdir(fd):
            if not permitted(name):
                continue
            try:
                metadata = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if (
                    not stat.S_ISREG(metadata.st_mode)
                    or metadata.st_nlink != 1
                    or metadata.st_uid != os.getuid()
                    or metadata.st_mtime >= cutoff
                ):
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
        raise ValueError("Artifact retention must be 1–3650 days")
    current = time.time() if now is None else now
    from logging_config import rotate_aged_active_log

    rotate_aged_active_log(now=current)
    cutoff = current - days * 86400
    with get_connection() as conn:
        _init_registry(conn)
        names = {
            row[0]
            for row in conn.execute(
                "SELECT filename FROM generated_sync_exports WHERE generated_at < ?",
                (cutoff,),
            )
        }
    from workflows.conversation_audio import prune_audio

    audio_deleted = prune_audio(now=current)
    from memory.practice_artifacts import prune_artifacts

    artifacts_deleted = prune_artifacts(now=current)
    structured_deleted = prune_structured_decisions(cutoff)
    evaluation_deleted = prune_evaluation_samples(cutoff)
    return {
        "evaluation_samples": evaluation_deleted,
        "structured_decisions": structured_deleted,
        "conversation_audio": audio_deleted,
        "practice_artifacts": artifacts_deleted,
        "logs": _prune_directory(
            os.getenv("LOG_DIR", "logs"),
            lambda name: re.fullmatch(r"app\.log\.[1-9][0-9]*", name) is not None,
            cutoff,
        ),
        "screenshots": _prune_directory(
            os.path.join(config.WORKSPACE_ROOT, "screenshots"),
            lambda name: re.fullmatch(r"action_[A-Za-z0-9_-]+\.png", name) is not None,
            cutoff,
        ),
        "sync_exports": _prune_directory(
            config.SYNC_EXPORT_DIR, lambda name: name in names, cutoff
        ),
    }


def prune_structured_decisions(cutoff):
    """Expire generated decision bytes, preserving non-sensitive provenance."""
    root = Path(config.WORKSPACE_ROOT).absolute() / "structured-decisions"
    if os.path.realpath(root) != str(root) or not root.is_dir():
        return 0
    deleted = 0
    for child in root.iterdir():
        if (
            re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", child.name)
            and child.is_dir()
            and not child.is_symlink()
        ):
            deleted += _prune_directory(
                str(child),
                lambda name: name != "provenance.json"
                and re.fullmatch(r"(?:input|brief|[a-z_]+-[12])\.json", name)
                is not None,
                cutoff,
            )
    return deleted


def _expire_evaluation_directory(directory, permitted, cutoff):
    """Retain hash/status receipts before deleting only our expired sample bytes."""
    directory = Path(directory).absolute()
    if os.path.realpath(directory) != str(directory) or not directory.is_dir():
        return 0
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    deleted = 0
    try:
        owner = os.fstat(fd)
        if owner.st_uid != os.getuid() or owner.st_mode & 0o022:
            raise ValueError("Evaluation retention directory must be owner-controlled")
        for name in os.listdir(fd):
            if not permitted(name):
                continue
            metadata = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or metadata.st_nlink != 1
                or metadata.st_mtime >= cutoff
                or metadata.st_size > 4_000_000
            ):
                continue
            reader = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
            try:
                opened = os.fstat(reader)
                if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
                    continue
                with os.fdopen(os.dup(reader), "rb") as handle:
                    raw = handle.read(4_000_001)
                if len(raw) > 4_000_000:
                    continue
                receipt = {
                    "sample_hash": hashlib.sha256(raw).hexdigest(),
                    "bytes_expired": True,
                    "original_size": len(raw),
                }
                try:
                    sample = json.loads(raw)
                except (ValueError, UnicodeError):
                    sample = {}
                if isinstance(sample, dict) and sample.get("status") in {
                    "valid",
                    "error",
                    "incomplete",
                    "valid_schema_private_draft",
                    "failed_no_decision_published",
                }:
                    receipt["status"] = sample["status"]
                encoded = (json.dumps(receipt, sort_keys=True) + "\n").encode()
                receipt_name = name + ".provenance.json"
                try:
                    writer = os.open(
                        receipt_name,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o600,
                        dir_fd=fd,
                    )
                except FileExistsError:
                    check = os.open(
                        receipt_name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd
                    )
                    with os.fdopen(check, "rb") as handle:
                        if handle.read(10000) != encoded:
                            continue
                else:
                    with os.fdopen(writer, "wb") as handle:
                        handle.write(encoded)
                        handle.flush()
                        os.fsync(handle.fileno())
                current = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if (
                    current.st_dev,
                    current.st_ino,
                    current.st_mtime_ns,
                    current.st_size,
                ) != (opened.st_dev, opened.st_ino, opened.st_mtime_ns, opened.st_size):
                    continue
                os.unlink(name, dir_fd=fd)
                deleted += 1
            finally:
                os.close(reader)
    finally:
        os.close(fd)
    return deleted


def prune_evaluation_samples(cutoff):
    """Expire declared local evaluation outputs; keep input freezes and summaries."""
    audit = Path(config.WORKSPACE_ROOT).absolute().parent / "audit-results"
    root = audit / "sprint6-evaluation"
    deleted = 0
    if root.is_dir() and os.path.realpath(root) == str(root):
        for child in root.iterdir():
            if re.fullmatch(r"(?:development|held_out)-[0-9a-f]{32}", child.name):
                deleted += _expire_evaluation_directory(
                    child,
                    lambda name: re.fullmatch(r"slot-[0-9]{2}\.json", name) is not None,
                    cutoff,
                )
    real_job = audit / "sprint6-reinstatly"
    deleted += _expire_evaluation_directory(
        real_job,
        lambda name: re.fullmatch(
            r"llama3(?:\.1)?-(?:result\.json|decision-brief\.md)", name
        )
        is not None,
        cutoff,
    )
    generated = real_job / "generated/structured-decisions"
    if generated.is_dir() and os.path.realpath(generated) == str(generated):
        for child in generated.iterdir():
            if re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", child.name):
                deleted += _prune_directory(
                    str(child),
                    lambda name: re.fullmatch(
                        r"(?:input|brief|[a-z_]+-[12])\.json", name
                    )
                    is not None,
                    cutoff,
                )
    # Sprint 7 contains private input snapshots and assessments as well as raw
    # outputs. Expire those bytes too; counts/settings and hash receipts remain.
    for label in ("schema", "intake", "delivery", "reasoning", "transfer"):
        container = audit / ("sprint7-" + label)
        if not container.is_dir() or os.path.realpath(container) != str(container):
            continue
        for child in container.iterdir():
            if not re.fullmatch(r"(?:run|freeze)-[0-9a-f]{32}", child.name):
                continue
            deleted += _expire_evaluation_directory(
                child,
                lambda name: name
                in {
                    "freeze.json",
                    "cases.json",
                    "semantic-assessment.json",
                    "backend-tests.log",
                }
                or re.fullmatch(
                    r"(?:A_as_tested|B_replied|C_silent)-[1-3](?:-(?:baseline|candidate))?\.json",
                    name,
                )
                is not None,
                cutoff,
            )
    deleted += _expire_evaluation_directory(
        audit / "sprint7-diagnosis",
        lambda name: name == "owner-run-trace.json",
        cutoff,
    )
    return deleted
