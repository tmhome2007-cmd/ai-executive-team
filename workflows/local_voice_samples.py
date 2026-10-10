"""Owner-only auditions of a fixed public sentence; no runtime/cloud synthesis."""

import io
import os
from pathlib import Path
import stat
import wave

ASSET_ROOT = Path(__file__).resolve().parents[1] / ".voice-assets"
SAMPLE_TEXT = "Hello. Let us review the evidence, identify what is unknown, and choose the next step together."
VOICES = {
    "am_michael": "Michael · US masculine",
    "am_fenrir": "Fenrir · US masculine",
    "am_adam": "Adam · US masculine",
    "af_heart": "Heart · US feminine",
    "af_bella": "Bella · US feminine",
    "af_sarah": "Sarah · US feminine",
}
MAX_AUDIO_BYTES = 4 * 1024 * 1024


def sample_audio(voice):
    if not isinstance(voice, str) or voice not in VOICES:
        raise ValueError("Unknown neural voice")
    # Fixed allowlisted names; descriptor-relative opens reject link escapes.
    try:
        directory = os.open(ASSET_ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            fd = os.open(
                voice + ".wav",
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=directory,
            )
        finally:
            os.close(directory)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or not 44 <= info.st_size <= MAX_AUDIO_BYTES
            ):
                raise ValueError("Invalid local voice sample")
            data = stream.read(MAX_AUDIO_BYTES + 1)
        with wave.open(io.BytesIO(data), "rb") as recording:
            if (
                recording.getnchannels() != 1
                or recording.getsampwidth() != 2
                or recording.getframerate() != 24000
                or not 0 < recording.getnframes() <= 24000 * 60
            ):
                raise ValueError("Invalid local voice sample")
            if (
                len(recording.readframes(recording.getnframes()))
                != recording.getnframes() * 2
            ):
                raise ValueError("Truncated local voice sample")
        return data
    except (OSError, EOFError, wave.Error):
        raise LookupError(
            "Local neural samples unavailable. Run ./company voices once."
        ) from None


def sample_catalog():
    result = []
    for key, label in VOICES.items():
        try:
            sample_audio(key)
            available = True
        except (ValueError, LookupError):
            available = False
        result.append({"id": key, "label": label, "available": available})
    return {
        "voices": result,
        "text": SAMPLE_TEXT,
        "scope": "Fixed audition only; generated conversations are not voiced by this engine yet.",
    }
