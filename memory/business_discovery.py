"""Zero-budget research/practice records. These never grant execution authority."""
import datetime
import json
from memory.database import get_connection
from memory.experiments import _text, _date
from memory.business_practice_history import init_history, history

def instruction_check(value):
    return value.strip().lower().rstrip(':').strip() in {'one per line', 'one check per line', 'checks one per line'}


def effective_assessment(checks, results):
    meaningful = [passed for check, passed in zip(checks, results) if not instruction_check(check)]
    return 'practice_passed' if len(meaningful) >= 2 and all(meaningful) else 'practice_failed'


SCOPE = 'Research and local text practice only; €0 spend/loss; no launch authority or verified demand/profit.'


def init_business_discovery(cursor):
    cursor.execute('''CREATE TABLE IF NOT EXISTS business_discovery (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, constraints TEXT NOT NULL,
        source_ids_json TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'draft',
        research TEXT, research_contract_version INTEGER NOT NULL DEFAULT 0, selected_option TEXT, exercise TEXT, checks_json TEXT,
        observation_due_at TEXT, sample TEXT, sample_created_at TEXT, review_json TEXT,
        created_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1
    )''')

    columns = {row[1] for row in cursor.execute('PRAGMA table_info(business_discovery)')}
    if 'research_contract_version' not in columns:
        cursor.execute('ALTER TABLE business_discovery ADD COLUMN research_contract_version INTEGER NOT NULL DEFAULT 0')
    if 'sample_created_at' not in columns:
        cursor.execute('ALTER TABLE business_discovery ADD COLUMN sample_created_at TEXT')
    init_history(cursor)


def get_brief(ident, include_history=True):
    with get_connection() as conn:
        conn.execute('BEGIN')
        row = conn.execute('SELECT * FROM business_discovery WHERE id = ?', (ident,)).fetchone()
        attempts = history(conn.cursor(), ident) if include_history else []
    if not row:
        raise LookupError('Research brief not found')
    result = dict(row)
    result['attempts'] = attempts
    for field in ('source_ids', 'checks', 'review'):
        result[field] = json.loads(result.pop(field + '_json') or 'null')
    from workflows.business_revision_contract import clean_deliverable
    result['sample_display'] = clean_deliverable(result['sample'], exercise=result['exercise'] or '') if result['sample'] else None
    if result['sample_display']:
        result['sample_display'] += '\n\nCurrent exercise scope: ' + (result['exercise'] or '') + '\nOwner assessment is recorded separately; this sample grants no launch authority.'
    result['ignored_check_indices'] = [i for i, check in enumerate(result['checks'] or []) if instruction_check(check)]
    result['review_assessment'] = effective_assessment(result['checks'], result['review']['results']) if result['review'] else None
    result.update(scope=SCOPE, budget_amount=0, risk_limit=0, skill_assessment='not_demonstrated' if not result['review'] else 'owner_reviewed_practice_only')
    return result


def list_briefs(limit=50, offset=0):
    if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
        raise ValueError('Invalid pagination')
    with get_connection() as conn:
        ids = [r[0] for r in conn.execute('SELECT id FROM business_discovery ORDER BY id DESC LIMIT ? OFFSET ?', (limit, offset))]
    return [get_brief(i, include_history=False) for i in ids]


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
    if any(instruction_check(check) for check in checks):
        raise ValueError('Remove the instruction “one per line:” from the checks; enter actual criteria only')
    if len(set(checks)) != len(checks):
        raise ValueError('Practice checks must be distinct')
    observation_due_at = _date(observation_due_at, 'observation date')
    if datetime.datetime.fromisoformat(observation_due_at.replace('Z', '+00:00')) <= datetime.datetime.now(datetime.timezone.utc):
        raise ValueError('Choose a future observation date')
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        cursor = conn.execute('''UPDATE business_discovery SET selected_option=?,exercise=?,checks_json=?,
            observation_due_at=?,state='practice_ready',version=version+1
            WHERE id=? AND version=? AND state='research_ready' AND research_contract_version=2 ''',
            (selected_option, exercise, json.dumps(checks), observation_due_at, ident, expected_version))
        if cursor.rowcount != 1:
            raise RuntimeError('Refresh; practice requires current validated research. Create a new attempt for older reports.')
        conn.commit()
    return get_brief(ident)


def claim_stage(ident, expected_version, stage):
    if type(expected_version) is not int or expected_version < 1:
        raise ValueError('Invalid version')
    states = {'research': ('draft', 'research_running'), 'practice': ('practice_ready', 'practice_running')}
    if stage == 'revision':
        return claim_revision(ident, expected_version)
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


def finish_stage(ident, stage, output=None, claimed_version=None):
    if stage == 'revision':
        return finish_revision(ident, output, claimed_version)
    if stage not in {'research', 'practice'}:
        raise ValueError('Invalid discovery stage')
    if output is not None:
        output = _text(output, 'AI output', 30000)
    # Fixed queries only; no model-controlled SQL identifiers.
    query = {'research': "UPDATE business_discovery SET research=?,state=?,research_contract_version=2,version=version+1 WHERE id=? AND state='research_running'",
             'practice': "UPDATE business_discovery SET sample=?,state=?,sample_created_at=?,version=version+1 WHERE id=? AND state='practice_running'"}[stage]
    state = ('research_ready' if stage == 'research' else 'sample_ready') if output else 'needs_review'
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        parameters = (output, state, ident) if stage == 'research' else (output, state, datetime.datetime.now(datetime.timezone.utc).isoformat() if output else None, ident)
        if claimed_version is not None:
            if type(claimed_version) is not int or claimed_version < 1:
                raise ValueError('Invalid claimed version')
            query += ' AND version=?'
            parameters += (claimed_version,)
        cursor = conn.execute(query, parameters)
        if stage == 'practice' and output and cursor.rowcount == 1:
            conn.execute('INSERT INTO business_practice_samples(brief_id,attempt,sample,created_at) VALUES (?,1,?,?)', (ident, output, parameters[2]))
        conn.commit()
    return get_brief(ident)


def reconcile_discovery():
    with get_connection() as conn:
        conn.execute("UPDATE business_discovery SET state='needs_review',version=version+1 WHERE state IN ('research_running','practice_running','revision_running')")
        conn.commit()


def review_practice(ident, expected_version, results, evidence, observed_at, correction=False):
    if type(expected_version) is not int or expected_version < 1:
        raise ValueError('Invalid version')
    if type(correction) is not bool:
        raise ValueError('Invalid correction mode')
    brief = get_brief(ident)
    if not isinstance(results, list) or len(results) != len(brief['checks'] or []) or any(type(r) is not bool for r in results):
        raise ValueError('Record a pass/fail for every practice check')
    evidence = _text(evidence, 'review evidence', 12000)
    observed_at = _date(observed_at, 'observed at')
    observed = datetime.datetime.fromisoformat(observed_at.replace('Z', '+00:00'))
    if observed > datetime.datetime.now(datetime.timezone.utc) or observed < datetime.datetime.fromisoformat(brief['sample_created_at'] or brief['created_at']):
        raise ValueError('Review time must be after brief creation and not in the future')
    review = dict(results=results, evidence=evidence, observed_at=observed_at, assessment=effective_assessment(brief['checks'], results), ignored_check_indices=brief['ignored_check_indices'],
                  scope='Owner assessment of this sample only; not independent skill verification, demand evidence or launch approval')
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        required_state = 'reviewed' if correction else 'sample_ready'
        cursor = conn.execute('''UPDATE business_discovery SET review_json=?,state='reviewed',version=version+1
            WHERE id=? AND version=? AND state=? ''', (json.dumps(review), ident, expected_version, required_state))
        if cursor.rowcount != 1:
            raise RuntimeError('Refresh; review requires an unreviewed completed sample')
        sample = conn.execute('SELECT id FROM business_practice_samples WHERE brief_id=? ORDER BY attempt DESC LIMIT 1', (ident,)).fetchone()
        if not sample:
            raise RuntimeError('Practice history missing; restart to import legacy records')
        reviews = conn.execute('SELECT id FROM business_practice_reviews WHERE sample_id=? ORDER BY id', (sample['id'],)).fetchall()
        if len(reviews) >= 20:
            raise ValueError('Assessment history limit reached for this sample')
        conn.execute('INSERT INTO business_practice_reviews(sample_id,review_json,supersedes_review_id) VALUES (?,?,?)',
                     (sample['id'], json.dumps(review), reviews[-1]['id'] if correction and reviews else None))
        conn.commit()
    return get_brief(ident)


def claim_revision(ident, expected_version):
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM business_discovery WHERE id=?', (ident,)).fetchone()
        if not row or row['version'] != expected_version or row['state'] not in {'reviewed', 'needs_review'} or not row['sample'] or not row['review_json']:
            raise RuntimeError('Revision requires a reviewed sample and current version; refresh')
        count = conn.execute('SELECT COUNT(*) FROM business_practice_samples WHERE brief_id=?', (ident,)).fetchone()[0]
        if not 1 <= count < 10:
            raise ValueError('Practice history supports at most ten samples per brief')
        conn.execute("UPDATE business_discovery SET state='revision_running',version=version+1 WHERE id=?", (ident,))
        conn.commit()
    return get_brief(ident)


def finish_revision(ident, output, claimed_version=None):
    if output is not None:
        output = _text(output, 'revision output', 30000)
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute("SELECT * FROM business_discovery WHERE id=? AND state='revision_running'", (ident,)).fetchone()
        if row and claimed_version is not None and row['version'] != claimed_version:
            row = None
        if row:
            if output:
                previous = conn.execute('SELECT * FROM business_practice_samples WHERE brief_id=? ORDER BY attempt DESC LIMIT 1', (ident,)).fetchone()
                review = conn.execute('SELECT id FROM business_practice_reviews WHERE sample_id=? ORDER BY id DESC LIMIT 1', (previous['id'],)).fetchone()
                now = datetime.datetime.now(datetime.timezone.utc).isoformat()
                conn.execute('''INSERT INTO business_practice_samples(brief_id,attempt,sample,created_at,parent_sample_id,feedback_review_id,changes)
                    VALUES (?,?,?,?,?,?,?)''', (ident, previous['attempt']+1, output, now, previous['id'], review['id'], 'See revision report; AI-described changes remain unverified'))
                conn.execute("UPDATE business_discovery SET sample=?,sample_created_at=?,review_json=NULL,state='sample_ready',version=version+1 WHERE id=?", (output, now, ident))
            else:
                conn.execute("UPDATE business_discovery SET state='needs_review',version=version+1 WHERE id=?", (ident,))
        conn.commit()
    return get_brief(ident)
