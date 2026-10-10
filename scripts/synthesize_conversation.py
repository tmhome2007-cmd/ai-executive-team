"""Bounded isolated local speech worker. Private input via stdin; WAV via stdout."""
import io
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import tempfile
# The worker has no network use, model download or company credentials.
def deny(*args,**kwargs): raise RuntimeError('Speech network access disabled')
socket.socket.connect=deny
socket.socket.connect_ex=deny
socket.create_connection=deny
import onnxruntime
onnxruntime.disable_telemetry_events()
import espeakng_loader
from kokoro_onnx import Kokoro, EspeakConfig
import soundfile
payload=json.loads(sys.stdin.buffer.read(10000))
if set(payload)!={'text','voice'} or not isinstance(payload['text'],str) or not 0<len(payload['text'])<=1200 or payload['voice'] not in {'am_michael','am_fenrir','am_adam','af_heart','af_bella','af_sarah'}:
    raise ValueError('Invalid speech request')
assets=Path(__file__).resolve().parents[1]/'.voice-assets'
with tempfile.TemporaryDirectory(prefix='speech-') as raw:
    data=Path(raw)/'data';shutil.copytree(espeakng_loader.get_data_path(),data)
    options=onnxruntime.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
    session=onnxruntime.InferenceSession(str(assets/'kokoro-v1.0.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
    engine=Kokoro.from_session(session,str(assets/'voices-v1.0.bin'),espeak_config=EspeakConfig(data_path=str(data)))
    audio,rate=engine.create(payload['text'],voice=payload['voice'],speed=1.0,lang='en-us')
    if rate!=24000 or not 0<len(audio)<=24000*120: raise ValueError('Speech duration exceeded')
    output=io.BytesIO();soundfile.write(output,audio,rate,format='WAV',subtype='PCM_16')
    sys.stdout.buffer.write(output.getvalue())
