"""Private immutable sample exports; expiring bytes never confer approval."""

import difflib
import hashlib
import json
import os
import re
import stat
import time
import uuid
from pathlib import Path
from config import config
from memory.database import get_connection
from memory.business_evidence import research_context

MAX_BYTES = 120_000
RETENTION_SECONDS = 30 * 86400


def init_artifacts(cursor):
    cursor.execute("""CREATE TABLE IF NOT EXISTS practice_artifacts (
        id INTEGER PRIMARY KEY, sample_id INTEGER NOT NULL, brief_id INTEGER NOT NULL,
        version INTEGER NOT NULL, kind TEXT NOT NULL, sha256 TEXT NOT NULL,
        byte_count INTEGER NOT NULL, storage_key TEXT NOT NULL UNIQUE,
        provenance_json TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL,
        UNIQUE(sample_id,kind))""")
    cursor.execute(
        """CREATE TRIGGER IF NOT EXISTS practice_artifacts_no_update
        BEFORE UPDATE ON practice_artifacts BEGIN SELECT RAISE(ABORT,'Artifact metadata is immutable'); END"""
    )
    cursor.execute(
        """CREATE TRIGGER IF NOT EXISTS practice_artifacts_no_delete
        BEFORE DELETE ON practice_artifacts BEGIN SELECT RAISE(ABORT,'Artifact provenance is retained'); END"""
    )


def _directory(create=False):
    directory = Path(config.DATABASE_PATH).absolute().parent / "practice-artifacts"
    if os.path.realpath(directory.parent) != str(directory.parent):
        raise ValueError("Artifact parent must not contain symlinks")
    parent_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        # Walk each component with no-follow handles, including intermediate parents.
        for part in directory.parent.parts[1:]:
            next_fd = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd
            )
            os.close(parent_fd)
            parent_fd = next_fd
        if create:
            try:
                os.mkdir(directory.name, mode=0o700, dir_fd=parent_fd)
            except FileExistsError:
                pass
        fd = os.open(
            directory.name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
    except FileNotFoundError:
        raise
    except OSError:
        raise ValueError("Unsafe artifact directory") from None
    finally:
        os.close(parent_fd)
    metadata = os.fstat(fd)
    if metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
        os.close(fd)
        raise ValueError("Artifact directory must be private to its owner")
    return fd


def _bytes(fd, key):
    if not re.fullmatch(r"[0-9a-f]{32}\.data", key):
        raise ValueError("Invalid artifact storage key")
    handle = os.open(key, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    try:
        meta = os.fstat(handle)
        if (
            not stat.S_ISREG(meta.st_mode)
            or meta.st_nlink != 1
            or meta.st_uid != os.getuid()
            or meta.st_mode & 0o077
            or not 0 < meta.st_size <= MAX_BYTES
        ):
            raise ValueError("Unsafe artifact file")
        with os.fdopen(handle, "rb", closefd=False) as stream:
            value = stream.read(MAX_BYTES + 1)
        if len(value) > MAX_BYTES:
            raise ValueError("Artifact exceeds file limit")
        return value
    finally:
        os.close(handle)


def _record(conn, ident):
    row = conn.execute(
        "SELECT * FROM practice_artifacts WHERE id=?", (ident,)
    ).fetchone()
    if row is None:
        raise LookupError("Artifact not found")
    return dict(row)


def _content(row, now=None):
    if (time.time() if now is None else now) >= row["expires_at"]:
        raise RuntimeError(
            "Artifact expired; saved sample and review provenance remain"
        )
    fd = _directory()
    try:
        data = _bytes(fd, row["storage_key"])
    finally:
        os.close(fd)
    if (
        len(data) != row["byte_count"]
        or hashlib.sha256(data).hexdigest() != row["sha256"]
    ):
        raise ValueError("Artifact integrity check failed")
    return data


def _public(row):
    result = {
        k: v for k, v in row.items() if k not in {"storage_key", "provenance_json"}
    }
    result["provenance"] = json.loads(row["provenance_json"])
    result["filename"] = (
        f"practice-{row['brief_id']}-sample-{row['version']}.{row['kind']}"
    )
    if time.time() >= row["expires_at"]:
        result["availability"] = "expired"
    else:
        try:
            _content(row)
            result["availability"] = "available"
        except RuntimeError:
            result["availability"] = "expired"
        except FileNotFoundError:
            result["availability"] = "missing"
        except (OSError, ValueError):
            result["availability"] = "integrity_error"
    return result


def export_sample(sample_id, kind):
    """Export exact saved text once per format; retries cannot extend its expiry."""
    if type(sample_id) is not int or sample_id < 1 or kind not in {"txt", "md"}:
        raise ValueError("Choose a saved sample and txt or md format")
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            "SELECT * FROM practice_artifacts WHERE sample_id=? AND kind=?",
            (sample_id, kind),
        ).fetchone()
        if existing:
            return _public(dict(existing))
        sample = conn.execute(
            "SELECT * FROM business_practice_samples WHERE id=?", (sample_id,)
        ).fetchone()
        if sample is None:
            raise LookupError("Saved sample not found")
        specification = conn.execute(
            """SELECT p.* FROM practice_specifications p
            JOIN practice_sample_specifications b ON b.specification_id=p.id WHERE b.sample_id=?""",
            (sample_id,),
        ).fetchone()
        if specification is None:
            raise ValueError("Sample has no frozen rubric binding; export unavailable")
        text = sample["sample"]
        data = text.encode("utf-8")
        if not 0 < len(data) <= MAX_BYTES:
            raise ValueError("Sample must fit 120000 UTF-8 bytes; no truncation")
        # Export only inert prose. Do not render Markdown as HTML or execute code.
        if re.search(
            r"<\s*/?\s*[a-z!]|(?:javascript|vbscript|data)\s*:|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]",
            text,
            re.I,
        ):
            raise ValueError(
                "Active markup, unsafe URL schemes or control bytes are not exportable"
            )
        skill = conn.execute(
            "SELECT skill_id FROM practice_skill_bindings WHERE brief_id=?",
            (sample["brief_id"],),
        ).fetchone()
        provenance = dict(
            specification_id=specification["id"],
            rubric_digest=specification["rubric_digest"],
            source_sample_id=sample_id,
            parent_sample_id=sample["parent_sample_id"],
            feedback_review_id=sample["feedback_review_id"],
            source_sha256=hashlib.sha256(data).hexdigest(),
            skill_version_id=skill[0] if skill else None,
            source_records=research_context(conn.cursor(), sample["brief_id"]),
            scope="Exact saved AI sample; export is not an assessment or launch approval",
        )
        fd = _directory(create=True)
        key = uuid.uuid4().hex + ".data"
        written = False
        try:
            # Per-checkout bound; expired and crash-orphan files are pruned separately.
            if len(os.listdir(fd)) >= 1000:
                raise RuntimeError(
                    "Private workspace file limit reached; prune expired files"
                )
            handle = os.open(
                key,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=fd,
            )
            written = True
            with os.fdopen(handle, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.fsync(fd)
            now = time.time()
            conn.execute(
                """INSERT INTO practice_artifacts(sample_id,brief_id,version,kind,sha256,byte_count,storage_key,provenance_json,created_at,expires_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    sample_id,
                    sample["brief_id"],
                    sample["attempt"],
                    kind,
                    hashlib.sha256(data).hexdigest(),
                    len(data),
                    key,
                    json.dumps(provenance),
                    now,
                    now + RETENTION_SECONDS,
                ),
            )
            ident = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            row = _record(conn, ident)
            conn.commit()
        except BaseException as error:
            if written:
                try:
                    os.unlink(key, dir_fd=fd)
                except FileNotFoundError:
                    pass
            if isinstance(error, OSError):
                raise RuntimeError(
                    "Private file storage unavailable; no export was published"
                ) from None
            raise
        finally:
            os.close(fd)
        return _public(row)


def list_artifacts(brief_id, limit=100, offset=0):
    with get_connection() as conn:
        return [
            _public(dict(row))
            for row in conn.execute(
                "SELECT * FROM practice_artifacts WHERE brief_id=? ORDER BY version,id LIMIT ? OFFSET ?",
                (brief_id, limit, offset),
            )
        ]


def download_artifact(ident):
    with get_connection() as conn:
        row = _record(conn, ident)
    try:
        return (
            _content(row),
            f"practice-{row['brief_id']}-sample-{row['version']}.{row['kind']}",
        )
    except FileNotFoundError:
        raise RuntimeError("Artifact bytes unavailable; metadata remains") from None
    except OSError:
        raise ValueError("Unsafe artifact file or directory") from None


def compare_artifacts(before_id, after_id):
    with get_connection() as conn:
        before, after = _record(conn, before_id), _record(conn, after_id)
    a, b = json.loads(before["provenance_json"]), json.loads(after["provenance_json"])
    if (
        before["brief_id"] != after["brief_id"]
        or a["specification_id"] != b["specification_id"]
    ):
        raise ValueError("Compare artifacts from the same frozen exercise")
    first, _ = download_artifact(before_id)
    second, _ = download_artifact(after_id)
    # Bound work and response for adversarial many-line samples.
    left, right = (
        first.decode("utf-8").splitlines(),
        second.decode("utf-8").splitlines(),
    )
    if len(left) > 2000 or len(right) > 2000:
        raise ValueError("Comparison supports at most 2000 lines per artifact")
    diff = "\n".join(
        difflib.unified_diff(
            left,
            right,
            fromfile=f'sample-{before["version"]}',
            tofile=f'sample-{after["version"]}',
            lineterm="",
        )
    )
    if len(diff.encode("utf-8")) > 2 * MAX_BYTES + 10000:
        raise ValueError("Comparison exceeds output limit")
    return dict(
        before_id=before_id,
        after_id=after_id,
        identical=first == second,
        diff=diff,
        scope="Text differences only; quality and owner assessments remain separate",
    )


def prune_artifacts(now=None):
    """Remove expired owned files and 30-day crash orphans, keeping all metadata."""
    current = time.time() if now is None else now
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT storage_key,expires_at FROM practice_artifacts"
        ).fetchall()
    registered = {row["storage_key"]: row["expires_at"] for row in rows}
    try:
        fd = _directory()
    except FileNotFoundError:
        return 0
    deleted = 0
    try:
        for name in os.listdir(fd):
            if not re.fullmatch(r"[0-9a-f]{32}\.data", name):
                continue
            try:
                meta = os.stat(name, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                continue
            expiry = registered.get(name, meta.st_mtime + RETENTION_SECONDS)
            if (
                expiry <= current
                and stat.S_ISREG(meta.st_mode)
                and meta.st_nlink == 1
                and meta.st_uid == os.getuid()
                and not meta.st_mode & 0o077
            ):
                try:
                    os.unlink(name, dir_fd=fd)
                    deleted += 1
                except FileNotFoundError:
                    continue
    finally:
        os.close(fd)
    return deleted
