"""Verify SQLite backup recovery, retention and unsafe path rejection."""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from config import config
from memory.database import init_db, backup_database


class BackupRecoveryTests(unittest.TestCase):
    def test_consistent_backup_can_be_restored_and_verified(self):
        prior = config.DATABASE_PATH
        with tempfile.TemporaryDirectory() as temporary:
            try:
                config.DATABASE_PATH = str(Path(temporary) / "primary.db")
                init_db()
                with sqlite3.connect(config.DATABASE_PATH) as db:
                    db.execute("CREATE TABLE recovery_probe (message TEXT)")
                    db.execute("INSERT INTO recovery_probe VALUES (?)", ("restorable",))
                    db.commit()
                backup_dir = Path(temporary) / "backups"
                snapshot = backup_database(str(backup_dir), keep_last=1)
                with sqlite3.connect(snapshot) as restored:
                    self.assertEqual(
                        restored.execute("PRAGMA integrity_check").fetchone()[0], "ok"
                    )
                    self.assertEqual(
                        restored.execute(
                            "SELECT message FROM recovery_probe"
                        ).fetchone()[0],
                        "restorable",
                    )
                self.assertEqual(os.stat(snapshot).st_mode & 0o777, 0o600)
                with self.assertRaises(ValueError):
                    backup_database(str(backup_dir), keep_last=0)
                self.assertTrue(Path(snapshot).exists())
                link = Path(temporary) / "linked_backup"
                link.symlink_to(backup_dir, target_is_directory=True)
                with self.assertRaises(ValueError):
                    backup_database(str(link), keep_last=1)
            finally:
                config.DATABASE_PATH = prior


if __name__ == "__main__":
    unittest.main()
