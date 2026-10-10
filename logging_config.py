"""Private rotating application logs with shared secret redaction.

Centrale logging-configuratie voor het hele project. Tot nu toe gebruikte
elke module gewone print()-statements — prima voor interactief testen, maar
onbruikbaar zodra dit systeem weken achter elkaar autonoom draait: er is dan
geen doorzoekbare geschiedenis, geen niveau-onderscheid (DEBUG/INFO/WARNING/
ERROR), en de terminal-scrollback is de enige "log" die bestaat.

Gebruik in elke module:
    from logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("Iets gebeurde")
    logger.warning("Iets verdachts")
    logger.error("Iets ging mis", exc_info=True)
"""

import logging
import os
import datetime
import time
from logging.handlers import RotatingFileHandler

_LOG_DIR = os.getenv("LOG_DIR", "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "app.log")
_MAX_BYTES = max(
    1024,
    min(100 * 1024 * 1024, int(os.getenv("LOG_ROTATION_BYTES", str(5 * 1024 * 1024)))),
)
_BACKUP_COUNT = max(1, min(100, int(os.getenv("LOG_RETENTION_COUNT", "3"))))

_configured = False


class PrivateRotatingFileHandler(RotatingFileHandler):
    """Rotating handler that keeps current and rotated logs owner-only."""

    def _harden_permissions(self) -> None:
        backup_count = int(getattr(self, "backupCount", 0) or 0)
        for path in [self.baseFilename] + [
            f"{self.baseFilename}.{i}" for i in range(1, backup_count + 1)
        ]:
            if os.path.exists(path):
                try:
                    os.chmod(path, 0o600)
                except OSError:
                    pass

    def _open(self):
        # Age from the oldest entry, so an active low-volume log cannot keep
        # old records indefinitely by receiving occasional new messages.
        if not hasattr(self, "period_start"):
            self.period_start = time.time()
            try:
                with open(self.baseFilename, encoding="utf-8") as previous:
                    first = previous.readline(256)
                self.period_start = datetime.datetime.strptime(
                    first[:19], "%Y-%m-%d %H:%M:%S"
                ).timestamp()
            except (OSError, ValueError):
                pass
        stream = super()._open()
        self._harden_permissions()
        return stream

    def shouldRollover(self, record):
        return time.time() - self.period_start >= 86400 or super().shouldRollover(
            record
        )

    def doRollover(self):
        self.period_start = time.time()
        super().doRollover()
        self._harden_permissions()


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configureert de root logger EENMALIG bij het opstarten van de applicatie
    (aangeroepen vanuit main.py, vóór al het andere). Idempotent — een
    dubbele aanroep doet niets extra's.
    """
    global _configured
    if _configured:
        return

    os.makedirs(_LOG_DIR, mode=0o700, exist_ok=True)
    try:
        os.chmod(_LOG_DIR, 0o700)
    except OSError:
        pass

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    file_handler = PrivateRotatingFileHandler(
        _LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(
        logging.DEBUG
    )  # bestand bewaart alles, console toont minder ruis

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Bibliotheken zoals urllib3/telegram zijn vaak erg spraakzaam op DEBUG —
    # dat verdrinkt onze eigen logs. Ietwat temperen, zonder ze volledig stil
    # te maken (WARNING en hoger blijft altijd zichtbaar).
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Haalt een logger op voor de gegeven module (gebruik altijd __name__)."""
    if not _configured:
        setup_logging()
    return logging.getLogger(name)


def rotate_aged_active_log(*, now: float) -> None:
    """Rotate the current directory's active handler before age pruning."""
    target = os.path.abspath(_LOG_FILE)
    for handler in logging.getLogger().handlers:
        if (
            isinstance(handler, PrivateRotatingFileHandler)
            and handler.baseFilename == target
        ):
            handler.acquire()
            try:
                if now - handler.period_start >= 86400:
                    handler.doRollover()
            finally:
                handler.release()
