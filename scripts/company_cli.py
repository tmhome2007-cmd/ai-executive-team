"""Local owner launcher. Never creates keys, resets data, switches branches or kills existing apps."""
import argparse
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / 'executive-dashboard'
SAFETY = {'SANDBOX_MODE':'true','ALLOW_UNSAFE_RAW_SHELL':'false','ALLOW_REMOTE_LLM':'false',
          'CREWAI_DISABLE_TELEMETRY':'true','CREWAI_TRACING_ENABLED':'false',
          'TELEGRAM_BOT_TOKEN':'','TELEGRAM_CHAT_ID':'','TELEGRAM_ALLOW_REMOTE_CONTROL':'false',
          'NEXT_TELEMETRY_DISABLED':'1','NEXT_PUBLIC_API_BASE':'http://127.0.0.1:8001','BIND_HOST':'127.0.0.1'}


def environment():
    try:
        from dotenv import dotenv_values
    except ImportError:
        raise RuntimeError('This checkout needs its .venv dependencies. See LOCAL_COMMANDS.md; no files were changed.') from None
    values={k:v for k,v in dotenv_values(ROOT/'.env').items() if v is not None}
    return {**values,**os.environ,**SAFETY,'VIRTUAL_ENV':str(ROOT/'.venv'),'PIPAPI_PYTHON_LOCATION':str(ROOT/'.venv/bin/python')}


def local_url(value):
    try:parsed=urllib.parse.urlsplit(value)
    except ValueError:raise RuntimeError('Ollama URL is invalid; no endpoint was contacted.') from None
    if parsed.scheme!='http' or parsed.hostname not in {'127.0.0.1','localhost','::1'} or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {'','/'}:
        raise RuntimeError('Ollama must use a plain local HTTP endpoint. No remote endpoint was contacted.')
    try:parsed.port
    except ValueError:raise RuntimeError('Ollama port is invalid.') from None
    return value.rstrip('/')


def available(port):
    with socket.socket() as probe:
        try:probe.bind(('127.0.0.1',port));return True
        except OSError:return False


def command_ok(command,env):
    try:return subprocess.run(command,cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15).returncode==0
    except (OSError,subprocess.TimeoutExpired):return False


def reachable(url):
    # Do not honor proxy variables for loopback probes and never follow redirects.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect()).open(url,timeout=3) as response:return response.status==200
    except (OSError,urllib.error.URLError):return False


def doctor(env):
    print(f'Checkout: {ROOT}')
    branch=subprocess.run(['git','branch','--show-current'],cwd=ROOT,capture_output=True,text=True,check=False)
    print('Branch: '+(branch.stdout.strip() or 'detached/unavailable'))
    checks=[('Checkout Python environment',(ROOT/'.venv/bin/python').is_file() and command_ok([str(ROOT/'.venv/bin/python'),'-c','import sys; raise SystemExit(0 if sys.version_info[:2] == (3,12) else 1)'],env),'Use this checkout’s Python 3.12 .venv; see LOCAL_COMMANDS.md.'),
            ('Existing API key',len(env.get('API_SECRET_KEY','').strip())>=32,'Set API_SECRET_KEY privately in this checkout’s .env. No key was generated.'),
            ('Node and npm',bool(shutil.which('node') and shutil.which('npm')),'Install Node/npm before starting the dashboard.'),
            ('Docker engine',command_ok(['docker','info'],env),'Open Docker Desktop and wait for the engine.'),
            ('Local Ollama',reachable(local_url(env.get('OLLAMA_BASE_URL','http://localhost:11434'))+'/api/tags'),'Open Ollama and wait for it to start.')]
    for label,ok,help_text in checks:
        print(('PASS ' if ok else 'NEEDS ATTENTION ')+label)
        if not ok:print('  '+help_text)
    for port,name in [(8001,'backend'),(3000,'dashboard')]:
        print(f'Port {port}: '+('free' if available(port) else f'in use; if this is your old {name}, stop it with Ctrl+C in its own terminal before ./company start'))
    print('Configuration: local sandbox; Telegram off; remote LLM off. Existing database and .env are preserved.')
    print('Next: ./company start runs both apps; ./company audit tests disposable data; ./company key copies the existing dashboard key.')
    return all(ok for _,ok,_ in checks)


def copy_key(env):
    key=env.get('API_SECRET_KEY','').strip()
    if len(key)<32:raise RuntimeError('Configured API key is missing/too short. Set it privately in .env; no new key was created.')
    if sys.platform!='darwin' or not shutil.which('pbcopy'):
        raise RuntimeError('Automatic clipboard copy is available on macOS. Use your configured key privately; it will not be printed.')
    subprocess.run(['pbcopy'],input=key,text=True,check=True)
    print('Existing API key copied. Paste it into the dashboard; no new key was created.')


def stop_children(children):
    for child in children:
        if child.poll() is None:
            try:os.killpg(child.pid,signal.SIGTERM)
            except ProcessLookupError:pass
    for child in children:
        try:child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            child.wait()


def start(env):
    if not doctor(env):raise RuntimeError('Fix the NEEDS ATTENTION items, then run ./company start again.')
    busy=[str(p) for p in (8001,3000) if not available(p)]
    if busy:raise RuntimeError('Ports already occupied: '+', '.join(busy)+'. Stop old apps in their own terminals. No process was killed.')
    if not (DASHBOARD/'node_modules').is_dir():
        print('Installing the exact dashboard dependencies with npm ci.',flush=True)
        subprocess.run(['npm','ci'],cwd=DASHBOARD,env=env,check=True)
    print('Building this branch’s dashboard; an old build will not be reused.',flush=True)
    subprocess.run(['npm','run','build','--','--webpack'],cwd=DASHBOARD,env=env,check=True)
    # Recheck after build; another process may have acquired either port.
    if not all(available(p) for p in (8001,3000)):raise RuntimeError('A port became occupied during build. No server was started.')
    children=[]
    try:
        backend=subprocess.Popen([str(ROOT/'.venv/bin/python'),'-m','uvicorn','main:app','--host','127.0.0.1','--port','8001'],cwd=ROOT,env=env,start_new_session=True);children.append(backend)
        deadline=time.monotonic()+60
        while not reachable('http://127.0.0.1:8001/'):
            if backend.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Backend did not become ready; review its messages above.')
            time.sleep(.25)
        frontend=subprocess.Popen(['npm','run','start','--','--hostname','127.0.0.1','--port','3000'],cwd=DASHBOARD,env=env,start_new_session=True);children.append(frontend)
        deadline=time.monotonic()+45
        while not reachable('http://127.0.0.1:3000/'):
            if frontend.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Dashboard did not become ready; review its messages above.')
            time.sleep(.25)
        if sys.platform=='darwin':copy_key(env)
        print('\nOpen http://127.0.0.1:3000 and paste the existing key. Keep this terminal open. Ctrl+C stops only these two apps.\nExisting approved local schedules still run under sandbox settings.',flush=True)
        while all(child.poll() is None for child in children):time.sleep(.5)
        raise RuntimeError('One app stopped; both launcher-owned apps have been stopped. Review its messages above.')
    finally:stop_children(children)


def main(argv=None):
    parser=argparse.ArgumentParser(description='One entry point for this checkout. Preserves keys/data; uses a local sandbox.')
    parser.add_argument('command',nargs='?',default='doctor',choices=['doctor','start','audit','key','voices','help'])
    args=parser.parse_args(argv)
    if args.command=='help':parser.print_help();return 0
    try:
        env=environment()
        if args.command=='doctor':return 0 if doctor(env) else 1
        if args.command=='key':copy_key(env);return 0
        if args.command=='start':start(env);return 0
        if args.command=='voices':
            return subprocess.run([sys.executable,str(ROOT/'scripts/prepare_voices.py')],cwd=ROOT,env=env).returncode
        if args.command=='audit':
            print('Audit uses disposable data and its own internal test key; your dashboard key/database remain unchanged.',flush=True)
            return subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'scripts/local_audit.py')],cwd=ROOT,env=env).returncode
    except KeyboardInterrupt:print('\nStopped. Existing files and unrelated apps were preserved.');return 0
    except (RuntimeError,OSError,subprocess.CalledProcessError):
        # Do not dump exception/command/env data, which could contain a credential.
        if sys.exc_info()[0] is RuntimeError:print(str(sys.exc_info()[1]),file=sys.stderr)
        else:print('A local command failed. Check the preceding status and retry; no key or data was reset.',file=sys.stderr)
        return 1


if __name__=='__main__':sys.exit(main())
