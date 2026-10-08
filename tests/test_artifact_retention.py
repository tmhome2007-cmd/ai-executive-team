import os
import tempfile
import time
import unittest
from pathlib import Path
from config import config
from memory.database import init_db, get_connection
from memory.artifact_retention import register_sync_export, prune_generated_artifacts


class ArtifactRetentionTests(unittest.TestCase):
    def test_expiry_preserves_recent_unknown_linked_files_and_database_history(self):
        saved = config.DATABASE_PATH, config.WORKSPACE_ROOT, config.SYNC_EXPORT_DIR, config.ARTIFACT_RETENTION_DAYS
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp:
            temp = os.path.realpath(temp)
            try:
                os.chdir(temp)
                config.DATABASE_PATH = str(Path(temp) / 'history.db')
                config.WORKSPACE_ROOT = str(Path(temp) / 'workspace')
                config.SYNC_EXPORT_DIR = str(Path(temp) / 'sync')
                config.ARTIFACT_RETENTION_DAYS = 30
                init_db()
                paths = ['logs/app.log.1', 'logs/app.log', 'logs/unrelated.txt',
                         'workspace/screenshots/action_old.png', 'workspace/screenshots/action_recent.png',
                         'sync/generated.jsonl', 'sync/unregistered.jsonl', 'outside.txt']
                now = time.time()
                old = now - 31*86400
                for name in paths:
                    p = Path(name); p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text('Synthetic only')
                    os.utime(p, (old, old))
                os.utime('workspace/screenshots/action_recent.png', (now, now))
                os.symlink(str(Path(temp) / 'outside.txt'), 'workspace/screenshots/action_link.png')
                os.link('outside.txt', 'workspace/screenshots/action_hardlink.png')
                register_sync_export(str(Path(temp) / 'sync/generated.jsonl'))
                with get_connection() as conn:
                    conn.execute('UPDATE generated_sync_exports SET generated_at = ?', (old,))
                    conn.commit()
                self.assertEqual(prune_generated_artifacts(now=now), {'logs':1,'screenshots':1,'sync_exports':1})
                for name in ['logs/app.log', 'logs/unrelated.txt', 'workspace/screenshots/action_recent.png',
                             'workspace/screenshots/action_link.png', 'workspace/screenshots/action_hardlink.png',
                             'sync/unregistered.jsonl', 'outside.txt', 'history.db']:
                    self.assertTrue(Path(name).exists(), name)
                with get_connection() as conn:
                    self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                config.ARTIFACT_RETENTION_DAYS = 0
                with self.assertRaises(ValueError):
                    prune_generated_artifacts()
            finally:
                os.chdir(cwd)
                config.DATABASE_PATH, config.WORKSPACE_ROOT, config.SYNC_EXPORT_DIR, config.ARTIFACT_RETENTION_DAYS = saved

    def test_low_volume_active_log_rotates_before_expired_records_are_pruned(self):
        import datetime
        import logging
        from logging_config import PrivateRotatingFileHandler
        from memory.artifact_retention import _prune_directory
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            path = Path(temp) / "app.log"
            old = time.time() - 31 * 86400
            stamp = datetime.datetime.fromtimestamp(old).strftime("%Y-%m-%d %H:%M:%S")
            path.write_text(stamp + " | INFO | synthetic old record\n")
            os.utime(path, (old, old))
            handler = PrivateRotatingFileHandler(path, maxBytes=4096, backupCount=3)
            try:
                handler.emit(logging.LogRecord("test", logging.INFO, "", 0, "synthetic new record", (), None))
                self.assertIn("synthetic new record", path.read_text())
                self.assertNotIn("old record", path.read_text())
                self.assertEqual(_prune_directory(temp, lambda name: name == "app.log.1", time.time()-30*86400), 1)
                self.assertTrue(path.exists())
            finally:
                handler.close()
