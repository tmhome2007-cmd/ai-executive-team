"""Zero-budget research/practice records. These never grant execution authority."""
import datetime
import json
from memory.database import get_connection
from memory.experiments import _text, _date

SCOPE = 'Research and local text practice only; €0 spend/loss; no launch authority or verified demand/profit.'


def init_business_discovery(cursor):
    cursor.execute('''CREATE TABLE IF NOT EXISTS business_discovery (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, constraints TEXT NOT NULL,
        source_ids_json TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'draft',
        research TEXT, selected_option TEXT, exercise TEXT, checks_json TEXT,
        observation_due_at TEXT, sample TEXT, sample_created_at TEXT, review_json TEXT,
        created_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1
    )''')

    columns = {row[1] for row in cursor.execute('PRAGMA table_info(business_discovery)')}
    if 'sample_created_at' not in columns:
        cursor.execute('ALTER TABLE business_discovery ADD COLUMN sample_created_at TEXT')


def get_brief(ident):
    with get_connection() as conn:
        row = conn.execute('SELECT * FROM business_discovery WHERE id = ?', (ident,)).fetchone()
    if not row:
        raise LookupError('Research brief not found')
    result = dict(row)
    for field in ('source_ids', 'checks', 'review'):
        result[field] = json.loads(result.pop(field + '_json') or 'null')
    result.update(scope=SCOPE, budget_amount=0, risk_limit=0, skill_assessment='not_demonstrated' if not result['review'] else 'owner_reviewed_practice_only')
    return result


def list_briefs(limit=50, offset=0):
    if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
        raise ValueError('Invalid pagination')
    with get_connection() as conn:
        ids = [r[0] for r in conn.execute('SELECT id FROM business_discovery ORDER BY id DESC LIMIT ? OFFSET ?', (limit, offset))]
    return [get_brief(i) for i in ids]


def create_brief(title, constraints, source_ids):
    from memory.evidence import source_context
    title = _text(title, 'title', 200)
    constraints = _text(constraints, 'constraints', 4000)
    source_context(source_ids)
    if len(source_ids) < 3:
        raise ValueError('Register at least three dated research sources first')
    with get_connection() as conn:
        cursor = conn.execute('''INSERT INTO business_discovery(title,constraints,source_ids_json,created_at)
            VALUES (?,?,?,?)''', (title, constraints, json.dumps(source_ids), datetime.datetime.now(datetime.timezone.utc).isoformat()))
        conn.commit()
    return get_brief(cursor.lastrowid)


def select_practice(ident, expected_version, selected_option, exercise, checks, observation_due_at):
    if type(expected_version) is not int or expected_version < 1:
        raise ValueError('Invalid version')
    selected_option = _text(selected_option, 'selected option', 1000)
    exercise = _text(exercise, 'practice exercise', 4000)
    if not isinstance(checks, list) or not 2 <= len(checks) <= 10:
        raise ValueError('Define two to ten observable practice checks')
    checks = [_text(c, 'practice check', 500) for c in checks]
    if len(set(checks)) != len(checks):
        raise ValueError('Practice checks must be distinct')
    observation_due_at = _date(observation_due_at, 'observation date')
    if datetime.datetime.fromisoformat(observation_due_at.replace('Z', '+00:00')) <= datetime.datetime.now(datetime.timezone.utc):
        raise ValueError('Choose a future observation date')
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        cursor = conn.execute('''UPDATE business_discovery SET selected_option=?,exercise=?,checks_json=?,
            observation_due_at=?,state='practice_ready',version=version+1
            WHERE id=? AND version=? AND state='research_ready' ''',
            (selected_option, exercise, json.dumps(checks), observation_due_at, ident, expected_version))
        if cursor.rowcount != 1:
            raise RuntimeError('Refresh; practice requires completed research and current version')
        conn.commit()
    return get_brief(ident)


def claim_stage(ident, expected_version, stage):
    if type(expected_version) is not int or expected_version < 1:
        raise ValueError('Invalid version')
    states = {'research': ('draft', 'research_running'), 'practice': ('practice_ready', 'practice_running')}
    if stage not in states:
        raise ValueError('Invalid discovery stage')
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        cursor = conn.execute('''UPDATE business_discovery SET state=?,version=version+1
            WHERE id=? AND version=? AND state=?''', (states[stage][1], ident, expected_version, states[stage][0]))
        if cursor.rowcount != 1:
            raise RuntimeError('Stage already started or brief changed; refresh')
        conn.commit()
    return get_brief(ident)


def finish_stage(ident, stage, output=None):
    if stage not in {'research', 'practice'}:
        raise ValueError('Invalid discovery stage')
    if output is not None:
        output = _text(output, 'AI output', 30000)
    # Fixed queries only; no model-controlled SQL identifiers.
    query = {'research': "UPDATE business_discovery SET research=?,state=?,version=version+1 WHERE id=? AND state='research_running'",
             'practice': "UPDATE business_discovery SET sample=?,state=?,sample_created_at=?,version=version+1 WHERE id=? AND state='practice_running'"}[stage]
    state = ('research_ready' if stage == 'research' else 'sample_ready') if output else 'needs_review'
    with get_connection() as conn:
        parameters = (output, state, ident) if stage == 'research' else (output, state, datetime.datetime.now(datetime.timezone.utc).isoformat() if output else None, ident)
        conn.execute(query, parameters)
        conn.commit()
    return get_brief(ident)


def reconcile_discovery():
    with get_connection() as conn:
        conn.execute("UPDATE business_discovery SET state='needs_review',version=version+1 WHERE state IN ('research_running','practice_running')")
        conn.commit()


def review_practice(ident, expected_version, results, evidence, observed_at):
    if type(expected_version) is not int or expected_version < 1:
        raise ValueError('Invalid version')
    brief = get_brief(ident)
    if not isinstance(results, list) or len(results) != len(brief['checks'] or []) or any(type(r) is not bool for r in results):
        raise ValueError('Record a pass/fail for every practice check')
    evidence = _text(evidence, 'review evidence', 12000)
    observed_at = _date(observed_at, 'observed at')
    observed = datetime.datetime.fromisoformat(observed_at.replace('Z', '+00:00'))
    if observed > datetime.datetime.now(datetime.timezone.utc) or observed < datetime.datetime.fromisoformat(brief['sample_created_at'] or brief['created_at']):
        raise ValueError('Review time must be after brief creation and not in the future')
    review = dict(results=results, evidence=evidence, observed_at=observed_at, assessment='practice_passed' if all(results) else 'practice_failed',
                  scope='Owner assessment of this sample only; not independent skill verification, demand evidence or launch approval')
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        cursor = conn.execute('''UPDATE business_discovery SET review_json=?,state='reviewed',version=version+1
            WHERE id=? AND version=? AND state='sample_ready' ''', (json.dumps(review), ident, expected_version))
        if cursor.rowcount != 1:
            raise RuntimeError('Refresh; review requires an unreviewed completed sample')
        conn.commit()
    return get_brief(ident)
