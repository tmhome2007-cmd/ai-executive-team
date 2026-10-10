"""Regression checks for encrypted backup."""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
from config import config
from memory.database import init_db, backup_database, create_company_goal
from memory.encrypted_backup import restore_encrypted_database


class EncryptedBackupTests(unittest.TestCase):
    def test_authenticated_restore_retention_and_no_plaintext_fallback(self):
        saved = config.DATABASE_PATH, config.BACKUP_ENCRYPTION_KEY
        with tempfile.TemporaryDirectory() as temp:
            try:
                config.DATABASE_PATH = str(Path(temp) / "source.db")
                config.BACKUP_ENCRYPTION_KEY = Fernet.generate_key().decode()
                init_db()
                create_company_goal("Private test evidence", "Test only", "Test only")
                directory = str(Path(temp) / "backups")
                first = backup_database(directory, keep_last=1)
                backup = backup_database(directory, keep_last=1)
                self.assertFalse(Path(first).exists())
                self.assertNotIn(b"Private test evidence", Path(backup).read_bytes())
                self.assertEqual(os.stat(backup).st_mode & 0o777, 0o600)
                target = str(Path(temp) / "restored.db")
                with self.assertRaises(InvalidToken):
                    restore_encrypted_database(
                        backup, target, Fernet.generate_key().decode()
                    )
                self.assertFalse(Path(target).exists())
                restore_encrypted_database(backup, target, config.BACKUP_ENCRYPTION_KEY)
                with sqlite3.connect(target) as conn:
                    self.assertEqual(
                        conn.execute("PRAGMA integrity_check").fetchone()[0], "ok"
                    )
                    self.assertEqual(
                        conn.execute("SELECT title FROM company_goals").fetchone()[0],
                        "Private test evidence",
                    )
                with self.assertRaises(FileExistsError):
                    restore_encrypted_database(
                        backup, target, config.BACKUP_ENCRYPTION_KEY
                    )
                corrupted = bytearray(Path(backup).read_bytes())
                corrupted[len(corrupted) // 2] ^= 1
                Path(backup).write_bytes(corrupted)
                with self.assertRaises(InvalidToken):
                    restore_encrypted_database(
                        backup,
                        str(Path(temp) / "tampered.db"),
                        config.BACKUP_ENCRYPTION_KEY,
                    )
                config.BACKUP_ENCRYPTION_KEY = "invalid-key"
                with self.assertRaises(ValueError):
                    backup_database(directory)
                self.assertEqual(len(list(Path(directory).iterdir())), 1)
            finally:
                config.DATABASE_PATH, config.BACKUP_ENCRYPTION_KEY = saved
