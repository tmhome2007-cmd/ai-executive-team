"""Optional isolated neural runtime; consumes verified local assets and fixed text."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workflows.local_voice_samples import ASSET_ROOT, VOICES, SAMPLE_TEXT
import espeakng_loader
import tempfile
import shutil
import onnxruntime

onnxruntime.disable_telemetry_events()
from kokoro_onnx import Kokoro
import soundfile

# The bundled espeak library cannot initialize its data at this long checkout path.
# A disposable short data path avoids its path-length limit without altering the package.
with tempfile.TemporaryDirectory(prefix="voice-") as raw:
    data = Path(raw) / "data"
    shutil.copytree(espeakng_loader.get_data_path(), data)
    from kokoro_onnx import EspeakConfig

    engine = Kokoro(
        str(ASSET_ROOT / "kokoro-v1.0.onnx"),
        str(ASSET_ROOT / "voices-v1.0.bin"),
        espeak_config=EspeakConfig(data_path=str(data)),
    )
    for voice in VOICES:
        audio, rate = engine.create(SAMPLE_TEXT, voice=voice, speed=1.0, lang="en-us")
        target = ASSET_ROOT / (voice + ".wav")
        if target.is_symlink():
            raise RuntimeError("Refusing linked sample")
        temporary = ASSET_ROOT / (voice + ".tmp.wav")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        try:
            soundfile.write(str(temporary), audio, rate, subtype="PCM_16")
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
        print("Generated local sample:", voice, flush=True)
