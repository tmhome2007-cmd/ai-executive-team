"""Explicit local voice installation; never sends company text or changes core dependencies."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import requests
ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'.voice-assets'
MODELS={
 'kokoro-v1.0.onnx':('beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a',325505369),
 'voices-v1.0.bin':('bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d',28214398),
}


def main():
    print('Preparing local neural auditions (~354 MB model assets plus isolated dependencies). Public downloads only; no company text is sent.',flush=True)
    if ASSETS.is_symlink() or (ROOT/'.voice-venv').is_symlink(): raise RuntimeError('Refusing linked voice directories')
    ASSETS.mkdir(mode=0o700,exist_ok=True);os.chmod(ASSETS,0o700)
    python=ROOT/'.voice-venv/bin/python'
    if not python.exists(): subprocess.run([sys.executable,'-m','venv',str(ROOT/'.voice-venv')],check=True)
    subprocess.run([str(python),'-m','pip','install','-r',str(ROOT/'requirements-voices.txt')],check=True)
    for name,(digest,size) in MODELS.items():
        target=ASSETS/name
        if target.is_symlink(): raise RuntimeError('Refusing linked model file')
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==digest: continue
        temporary=ASSETS/(name+'.download')
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        try:
            with os.fdopen(fd,'wb') as output,requests.get('https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/'+name,stream=True,timeout=60) as response:
                response.raise_for_status();count=0;hasher=hashlib.sha256()
                for chunk in response.iter_content(1024*1024):
                    count+=len(chunk)
                    if count>size: raise RuntimeError('Model exceeds expected size')
                    hasher.update(chunk);output.write(chunk)
            if count!=size or hasher.hexdigest()!=digest: raise RuntimeError('Model integrity verification failed')
            os.replace(temporary,target)
        finally:
            if temporary.exists(): temporary.unlink()
        print('Verified model:',name,flush=True)
    subprocess.run([str(python),str(ROOT/'scripts/generate_voice_samples.py')],check=True,timeout=300)
    print('Local auditions ready. Refresh Characters; choose Neural voice auditions.',flush=True)

if __name__=='__main__': main()
