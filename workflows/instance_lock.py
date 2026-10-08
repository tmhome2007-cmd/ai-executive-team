"""Keep startup reconciliation from changing another live server's claims."""
import os
import stat
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def database_instance_lock(database_path: str):
    import fcntl
    path = Path(database_path).absolute()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(str(path) + '.server.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_nlink != 1:
            raise RuntimeError('Unsafe application instance-lock file')
        os.fchmod(fd, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another application instance owns this database; recovery aborted') from None
        yield
    finally:
        # Never unlink: another process may already hold this same inode open.
        os.close(fd)
