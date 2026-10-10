"""Explicit owner-requested, bounded local speech; source/profile-bound private cache."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import threading
import time
import wave
from config import config
from memory.database import get_connection
from memory.character_profiles import get_character
from workflows.local_voice_samples import VOICES, ASSET_ROOT

ROOT = Path(__file__).resolve().parents[1]
MAX_TEXT = 12000
MAX_BYTES = 64 * 1024 * 1024
MAX_FILES = 40
MAX_CACHE_BYTES = 256 * 1024 * 1024
MODEL_DIGESTS = {'kokoro-v1.0.onnx': 'beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a',
                 'voices-v1.0.bin': 'bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d'}
_BUSY = threading.Lock()
_JOBS_LOCK = threading.Lock()
_JOBS = {}
_VERIFIED = set()


def init_audio(cursor):
    cursor.execute('''CREATE TABLE IF NOT EXISTS conversation_audio (
        cache_key TEXT PRIMARY KEY, source_kind TEXT NOT NULL, source_id INTEGER NOT NULL,
        executive_key TEXT NOT NULL, profile_version INTEGER NOT NULL, voice TEXT NOT NULL,
        source_digest TEXT NOT NULL, speech_digest TEXT NOT NULL, audio_digest TEXT NOT NULL,
        created_at REAL NOT NULL, expires_at REAL NOT NULL, duration REAL NOT NULL)''')
    cursor.execute("CREATE TRIGGER IF NOT EXISTS conversation_audio_no_update BEFORE UPDATE ON conversation_audio BEGIN SELECT RAISE(ABORT,'Audio provenance is immutable'); END")


def _directory():
    directory = Path(config.DATABASE_PATH).absolute().parent / 'conversation-audio'
    if Path(os.path.realpath(directory.parent)) != directory.parent:
        raise ValueError('Audio directory must have canonical owner-controlled parents')
    directory.mkdir(mode=0o700, exist_ok=True)
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    info = os.fstat(fd)
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        os.close(fd)
        raise ValueError('Audio directory must be owner-only')
    return fd


def _read(fd, name):
    handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    with os.fdopen(handle, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or info.st_mode & 0o077 or not 44 <= info.st_size <= MAX_BYTES:
            raise ValueError('Unsafe audio cache file')
        return stream.read(MAX_BYTES + 1)


def validate_wave(data):
    if len(data) > MAX_BYTES: raise ValueError('Audio exceeds size limit')
    try:
        with wave.open(io.BytesIO(data), 'rb') as audio:
            frames = audio.getnframes()
            if audio.getnchannels()!=1 or audio.getsampwidth()!=2 or audio.getframerate()!=24000 or not 0 < frames <= 24000*1200:
                raise ValueError('Invalid audio format or duration')
            if len(audio.readframes(frames)) != frames*2: raise ValueError('Truncated audio')
            return frames/24000
    except (wave.Error, EOFError): raise ValueError('Invalid audio response') from None


def spoken_text(body):
    # Speak published text, never generate a new recommendation or read URL targets.
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', body)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'(?m)^\s*(?:#{1,6}|[-*+] |\d+[.)] )', '', text)
    text = text.replace('**', '').replace('`', '')
    text = ' '.join(text.split())
    if not text or len(text)>MAX_TEXT:
        raise ValueError(f'Contribution must fit {MAX_TEXT} spoken characters; no silent truncation. Choose a shorter contribution.')
    return text


def source(kind, ident):
    with get_connection() as conn:
        if kind=='contribution':
            row=conn.execute('SELECT executive_key,body FROM decision_contributions WHERE id=?',(ident,)).fetchone()
        elif kind=='discussion':
            row=conn.execute('SELECT executive_key,body FROM discussion_messages WHERE id=?',(ident,)).fetchone()
        else: raise ValueError('Choose a published contribution or discussion message')
    if not row: raise LookupError('Published contribution not found')
    profile=get_character('executive:'+row['executive_key'])
    voice=profile['voice']
    if voice['provider']!='kokoro_local' or voice['voice_name'] not in VOICES:
        raise RuntimeError('Choose and save a local neural voice for this executive in People & simulation first. No voice is substituted.')
    return dict(row), profile


def verify_runtime():
    python=ROOT/'.voice-venv/bin/python'
    if not python.is_file() or (ROOT/'.voice-venv').is_symlink():
        raise RuntimeError('Install local voices with ./company voices first')
    if ASSET_ROOT.is_symlink() or Path(os.path.realpath(ASSET_ROOT)) != ASSET_ROOT:
        raise ValueError('Unsafe voice asset directory')
    for name, digest in MODEL_DIGESTS.items():
        handle=os.open(ASSET_ROOT/name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(handle,'rb') as stream:
            info=os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1: raise ValueError('Unsafe voice model')
            fingerprint=(name,info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)
            if fingerprint not in _VERIFIED:
                hasher=hashlib.sha256()
                for chunk in iter(lambda: stream.read(1024*1024), b''): hasher.update(chunk)
                if hasher.hexdigest()!=digest: raise ValueError('Voice model integrity check failed; reinstall local voices')
                _VERIFIED.add(fingerprint)
    return python


def cancel(request_id):
    with _JOBS_LOCK:
        job=_JOBS.get(request_id)
        if job:
            job['cancelled'].set()
            if job['process'] is not None and job['process'].poll() is None: job['process'].terminate()
    return {'cancel_requested': bool(job)}


def synthesize(text, voice, job):
    try: python=verify_runtime()
    except OSError: raise RuntimeError('Local voice assets unavailable. Run ./company voices first') from None
    env={key:os.environ[key] for key in ('PATH','LANG','LC_ALL','TMPDIR') if key in os.environ}
    env.update({'OMP_NUM_THREADS':'2','CREWAI_DISABLE_TELEMETRY':'true','HF_HUB_OFFLINE':'1','DO_NOT_TRACK':'1'})
    process=subprocess.Popen([str(python),'-I',str(ROOT/'scripts/synthesize_conversation.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env=env)
    with _JOBS_LOCK:
        job['process']=process
        if job['cancelled'].is_set(): process.terminate()
    try:
        data,_=process.communicate(json.dumps({'text':text,'voice':voice}).encode(),timeout=240)
    except subprocess.TimeoutExpired:
        process.kill();process.communicate()
        raise RuntimeError('Local speech timed out; nothing was published. Retry a shorter contribution.') from None
    if job['cancelled'].is_set(): raise RuntimeError('Speech generation cancelled; nothing was published')
    if process.returncode: raise RuntimeError('Local speech failed; no audio was published. Check ./company voices.')
    validate_wave(data)
    return data


def prune_audio(now=None, *, _locked=False):
    current=time.time() if now is None else now
    with get_connection() as conn:
        init_audio(conn.cursor())
        expired=conn.execute('SELECT cache_key FROM conversation_audio WHERE expires_at<=?',(current,)).fetchall()
    if not expired: return 0
    fd=_directory();deleted=0;lock=None
    try:
        if not _locked:
            import fcntl
            lock=os.open('.writer-lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600,dir_fd=fd)
            info=os.fstat(lock)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=os.getuid() or info.st_mode & 0o077: raise ValueError('Unsafe audio writer lock')
            try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError: return 0
            # Recheck after acquiring ownership, not a stale pre-lock expiry snapshot.
            with get_connection() as conn:
                expired=conn.execute('SELECT cache_key FROM conversation_audio WHERE expires_at<=?',(current,)).fetchall()
        for row in expired:
            if not re.fullmatch('[a-f0-9]{64}',row[0]): continue
            name=row[0]+'.wav'
            try:
                info=os.stat(name,dir_fd=fd,follow_symlinks=False)
                if stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_uid==os.getuid():
                    os.unlink(name,dir_fd=fd);deleted+=1
            except FileNotFoundError: pass
    finally:
        if lock is not None: os.close(lock)
        os.close(fd)
    return deleted


def audio_bytes(key):
    if not re.fullmatch('[a-f0-9]{64}',key): raise ValueError('Invalid audio identifier')
    with get_connection() as conn:
        init_audio(conn.cursor())
        row=conn.execute('SELECT * FROM conversation_audio WHERE cache_key=? AND expires_at>?',(key,time.time())).fetchone()
    if not row: raise LookupError('Audio expired or unavailable; generate it again')
    fd=_directory()
    try:
        try: data=_read(fd,key+'.wav')
        except FileNotFoundError: raise LookupError('Audio unavailable; generate it again') from None
        except OSError: raise ValueError('Unsafe or inaccessible audio cache file') from None
    finally: os.close(fd)
    validate_wave(data)
    if hashlib.sha256(data).hexdigest()!=row['audio_digest']: raise ValueError('Audio integrity check failed')
    return data


def generate(kind, ident, request_id):
    if not re.fullmatch('[a-f0-9]{32}',request_id): raise ValueError('Invalid request identifier')
    days=config.CONVERSATION_AUDIO_RETENTION_DAYS
    if days not in {7,30}: raise RuntimeError('Conversation speech is disabled by audio retention configuration')
    if not _BUSY.acquire(blocking=False): raise RuntimeError('Local speech is busy; wait for the current request or stop it')
    job={'cancelled':threading.Event(),'process':None}
    with _JOBS_LOCK: _JOBS[request_id]=job
    fd=lock=None
    try:
        original,profile=source(kind,ident)
        text=spoken_text(original['body']);voice=profile['voice']['voice_name']
        source_digest=hashlib.sha256(original['body'].encode()).hexdigest()
        speech_digest=hashlib.sha256(text.encode()).hexdigest()
        key=hashlib.sha256(json.dumps([kind,ident,source_digest,speech_digest,profile['version'],voice,MODEL_DIGESTS,'speech-v1']).encode()).hexdigest()
        fd=_directory()
        import fcntl
        lock=os.open('.writer-lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600,dir_fd=fd)
        info=os.fstat(lock)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=os.getuid() or info.st_mode & 0o077:
            raise ValueError('Unsafe audio writer lock')
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise RuntimeError('Another local speech writer is busy; retry later') from None
        prune_audio(_locked=True)
        with get_connection() as conn:
            init_audio(conn.cursor())
            existing=conn.execute('SELECT * FROM conversation_audio WHERE cache_key=? AND expires_at>?',(key,time.time())).fetchone()
        if existing:
            try:
                audio_bytes(key)
                return dict(existing,cached=True)
            except LookupError: pass
        files=[os.stat(name,dir_fd=fd,follow_symlinks=False) for name in os.listdir(fd) if re.fullmatch('[a-f0-9]{64}\\.wav',name)]
        if len(files)>=MAX_FILES or sum(item.st_size for item in files)>MAX_CACHE_BYTES-MAX_BYTES:
            raise RuntimeError('Private audio cache is full; delete audio or wait for expiry before generating more')
        if job['cancelled'].is_set(): raise RuntimeError('Speech generation cancelled; nothing was published')
        data=synthesize(text,voice,job);duration=validate_wave(data)
        temporary=key+'.'+request_id+'.tmp'
        handle=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
        try:
            with os.fdopen(handle,'wb') as stream: stream.write(data);stream.flush();os.fsync(stream.fileno())
            # Cancellation and publication share a guard: stop cannot race a publish decision.
            with _JOBS_LOCK:
                if job['cancelled'].is_set(): raise RuntimeError('Speech generation cancelled; nothing was published')
                with get_connection() as conn:
                    conn.execute('BEGIN IMMEDIATE')
                    conn.execute('DELETE FROM conversation_audio WHERE cache_key=?',(key,))
                    now=time.time()
                    os.replace(temporary,key+'.wav',src_dir_fd=fd,dst_dir_fd=fd)
                    conn.execute('INSERT INTO conversation_audio VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(key,kind,ident,original['executive_key'],profile['version'],voice,source_digest,speech_digest,hashlib.sha256(data).hexdigest(),now,now+days*86400,duration))
                    conn.commit()
        finally:
            try: os.unlink(temporary,dir_fd=fd)
            except FileNotFoundError: pass
        return {'cache_key':key,'voice':voice,'profile_version':profile['version'],'duration':duration,'expires_at':now+days*86400,'cached':False}
    except OSError:
        raise RuntimeError('Local speech storage or runtime is unavailable; no successful audio result is recorded') from None
    finally:
        if lock is not None: os.close(lock)
        if fd is not None: os.close(fd)
        with _JOBS_LOCK: _JOBS.pop(request_id,None)
        _BUSY.release()


def delete_audio(key):
    if not re.fullmatch('[a-f0-9]{64}',key): raise ValueError('Invalid audio identifier')
    with get_connection() as conn:
        init_audio(conn.cursor())
        if not conn.execute('SELECT cache_key FROM conversation_audio WHERE cache_key=?',(key,)).fetchone(): raise LookupError('Audio not found')
    fd=_directory();lock=None
    try:
        import fcntl
        lock=os.open('.writer-lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600,dir_fd=fd)
        info=os.fstat(lock)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=os.getuid() or info.st_mode & 0o077: raise ValueError('Unsafe audio writer lock')
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise RuntimeError('Local audio writer is busy; stop generation or retry deletion later') from None
        try:
            _read(fd,key+'.wav')
            os.unlink(key+'.wav',dir_fd=fd)
        except FileNotFoundError: pass
    except OSError: raise ValueError('Unsafe or inaccessible audio cache') from None
    finally:
        if lock is not None: os.close(lock)
        os.close(fd)
    return {'deleted':True,'scope':'Audio bytes only; source text and history remain intact'}
