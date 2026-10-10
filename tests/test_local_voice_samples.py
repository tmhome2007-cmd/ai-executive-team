"""Neural audition boundaries; tiny synthetic WAV fixtures, no model inference/network."""

import copy
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
from workflows import local_voice_samples as samples
from memory.character_profiles import default_presentation, validate_presentation


class LocalVoiceSamplesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.root_patch = patch.object(samples, "ASSET_ROOT", self.root)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def sample(self):
        path = self.root / "am_michael.wav"
        with wave.open(str(path), "wb") as recording:
            recording.setnchannels(1)
            recording.setsampwidth(2)
            recording.setframerate(24000)
            recording.writeframes(b"\0\0" * 2400)
        return path

    def test_audio_catalog_and_absent_models_fail_closed(self):
        self.assertFalse(
            any(v["available"] for v in samples.sample_catalog()["voices"])
        )
        with self.assertRaises(LookupError):
            samples.sample_audio("am_michael")
        self.sample()
        self.assertTrue(samples.sample_audio("am_michael").startswith(b"RIFF"))
        self.assertEqual(
            sum(v["available"] for v in samples.sample_catalog()["voices"]), 1
        )

    def test_path_links_malformed_and_oversized_files_rejected(self):
        self.sample()
        for invalid in ("../am_michael", "https://example.test/voice", "unknown"):
            with self.assertRaises(ValueError):
                samples.sample_audio(invalid)
        (self.root / "af_heart.wav").symlink_to(self.root / "am_michael.wav")
        with self.assertRaises(LookupError):
            samples.sample_audio("af_heart")
        (self.root / "am_michael.wav").write_bytes(b"not a wave")
        with self.assertRaises((ValueError, LookupError)):
            samples.sample_audio("am_michael")
        with (self.root / "am_michael.wav").open("wb") as stream:
            stream.truncate(samples.MAX_AUDIO_BYTES + 1)
        with self.assertRaises(ValueError):
            samples.sample_audio("am_michael")

    def test_truncated_frames_and_hardlinks_rejected(self):
        import os

        path = self.sample()
        path.write_bytes(path.read_bytes()[:-500])
        with self.assertRaises(ValueError):
            samples.sample_audio("am_michael")
        path = self.sample()
        os.link(path, self.root / "extra.wav")
        with self.assertRaises(ValueError):
            samples.sample_audio("am_michael")

    def test_neural_preferences_are_allowlisted_and_fixed_speed(self):
        profile = default_presentation("ceo")
        voice = dict(
            profile["voice"],
            provider="kokoro_local",
            voice_name="am_michael",
            language="en-US",
            pitch=1,
            rate=1,
        )
        self.assertEqual(
            validate_presentation(profile["appearance"], profile["body"], voice)[2][
                "provider"
            ],
            "kokoro_local",
        )
        for field, value in [
            ("voice_name", "unknown"),
            ("language", "en-GB"),
            ("pitch", 0.7),
            ("rate", 1.2),
            ("provider", "cloud"),
        ]:
            changed = copy.deepcopy(voice)
            changed[field] = value
            with self.assertRaises(ValueError):
                validate_presentation(profile["appearance"], profile["body"], changed)

    def test_api_requires_owner_key_and_returns_no_store_audio(self):
        from config import config
        from main import app
        from fastapi.testclient import TestClient

        with patch.object(
            config, "API_SECRET_KEY", "synthetic-voice-test-owner-key-1234567890"
        ):
            client = TestClient(app)
            self.assertEqual(client.get("/characters/voice-samples").status_code, 401)
            self.assertEqual(
                client.get("/characters/voice-samples/am_michael").status_code, 401
            )
            headers = {"X-API-Key": config.API_SECRET_KEY}
            self.sample()
            response = client.get(
                "/characters/voice-samples/am_michael", headers=headers
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertTrue(response.content.startswith(b"RIFF"))
            self.assertEqual(
                client.get(
                    "/characters/voice-samples/unknown", headers=headers
                ).status_code,
                400,
            )
            self.assertEqual(
                client.get(
                    "/characters/voice-samples/af_heart", headers=headers
                ).status_code,
                404,
            )
