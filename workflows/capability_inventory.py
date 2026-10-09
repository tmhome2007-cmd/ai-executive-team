"""Bounded provider checks. No arbitrary URLs, credential values in storage, or redirects."""
import datetime
import json
import os
import requests
from config import config
from memory.database import get_connection
from memory.capabilities import credential_fingerprint, _public


def verify_capability(ident):
    with get_connection() as conn:
        row = conn.execute('SELECT * FROM capability_inventory WHERE id = ?', (ident,)).fetchone()
    if not row:
        raise LookupError('Capability not found')
    row = dict(row)
    if row['status'] == 'revoked':
        raise ValueError('Revoked capability cannot be re-enabled; request new access')
    healthy = False
    fingerprint = None
    if row['provider'] == 'github':
        secret = os.environ.get('GITHUB_TOKEN', '')
        if secret:
            fingerprint = credential_fingerprint('GITHUB_TOKEN', captured_secret=secret)
            try:
                response = requests.get('https://api.github.com/repos/' + row['target'],
                    headers={'Authorization': 'Bearer ' + secret, 'Accept': 'application/vnd.github+json'},
                    timeout=5, allow_redirects=False)
                if response.status_code == 200:
                    permissions = response.json().get('permissions', {})
                    healthy = bool(permissions.get('pull') and ('repo.write' not in json.loads(row['scopes_json']) or permissions.get('push')))
                if not fingerprint or fingerprint != credential_fingerprint('GITHUB_TOKEN'):
                    healthy = False
            except Exception:
                healthy = False  # Never persist provider error bodies or token-bearing exceptions.
    elif row['provider'] == 'browser':
        allowed = {host.strip().lower() for host in config.ALLOWED_BROWSER_DOMAINS.split(',') if host.strip()}
        if row['target'] in allowed:
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as runtime:
                    browser = runtime.chromium.launch(headless=True)
                    browser.close()
                healthy = True
            except Exception:
                healthy = False
    # Manual inventory intentionally cannot claim provider-verified health.
    now = datetime.datetime.now(datetime.timezone.utc)
    status = 'verified' if healthy else 'provided'
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        current = conn.execute('SELECT * FROM capability_inventory WHERE id = ?', (ident,)).fetchone()
        if current['version'] != row['version'] or current['status'] == 'revoked':
            raise RuntimeError('Capability changed during verification; retry against current scope')
        if row['secret_ref'] and fingerprint != credential_fingerprint(row['secret_ref']):
            healthy, status = False, 'provided'
        changed = current['status'] != status or current['credential_fingerprint'] != fingerprint
        conn.execute('''UPDATE capability_inventory SET status = ?, health = ?, last_health_at = ?, verified_until = ?,
            credential_fingerprint = ?, version = version + ? WHERE id = ?''',
            (status, 'healthy' if healthy else 'unverified', now.isoformat(), (now + datetime.timedelta(minutes=30)).isoformat() if healthy else None, fingerprint, int(changed), ident))
        conn.commit()
        return _public(conn.execute('SELECT * FROM capability_inventory WHERE id = ?', (ident,)).fetchone())


async def refresh_verified_capabilities():
    import asyncio
    cursor_id = 0
    checked = 0
    while True:
        with get_connection() as conn:
            ids = [r[0] for r in conn.execute("SELECT id FROM capability_inventory WHERE status = 'verified' AND id > ? ORDER BY id LIMIT 100", (cursor_id,))]
        if not ids:
            break
        for ident in ids:
            cursor_id = ident
            try:
                await asyncio.to_thread(verify_capability, ident)
            except (ValueError, RuntimeError):
                pass
            checked += 1
    return checked
