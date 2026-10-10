"""Disposable artifact confinement, recovery, expiry and owner API checks."""

import os
import sqlite3
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from tests import test_sprint3_practice_evidence as fixtures
from memory.database import get_connection
from memory.practice_artifacts import (
    export_sample,
    list_artifacts,
    download_artifact,
    compare_artifacts,
    prune_artifacts,
)


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        fixtures.SprintThreeTests.setUp(self)
        from config import config

        config.DATABASE_PATH = str(Path(config.DATABASE_PATH).resolve())

    tearDown = fixtures.SprintThreeTests.tearDown
    payload = fixtures.SprintThreeTests.payload
    brief = fixtures.SprintThreeTests.brief
    sample = fixtures.SprintThreeTests.sample
    assess = fixtures.SprintThreeTests.assess

    def saved(self):
        b = self.sample(self.brief())
        return b, b["attempts"][-1]["id"]

    def path(self, ident):
        with get_connection() as conn:
            key = conn.execute(
                "SELECT storage_key FROM practice_artifacts WHERE id=?", (ident,)
            ).fetchone()[0]
        return Path(self.temp.name) / "practice-artifacts" / key

    def test_exact_private_export_and_retry(self):
        b, sample = self.saved()
        a = export_sample(sample, "txt")
        self.assertEqual(
            download_artifact(a["id"])[0].decode(), b["attempts"][-1]["sample"]
        )
        self.assertEqual(self.path(a["id"]).stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.path(a["id"]).parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(export_sample(sample, "txt")["id"], a["id"])
        self.assertEqual(a["provenance"]["source_sample_id"], sample)
        self.assertTrue(a["provenance"]["rubric_digest"])
        self.assertEqual(len(a["provenance"]["source_records"]), 3)
        with get_connection() as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("DELETE FROM practice_artifacts WHERE id=?", (a["id"],))

    def test_expiry_keeps_metadata_and_cannot_reset_clock(self):
        b, sample = self.saved()
        a = export_sample(sample, "md")
        expiry = a["expires_at"]
        with patch("memory.practice_artifacts.time.time", return_value=expiry):
            self.assertEqual(prune_artifacts(), 1)
            self.assertEqual(export_sample(sample, "md")["availability"], "expired")
            self.assertEqual(list_artifacts(b["id"])[0]["expires_at"], expiry)
            with self.assertRaisesRegex(RuntimeError, "expired"):
                download_artifact(a["id"])
        with get_connection() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT count(*) FROM business_practice_samples"
                ).fetchone()[0],
                1,
            )

    def test_missing_corrupt_symlink_hardlink_and_directory_escape(self):
        _, sample = self.saved()
        a = export_sample(sample, "txt")
        p = self.path(a["id"])
        original = p.read_bytes()
        p.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "integrity"):
            download_artifact(a["id"])
        p.unlink()
        self.assertEqual(export_sample(sample, "txt")["availability"], "missing")
        target = Path(self.temp.name) / "outside"
        target.write_bytes(original)
        p.symlink_to(target)
        with self.assertRaises(ValueError):
            download_artifact(a["id"])
        prune_artifacts(now=a["expires_at"] + 1)
        self.assertTrue(target.exists())
        self.assertTrue(p.is_symlink())
        p.unlink()
        os.link(target, p)
        with self.assertRaises(ValueError):
            download_artifact(a["id"])
        self.assertEqual(prune_artifacts(now=a["expires_at"] + 1), 0)

    def test_compare_requires_same_exercise(self):
        b, sample = self.saved()
        a = export_sample(sample, "txt")
        same = export_sample(sample, "md")
        self.assertTrue(compare_artifacts(a["id"], same["id"])["identical"])
        other = self.sample(self.brief(facts="Other fictional facts"))
        different = export_sample(other["attempts"][-1]["id"], "txt")
        with self.assertRaises(ValueError):
            compare_artifacts(a["id"], different["id"])
        b = self.assess(b, [False, True])
        b = self.sample(b, revision=True)
        revision = export_sample(b["attempts"][-1]["id"], "txt")
        self.assertEqual(revision["provenance"]["parent_sample_id"], sample)
        self.assertTrue(revision["provenance"]["feedback_review_id"])
        self.assertEqual(
            compare_artifacts(a["id"], revision["id"])["after_id"], revision["id"]
        )

    def test_crash_orphans_and_unrelated_files(self):
        _, sample = self.saved()
        a = export_sample(sample, "txt")
        d = self.path(a["id"]).parent
        orphan = d / ("f" * 32 + ".data")
        orphan.write_bytes(b"orphan")
        orphan.chmod(0o600)
        unrelated = d / "notes.txt"
        unrelated.write_text("keep")
        old = time.time() - 31 * 86400
        os.utime(orphan, (old, old))
        self.assertEqual(prune_artifacts(), 1)
        self.assertTrue(unrelated.exists())
        self.assertTrue(self.path(a["id"]).exists())

    def test_failed_database_publish_cleans_file(self):
        _, sample = self.saved()
        with get_connection() as conn:
            conn.execute(
                "CREATE TRIGGER artifact_fail BEFORE INSERT ON practice_artifacts BEGIN SELECT RAISE(ABORT,'fixture failure'); END"
            )
            conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            export_sample(sample, "txt")
        self.assertEqual(
            list((Path(self.temp.name) / "practice-artifacts").iterdir()), []
        )

    def test_reject_paths_and_owner_api_headers(self):
        _, sample = self.saved()
        for kind in ("../x", "html", "js"):
            with self.assertRaises(ValueError):
                export_sample(sample, kind)
        from fastapi.testclient import TestClient
        from main import app
        from config import config

        with patch.object(config, "API_SECRET_KEY", "artifact-fixture-key"):
            client = TestClient(app)
            self.assertEqual(
                client.get("/practice-artifacts?brief_id=1").status_code, 401
            )
            headers = {"X-API-Key": "artifact-fixture-key"}
            result = client.post(
                "/practice-artifacts",
                headers=headers,
                json=dict(sample_id=sample, kind="txt"),
            )
            self.assertEqual(result.status_code, 200, result.text)
            ident = result.json()["id"]
            response = client.get(
                f"/practice-artifacts/{ident}/download", headers=headers
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertEqual(response.headers["x-content-type-options"], "nosniff")
            self.assertIn("attachment", response.headers["content-disposition"])
            self.assertEqual(
                client.post(
                    "/practice-artifacts",
                    headers=headers,
                    json=dict(sample_id=sample, kind="txt", path="../x"),
                ).status_code,
                422,
            )

    def test_active_content_and_oversize_are_not_published(self):
        from memory.business_discovery import claim_stage, finish_stage

        for text in (
            "<script>alert(1)</script>",
            "[link](javascript:alert(1))",
            "bad\x00text",
        ):
            b = self.brief()
            b = claim_stage(b["id"], b["version"], "practice")
            b = finish_stage(b["id"], "practice", text, b["version"])
            with self.assertRaises(ValueError):
                export_sample(b["attempts"][-1]["id"], "md")
            self.assertEqual(list_artifacts(b["id"]), [])
        b, sample = self.saved()
        with patch("memory.practice_artifacts.MAX_BYTES", 10):
            with self.assertRaisesRegex(ValueError, "no truncation"):
                export_sample(sample, "txt")

    def test_directory_and_parent_symlinks_are_rejected(self):
        from config import config

        b, sample = self.saved()
        target = Path(self.temp.name) / "elsewhere"
        target.mkdir()
        (Path(self.temp.name) / "practice-artifacts").symlink_to(
            target, target_is_directory=True
        )
        with self.assertRaises(ValueError):
            export_sample(sample, "txt")
        self.assertEqual(list(target.iterdir()), [])
        (Path(self.temp.name) / "practice-artifacts").unlink()
        parent = Path(self.temp.name) / "alias"
        parent.symlink_to(Path(self.temp.name), target_is_directory=True)
        with patch.object(config, "DATABASE_PATH", str(parent / "test.db")):
            with self.assertRaisesRegex(ValueError, "symlinks"):
                export_sample(sample, "txt")

    def test_changed_revision_diff_is_literal_text(self):
        from memory.business_discovery import claim_stage, finish_stage

        b, sample = self.saved()
        before = export_sample(sample, "txt")
        b = self.assess(b, [False, True])
        b = claim_stage(b["id"], b["version"], "revision")
        b = finish_stage(
            b["id"],
            "revision",
            "A revised fictional sample. Unknown details remain unknown.",
            b["version"],
        )
        after = export_sample(b["attempts"][-1]["id"], "md")
        result = compare_artifacts(before["id"], after["id"])
        self.assertFalse(result["identical"])
        self.assertIn("+A revised fictional sample.", result["diff"])
        self.assertIn("-Fictional private sample", result["diff"])

    def test_expiry_boundary_and_concurrent_removal_are_honest(self):
        from memory.practice_artifacts import _public

        _, sample = self.saved()
        a = export_sample(sample, "txt")
        with get_connection() as conn:
            row = dict(
                conn.execute(
                    "SELECT * FROM practice_artifacts WHERE id=?", (a["id"],)
                ).fetchone()
            )
        with patch(
            "memory.practice_artifacts.time.time",
            side_effect=[a["expires_at"] - 1, a["expires_at"]],
        ):
            self.assertEqual(_public(row)["availability"], "expired")
        with patch("memory.practice_artifacts.os.stat", side_effect=FileNotFoundError):
            self.assertEqual(prune_artifacts(now=a["expires_at"] + 1), 0)
