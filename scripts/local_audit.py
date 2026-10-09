#!/usr/bin/env python3
"""Disposable local verification. Upstream findings remain visible, never ignored."""
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
KNOWN_CHROMA = {'PYSEC-2026-311', 'PYSEC-2026-3813', 'PYSEC-2026-3814', 'PYSEC-2026-3815'}


def main():
    branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip()
    if branch not in {'chatgpt/foundation-hardening', 'main', 'codex/operating-foundation-sprint', 'codex/identity-organization-simulation', 'codex/sprint-2-local-review'}:
        raise SystemExit('Stop: use the foundation-hardening or main development baseline for this disposable audit.')
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    report = ROOT / 'audit-results' / stamp
    report.mkdir(mode=0o700, parents=True, exist_ok=False)
    results = []
    with tempfile.TemporaryDirectory(prefix='ai-executive-audit-') as raw:
        temp = Path(raw).resolve()
        env = dict(os.environ)
        env.update({
            'DATABASE_PATH': str(temp / 'history.db'), 'WORKSPACE_ROOT': str(temp / 'workspace'),
            'CREWAI_STORAGE_DIR': str(temp / 'crewai'), 'SYNC_EXPORT_DIR': str(temp / 'sync'),
            'API_SECRET_KEY': 'disposable-local-audit-key-1234567890',
            'OPENAI_API_KEY': 'ollama-local-test', 'TELEGRAM_BOT_TOKEN': '', 'TELEGRAM_CHAT_ID': '',
            'BACKUP_ENCRYPTION_KEY': '', 'SYNC_HMAC_KEY': '', 'ACTION_APPROVAL_HMAC_KEY': '',
            'SANDBOX_MODE': 'true', 'ALLOW_UNSAFE_RAW_SHELL': 'false', 'ALLOW_REMOTE_LLM': 'false',
            'CREWAI_DISABLE_TELEMETRY': 'true', 'CREWAI_TRACING_ENABLED': 'false',
            'TELEGRAM_ALLOW_REMOTE_CONTROL': 'false', 'TELEGRAM_INCLUDE_SENSITIVE_DETAILS': 'false',
            'OLLAMA_BASE_URL': 'http://localhost:11434', 'OLLAMA_MODEL': 'llama3.1',
            'BIND_HOST': '127.0.0.1', 'ALLOW_INSECURE_REMOTE_HTTP': 'false',
            'ARTIFACT_RETENTION_DAYS': '30', 'RUN_DOCKER_INTEGRATION': '1',
            'NEXT_PUBLIC_API_BASE': 'http://127.0.0.1:8001',
        })

        def run(name, command, cwd=ROOT, timeout=900, defer_failure=False):
            path = report / (name + '.log')
            print(f'RUN   {name}', flush=True)
            try:
                with path.open('w') as log:
                    completed = subprocess.run(command, cwd=cwd, env=env, stdout=log,
                                               stderr=subprocess.STDOUT, timeout=timeout)
                ok = completed.returncode == 0
            except (OSError, subprocess.TimeoutExpired) as error:
                with path.open('a') as log:
                    log.write(f'\nRunner error: {error}\n')
                ok = False
            results.append({'check': name, 'status': 'PASS' if ok else 'FAIL', 'log': str(path)})
            display_status = "REVIEW" if not ok and defer_failure else results[-1]["status"]
            print(f'{display_status:5} {name}', flush=True)
            if not ok:
                print('\n'.join(path.read_text(errors='replace').splitlines()[-12:]), flush=True)
            return ok

        run('python-compatibility', [sys.executable, '-m', 'pip', 'check'])
        docker_ready = run('docker-ready', ['docker', 'info'], timeout=30)
        if docker_ready:
            run('docker-pinned-image', ['docker', 'pull', 'alpine@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc'], timeout=300)
        run('security-tests', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'])
        run('foundation-150', [sys.executable, 'verify_system.py'])
        run('bandit', [sys.executable, '-m', 'bandit', '-r', 'agents', 'memory', 'notifications',
                       'tools', 'workflows', 'main.py', 'config.py', 'system_checks.py', 'logging_config.py', 'foundation_api.py', '-ll'])
        audit_json = report / 'python-dependencies.json'
        audit_ok = run('python-dependencies', [sys.executable, '-m', 'pip_audit', '-f', 'json', '-o', str(audit_json)], defer_failure=True)
        if not audit_ok and audit_json.exists():
            try:
                data = json.loads(audit_json.read_text())
                findings = [(item['name'], issue) for item in data['dependencies'] for issue in item.get('vulns', [])]
                if findings and all(name == 'chromadb' and issue['id'] in KNOWN_CHROMA
                                    and not issue.get('fix_versions') for name, issue in findings):
                    results[-1]['status'] = 'UPSTREAM'
                    results[-1]['advisories'] = sorted({issue['id'] for _, issue in findings})
                    print('UPSTREAM: known unpatched Chroma findings remain; dependency scan is not clean.', flush=True)
            except (KeyError, ValueError, TypeError):
                pass

        # Build a clean copy so an open dashboard and its .next output are untouched.
        dashboard = temp / 'dashboard'
        shutil.copytree(ROOT / 'executive-dashboard', dashboard,
                        ignore=shutil.ignore_patterns('node_modules', '.next', '.git', '.env*'))
        installed = run('frontend-clean-install', ['npm', 'ci'], cwd=dashboard)
        if installed:
            run('frontend-review-summary', ['npm', 'run', 'test:review-summary'], cwd=dashboard)
            run('frontend-glob', ['npm', 'run', 'test:lint-glob'], cwd=dashboard)
            run('frontend-lint', ['npm', 'run', 'lint'], cwd=dashboard)
            built = run('frontend-build', ['npm', 'run', 'build', '--', '--webpack'], cwd=dashboard)
            if built:
                manifest = json.loads((dashboard / '.next' / 'routes-manifest.json').read_text())
                policies = [header['value'] for entry in manifest['headers'] for header in entry['headers']
                            if header['key'].lower() == 'content-security-policy']
                valid = any("connect-src 'self' http://127.0.0.1:8001" in policy for policy in policies)
                results.append({'check': 'frontend-api-policy', 'status': 'PASS' if valid else 'FAIL'})
                print(f'{results[-1]["status"]:5} frontend-api-policy', flush=True)
            run('frontend-dependencies', ['npm', 'audit'], cwd=dashboard)
        browser_smoke = (
            "from playwright.sync_api import sync_playwright\n"
            "with sync_playwright() as runtime:\n"
            "    browser = runtime.chromium.launch(headless=True)\n"
            "    page = browser.new_page()\n"
            "    page.set_content('<title>Synthetic audit</title><p>Local browser test</p>')\n"
            "    assert page.title() == 'Synthetic audit'\n"
            "    browser.close()\n"
            "print('Chromium runtime passed without visiting external pages')\n"
        )
        run('chromium-runtime', [sys.executable, '-c', browser_smoke], timeout=60)
        # Local model smoke test; the security suite uses a synthetic LLM for action gates.
        run('ollama-local-inference', ['ollama', 'run', 'llama3.1', 'Synthetic test only. Reply with one short greeting.'], timeout=180)

    summary = {'branch': branch, 'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
               'checks': results, 'scope': 'Automated local checks; not exhaustive security or production sign-off.'}
    (report / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    failed = [item['check'] for item in results if item['status'] == 'FAIL']
    print(f'\nReports: {report}')
    print('PROJECT CHECKS: ' + ('FAIL — ' + ', '.join(failed) if failed else 'PASS'))
    if any(item['status'] == 'UPSTREAM' for item in results):
        print('UPSTREAM: Chroma advisories still present; tracked separately from project check failures.')
    print('This does not certify every model answer or clear production deployment.')
    return bool(failed)


if __name__ == '__main__':
    sys.exit(main())
