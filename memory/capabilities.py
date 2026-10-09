"""Resource-backed, scoped access inventory. Records never expand executive tool roles."""
import datetime
import hashlib
import hmac
import json
import os
import re
from config import config
from memory.database import get_connection
from memory.agile import OWNERS
from memory.experiments import _text
from workflows.capability_policy import normalize_executive_role


SCOPES = {'github': {'repo.read', 'repo.write'}, 'browser': {'page.read', 'page.interact'}}


def init_capabilities(cursor):
    cursor.execute('''CREATE TABLE IF NOT EXISTS capability_inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT, resource_request_id INTEGER NOT NULL UNIQUE,
        provider TEXT NOT NULL, scopes_json TEXT NOT NULL, roles_json TEXT NOT NULL,
        target TEXT NOT NULL, secret_ref TEXT, status TEXT NOT NULL DEFAULT 'provided',
        health TEXT NOT NULL DEFAULT 'unknown', last_health_at TEXT, verified_until TEXT,
        credential_fingerprint TEXT, version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS action_capability_requirements (
        id INTEGER PRIMARY KEY AUTOINCREMENT, action_id INTEGER NOT NULL, grant_id INTEGER NOT NULL,
        required_scope TEXT NOT NULL, UNIQUE(action_id, grant_id, required_scope)
    )''')

    cursor.execute("""CREATE TRIGGER IF NOT EXISTS capability_no_delete BEFORE DELETE ON capability_inventory
        BEGIN SELECT RAISE(ABORT, 'Capability history is retained'); END""")
    cursor.execute("""CREATE TRIGGER IF NOT EXISTS capability_no_rewrite BEFORE UPDATE ON capability_inventory
        WHEN OLD.resource_request_id IS NOT NEW.resource_request_id OR OLD.provider IS NOT NEW.provider
        OR OLD.scopes_json IS NOT NEW.scopes_json OR OLD.roles_json IS NOT NEW.roles_json
        OR OLD.target IS NOT NEW.target OR OLD.secret_ref IS NOT NEW.secret_ref
        BEGIN SELECT RAISE(ABORT, 'Provided scopes are immutable; request new access'); END""")
    cursor.execute("""CREATE TRIGGER IF NOT EXISTS requirement_no_delete BEFORE DELETE ON action_capability_requirements
        BEGIN SELECT RAISE(ABORT, 'Capability requirements are retained'); END""")
    cursor.execute("""CREATE TRIGGER IF NOT EXISTS requirement_no_update BEFORE UPDATE ON action_capability_requirements
        BEGIN SELECT RAISE(ABORT, 'Capability requirements are immutable'); END""")


def credential_fingerprint(secret_ref, *, captured_secret=None):
    if not secret_ref:
        return None
    secret = os.environ.get(secret_ref, '') if captured_secret is None else captured_secret
    if not secret or not config.API_SECRET_KEY:
        return None
    return hmac.new(config.API_SECRET_KEY.encode(), secret.encode(), hashlib.sha256).hexdigest()


def provide_capability(*, resource_request_id, provider, scopes, roles, target, secret_ref=None):
    if provider not in {'github', 'browser', 'manual'}:
        raise ValueError('Unsupported provider adapter; use manual inventory for unimplemented connectors')
    if not isinstance(scopes, list) or not 1 <= len(scopes) <= 10 or any(not isinstance(s, str) or not re.fullmatch(r'[a-z][a-z0-9_.]{1,60}', s) for s in scopes) or len(set(scopes)) != len(scopes):
        raise ValueError('Invalid requested scopes')
    if provider in SCOPES and set(scopes) - SCOPES[provider]:
        raise ValueError('Unsupported provider scope')
    if not isinstance(roles, list) or not roles or len(roles) > 11 or any(role not in OWNERS - {'owner'} for role in roles) or len(set(roles)) != len(roles):
        raise ValueError('Invalid capability role scope')
    target = _text(target, 'capability target', 200)
    if provider == 'github' and (target.split('/')[-1] in {'.', '..'} or not re.fullmatch(r'[A-Za-z0-9-]{1,39}/[A-Za-z0-9_.-]{1,100}', target)):
        raise ValueError('GitHub target must be owner/repository')
    if provider == 'browser' and not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]{0,198}[a-z0-9])?', target):
        raise ValueError('Browser target must be an exact lowercase host, without URL/wildcards')
    if (provider == 'github' and secret_ref != 'GITHUB_TOKEN') or (provider != 'github' and secret_ref is not None):
        raise ValueError('Only the configured GITHUB_TOKEN environment reference is supported; never supply its value')
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('BEGIN IMMEDIATE')
        request = cursor.execute('''SELECT r.*, g.status AS goal_status FROM resource_requests r
            LEFT JOIN decisions d ON d.id = r.source_decision_id LEFT JOIN company_goals g ON g.id = d.goal_id WHERE r.id = ?''', (resource_request_id,)).fetchone()
        if not request or request['status'] not in {'approved', 'fulfilled'} or request['resource_type'] not in {'access', 'credential', 'plugin', 'service', 'data'} or (request['goal_status'] is not None and request['goal_status'] != 'active'):
            raise ValueError('Provide access only against an approved access resource and active linked goal')
        existing = cursor.execute('SELECT * FROM capability_inventory WHERE resource_request_id = ?', (resource_request_id,)).fetchone()
        values = (provider, json.dumps(sorted(scopes)), json.dumps(sorted(roles)), target, secret_ref)
        if existing:
            if tuple(existing[k] for k in ['provider','scopes_json','roles_json','target','secret_ref']) != values or existing['status'] == 'revoked':
                raise RuntimeError('Provided scope differs or is revoked; create a new resource request')
            return _public(existing)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cursor.execute('''INSERT INTO capability_inventory(resource_request_id,provider,scopes_json,roles_json,target,secret_ref,created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)''', (resource_request_id, *values, now))
        ident = cursor.lastrowid
        if request['status'] == 'approved':
            cursor.execute("UPDATE resource_requests SET status = 'fulfilled', fulfilled_at = ?, fulfillment_note = 'Scoped access provided; independent health verification pending' WHERE id = ? AND status = 'approved'", (datetime.datetime.now().isoformat(), resource_request_id))
        conn.commit()
        return _public(cursor.execute('SELECT * FROM capability_inventory WHERE id = ?', (ident,)).fetchone())


def _public(row):
    item = dict(row)
    item.pop('credential_fingerprint', None)
    item['scopes'] = json.loads(item.pop('scopes_json'))
    item['roles'] = json.loads(item.pop('roles_json'))
    item['fresh'] = bool(item['verified_until'] and datetime.datetime.fromisoformat(item['verified_until']) > datetime.datetime.now(datetime.timezone.utc))
    return item


def list_capabilities(limit=50, offset=0):
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError('Invalid inventory pagination')
    with get_connection() as conn:
        return [_public(r) for r in conn.execute('SELECT * FROM capability_inventory ORDER BY id DESC LIMIT ? OFFSET ?', (limit, offset))]


def revoke_capability(ident, expected_version):
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM capability_inventory WHERE id = ?', (ident,)).fetchone()
        if not row:
            raise LookupError('Capability not found')
        if row['version'] != expected_version or row['status'] == 'revoked':
            raise RuntimeError('Capability changed or already revoked')
        conn.execute("UPDATE capability_inventory SET status = 'revoked', health = 'revoked', verified_until = NULL, version = version + 1 WHERE id = ?", (ident,))
        conn.commit()
    return {'id': ident, 'status': 'revoked'}


def bind_capabilities(action_id, requirements):
    if not isinstance(requirements, list) or not 1 <= len(requirements) <= 10:
        raise ValueError('Invalid capability requirements')
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('BEGIN IMMEDIATE')
        action = cursor.execute('SELECT status FROM action_queue WHERE id = ?', (action_id,)).fetchone()
        if not action or action['status'] != 'pending':
            raise ValueError('Bind capability requirements before approving an action')
        for requirement in requirements:
            if not isinstance(requirement, dict) or set(requirement) != {'grant_id', 'scope'}:
                raise ValueError('Invalid requirement fields')
            if type(requirement['grant_id']) is not int or requirement['grant_id'] < 1 or not isinstance(requirement['scope'], str):
                raise ValueError('Invalid requirement identifier or scope')
            row = cursor.execute('SELECT * FROM capability_inventory WHERE id = ?', (requirement['grant_id'],)).fetchone()
            if not row or row['status'] == 'revoked' or requirement['scope'] not in json.loads(row['scopes_json']):
                raise ValueError('Capability scope is not provided')
            cursor.execute('INSERT OR IGNORE INTO action_capability_requirements(action_id,grant_id,required_scope) VALUES (?, ?, ?)', (action_id, requirement['grant_id'], requirement['scope']))
        conn.commit()
    return {'action_id': action_id, 'requirements': inventory_policy(cursor=None, action_id=action_id)}


def inventory_policy(cursor, action_id):
    if cursor is None:
        with get_connection() as conn:
            return inventory_policy(conn.cursor(), action_id)
    rows = [dict(r) for r in cursor.execute("""SELECT r.grant_id, r.required_scope, c.version, c.status,
        c.provider, c.scopes_json, c.roles_json, c.target, c.credential_fingerprint
        FROM action_capability_requirements r JOIN capability_inventory c ON c.id = r.grant_id
        WHERE r.action_id = ? ORDER BY r.grant_id, r.required_scope""", (action_id,))]
    # Scoped browser resources in the action's preparation lineage are mandatory,
    # even if an agent/owner did not explicitly bind them on the action form.
    action = cursor.execute('SELECT action_type, action_detail, source_decision_id FROM action_queue WHERE id = ?', (action_id,)).fetchone()
    if action and action['action_type'] == 'browser_action' and action['source_decision_id'] is not None:
        try:
            scope = 'page.interact' if json.loads(action['action_detail']).get('click_selector') else 'page.read'
        except (ValueError, TypeError, AttributeError):
            raise ValueError('Invalid scoped browser action payload') from None
        implicit = cursor.execute("""SELECT c.id AS grant_id, c.version, c.status, c.provider, c.scopes_json,
            c.roles_json, c.target, c.credential_fingerprint FROM capability_inventory c
            JOIN resource_requests r ON r.id = c.resource_request_id
            WHERE r.source_decision_id = ? AND c.provider = 'browser'""", (action['source_decision_id'],)).fetchall()
        for grant in implicit:
            item = {**dict(grant), 'required_scope': scope}
            if not any(r['grant_id'] == item['grant_id'] and r['required_scope'] == scope for r in rows):
                rows.append(item)
    return sorted(rows, key=lambda r: (r['grant_id'], r['required_scope']))


def check_inventory_requirements(cursor, action):
    role = normalize_executive_role(action['proposed_by'])
    for requirement in inventory_policy(cursor, action['id']):
        row = dict(cursor.execute('SELECT * FROM capability_inventory WHERE id = ?', (requirement['grant_id'],)).fetchone())
        row['required_scope'] = requirement['required_scope']
        if row['status'] != 'verified' or row['health'] != 'healthy' or not row['verified_until'] or datetime.datetime.fromisoformat(row['verified_until']) <= datetime.datetime.now(datetime.timezone.utc):
            raise ValueError('Required capability is revoked, stale or unverified')
        if role not in json.loads(row['roles_json']) or row['required_scope'] not in json.loads(row['scopes_json']):
            raise ValueError('Action executive or scope is not authorized by its capability')
        if row['secret_ref'] and credential_fingerprint(row['secret_ref']) != row['credential_fingerprint']:
            raise ValueError('Credential changed; verify access and review approval again')
        request = cursor.execute('''SELECT r.status, g.status AS goal_status FROM resource_requests r
            LEFT JOIN decisions d ON d.id = r.source_decision_id LEFT JOIN company_goals g ON g.id = d.goal_id WHERE r.id = ?''', (row['resource_request_id'],)).fetchone()
        if not request or request['status'] != 'fulfilled' or (request['goal_status'] is not None and request['goal_status'] != 'active'):
            raise ValueError('Capability resource or goal is no longer active')
        if row['provider'] == 'browser':
            from urllib.parse import urlsplit
            if action['action_type'] != 'browser_action':
                raise ValueError('Browser capability can only gate a browser action')
            try:
                payload = json.loads(action['action_detail'])
                host = urlsplit(payload['url']).hostname
            except (ValueError, KeyError, TypeError):
                raise ValueError('Browser action lacks a scoped target') from None
            allowed = {h.strip().lower() for h in config.ALLOWED_BROWSER_DOMAINS.split(',') if h.strip()}
            if row['required_scope'] == 'page.read' and payload.get('click_selector'):
                raise ValueError('Browser interaction requires page.interact scope')
            if host != row['target'] or host not in allowed:
                raise ValueError('Browser action target exceeds provided scope')
