"""Published, source-linked discussion rounds; no hidden reasoning or consent fabrication."""
import datetime
import json
import re
from memory.database import get_connection
from memory.agile import OWNERS
from memory.experiments import _text
from memory.evidence import link_source


PHASES = ('proposal', 'critique', 'revision', 'synthesis')


def init_discussions(cursor):
    cursor.execute('''CREATE TABLE IF NOT EXISTS discussion_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, decision_id INTEGER NOT NULL,
        round_number INTEGER NOT NULL, phase TEXT NOT NULL, executive_key TEXT NOT NULL,
        body TEXT NOT NULL, profile_json TEXT NOT NULL, captured_at TEXT NOT NULL,
        UNIQUE(decision_id, round_number, executive_key)
    )''')
    columns = {r[1] for r in cursor.execute('PRAGMA table_info(discussion_messages)')}
    if 'quality_json' not in columns:
        cursor.execute('ALTER TABLE discussion_messages ADD COLUMN quality_json TEXT')
    for operation in ('UPDATE', 'DELETE'):
        cursor.execute(f"CREATE TRIGGER IF NOT EXISTS discussion_no_{operation.lower()} BEFORE {operation} ON discussion_messages BEGIN SELECT RAISE(ABORT, 'Published rounds are immutable'); END")  # nosec B608 # Two literal SQL operations only.


def consent_guard(body):
    from workflows.meeting import _guard_owner_acknowledgement
    body, _ = _guard_owner_acknowledgement(body)
    return re.sub(r'(?i)\b(?:the\s+)?(?:owner|human|user)\s+(?:has\s+)?(?:approved|authorized|authorised|agreed|acknowledged|consented)\b[^\n.!?]*[.!?]?',
                  'Pending owner review. This discussion records no owner approval.', body)


def store_discussion(cursor, decision_id, messages, source_ids=None):
    if messages is None:
        return
    if not isinstance(messages, list) or not 1 <= len(messages) <= 34:
        raise ValueError('Invalid discussion message set')
    original = {(r[0], r[1]) for r in cursor.execute('SELECT round_number, executive_key FROM discussion_messages WHERE decision_id = ?', (decision_id,))}
    expected = {(m.get('round_number'), m.get('executive_key')) for m in messages if isinstance(m, dict) and type(m.get('round_number')) is int and isinstance(m.get('executive_key'), str)}
    if original and original != expected:
        raise RuntimeError('Discussion replay differs from its published speaker set')
    seen = set()
    for message in messages:
        if not isinstance(message, dict) or set(message) - {'round_number', 'phase', 'executive_key', 'body', 'profile', 'quality_checks'} or not {'round_number', 'phase', 'executive_key', 'body', 'profile'} <= set(message):
            raise ValueError('Invalid discussion message fields')
        number, phase, role = message['round_number'], message['phase'], message['executive_key']
        if type(number) is not int or not 1 <= number <= 4 or phase != PHASES[number-1] or role not in OWNERS - {'owner'} or (number == 4 and role != 'ceo'):
            raise ValueError('Invalid discussion phase or speaker')
        if (number, role) in seen:
            raise ValueError('Duplicate discussion speaker in round')
        seen.add((number, role))
        body = consent_guard(_text(message['body'], 'published discussion body', 100000))
        profile = message['profile']
        if not isinstance(profile, dict) or set(profile) - {'name', 'role', 'goal', 'backstory'}:
            raise ValueError('Invalid profile snapshot')
        for value in profile.values():
            _text(value, 'profile value', 20000)
        serialized = json.dumps(profile, sort_keys=True)
        quality = message.get('quality_checks')
        if quality is not None and (not isinstance(quality, dict) or set(quality) != {'version', 'status', 'warnings', 'scope'} or type(quality['version']) is not int or quality['version'] != 1 or quality['status'] not in {'review_required', 'checks_passed'} or not isinstance(quality['warnings'], list) or len(quality['warnings']) > 30):
            raise ValueError('Invalid discussion quality checks')
        if quality is not None:
            if (quality['status'] == 'review_required') != bool(quality['warnings']):
                raise ValueError('Inconsistent discussion quality status')
            _text(quality['scope'], 'quality scope', 300)
            for warning in quality['warnings']:
                _text(warning, 'quality warning', 300)
        quality_json = json.dumps(quality, sort_keys=True) if quality is not None else None
        existing = cursor.execute('SELECT * FROM discussion_messages WHERE decision_id = ? AND round_number = ? AND executive_key = ?', (decision_id, number, role)).fetchone()
        if existing:
            if existing['body'] != body or existing['profile_json'] != serialized or existing['phase'] != phase or existing['quality_json'] != quality_json:
                raise RuntimeError('Discussion replay differs from its published record')
            continue
        cursor.execute('''INSERT INTO discussion_messages(decision_id,round_number,phase,executive_key,body,profile_json,captured_at,quality_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (decision_id, number, phase, role, body, serialized, datetime.datetime.now(datetime.timezone.utc).isoformat(), quality_json))
        message_id = cursor.lastrowid
        sources = source_ids or [r[0] for r in cursor.execute("SELECT source_id FROM evidence_links WHERE entity_kind = 'decision' AND entity_id = ?", (decision_id,))]
        for source_id in sources:
            link_source(cursor, source_id, 'discussion', message_id, 'context')


def get_discussion(decision_id):
    with get_connection() as conn:
        if not conn.execute('SELECT id FROM decisions WHERE id = ?', (decision_id,)).fetchone():
            raise LookupError('Decision not found')
        rows = conn.execute('SELECT * FROM discussion_messages WHERE decision_id = ? ORDER BY round_number, id LIMIT 34', (decision_id,)).fetchall()
    return [{**dict(row), 'profile': json.loads(row['profile_json']), 'quality_checks': json.loads(row['quality_json']) if row['quality_json'] else {'status': 'not_assessed', 'warnings': [], 'scope': 'Legacy published output; no stored quality assessment'}} for row in rows]
