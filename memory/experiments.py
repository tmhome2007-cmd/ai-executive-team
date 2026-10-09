"""Owner-defined experiments and source-backed observations; no autonomous spending."""
import datetime
import math
import re
from memory.database import get_connection, _reject_secret_like_text


def init_experiments(cursor):
    cursor.execute('''CREATE TABLE IF NOT EXISTS experiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, action_id INTEGER NOT NULL UNIQUE,
        title TEXT NOT NULL, hypothesis TEXT NOT NULL, baseline_note TEXT NOT NULL,
        baseline_value REAL, metric_name TEXT NOT NULL, unit TEXT NOT NULL,
        target_value REAL, direction TEXT NOT NULL, expected_result TEXT NOT NULL,
        budget_amount REAL NOT NULL, risk_limit REAL NOT NULL, currency TEXT NOT NULL,
        observation_due_at TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS experiment_observations (
        id INTEGER PRIMARY KEY AUTOINCREMENT, experiment_id INTEGER NOT NULL,
        idempotency_key TEXT NOT NULL, observed_at TEXT NOT NULL, value REAL,
        evidence TEXT NOT NULL, notes TEXT NOT NULL, recorded_at TEXT NOT NULL,
        measurement_mode TEXT NOT NULL,
        UNIQUE(experiment_id, idempotency_key)
    )''')
    cursor.execute('CREATE INDEX IF NOT EXISTS experiment_observation_order ON experiment_observations(experiment_id, observed_at DESC, id DESC)')
    cursor.execute("""CREATE TRIGGER IF NOT EXISTS observations_no_update BEFORE UPDATE ON experiment_observations
        BEGIN SELECT RAISE(ABORT, 'Observations are immutable; append a correction'); END""")
    cursor.execute("""CREATE TRIGGER IF NOT EXISTS observations_no_delete BEFORE DELETE ON experiment_observations
        BEGIN SELECT RAISE(ABORT, 'Observations are immutable'); END""")


def _text(value, name, maximum, required=True):
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ValueError(f'Invalid {name}')
    _reject_secret_like_text(value)
    return value.strip()


def _number(value, name, optional=False, positive=False):
    if optional and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > 1e15 or (positive and value < 0):
        raise ValueError(f'Invalid {name}')
    return float(value)


def _date(value, name):
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError(f'Invalid {name}')
    try:
        parsed = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError()
        return parsed.astimezone(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
    except (ValueError, OverflowError):
        raise ValueError(f'{name} requires an ISO timestamp with timezone') from None


PLAN_FIELDS = ('title', 'hypothesis', 'baseline_note', 'baseline_value', 'metric_name', 'unit',
               'target_value', 'direction', 'expected_result', 'budget_amount', 'risk_limit', 'currency', 'observation_due_at')


def _validate(plan):
    for name, maximum in [('title', 200), ('hypothesis', 4000), ('baseline_note', 4000), ('metric_name', 120), ('unit', 40), ('expected_result', 4000)]:
        plan[name] = _text(plan.get(name), name, maximum)
    for name in ['baseline_value', 'target_value']:
        plan[name] = _number(plan.get(name), name, optional=True)
    for name in ['budget_amount', 'risk_limit']:
        plan[name] = _number(plan.get(name), name, positive=True)
    if plan['risk_limit'] > plan['budget_amount']:
        raise ValueError('Risk limit must not exceed the experiment budget')
    if plan.get('direction') not in {'increase', 'decrease'}:
        raise ValueError('Invalid metric direction')
    currency = plan.get('currency')
    if not isinstance(currency, str) or not re.fullmatch(r'[A-Z]{3}', currency):
        raise ValueError('Currency must be three uppercase letters')
    plan['observation_due_at'] = _date(plan.get('observation_due_at'), 'observation_due_at')


def experiment_policy(cursor, action_id):
    row = cursor.execute('SELECT id, version, budget_amount, risk_limit, currency FROM experiments WHERE action_id = ?', (action_id,)).fetchone()
    return dict(row) if row else None


def check_experiment_budget(cursor, action):
    plan = experiment_policy(cursor, action['id'])
    if not plan:
        return
    for field in ('budget_amount', 'risk_limit'):
        _number(plan[field], field, positive=True)
    amount = action.get('expected_cost_amount')
    if amount is None or not math.isfinite(float(amount)) or float(amount) < 0 or action.get('currency') != plan['currency']:
        raise ValueError('Experiment actions require a known expected cost and matching currency before approval')
    if float(amount) > min(plan['budget_amount'], plan['risk_limit']) + 1e-9:
        raise ValueError('Expected action cost exceeds the experiment budget or risk limit')


def create_experiment(action_id, **fields):
    if isinstance(action_id, bool) or not isinstance(action_id, int) or action_id < 1:
        raise ValueError('Invalid action link')
    if set(fields) - set(PLAN_FIELDS):
        raise ValueError('Unknown experiment fields')
    plan = dict(fields)
    _validate(plan)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('BEGIN IMMEDIATE')
        action = cursor.execute('SELECT status FROM action_queue WHERE id = ?', (action_id,)).fetchone()
        if not action:
            raise LookupError('Action not found')
        if action['status'] != 'pending':
            raise ValueError('Define an experiment before approving its action')
        if cursor.execute('SELECT id FROM experiments WHERE action_id = ?', (action_id,)).fetchone():
            raise RuntimeError('This action already has an experiment')
        now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
        cursor.execute('''INSERT INTO experiments(action_id, title, hypothesis, baseline_note, baseline_value,
            metric_name, unit, target_value, direction, expected_result, budget_amount, risk_limit,
            currency, observation_due_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (action_id, *(plan[f] for f in PLAN_FIELDS), now, now))
        ident = cursor.lastrowid
        conn.commit()
    return get_experiment(ident)


def update_experiment(ident, expected_version, **fields):
    if not fields or set(fields) - set(PLAN_FIELDS):
        raise ValueError('Invalid experiment update')
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('BEGIN IMMEDIATE')
        plan = cursor.execute('SELECT * FROM experiments WHERE id = ?', (ident,)).fetchone()
        if not plan:
            raise LookupError('Experiment not found')
        plan = dict(plan)
        if plan['version'] != expected_version:
            raise RuntimeError('Experiment changed. Refresh before editing.')
        action = cursor.execute('SELECT status FROM action_queue WHERE id = ?', (plan['action_id'],)).fetchone()
        if not action or action['status'] != 'pending':
            raise ValueError('An approved experiment plan is frozen; propose a new action for a new plan')
        if cursor.execute('SELECT id FROM experiment_observations WHERE experiment_id = ? LIMIT 1', (ident,)).fetchone():
            raise ValueError('A measured experiment plan is frozen')
        plan.update(fields)
        _validate(plan)
        cursor.execute('''UPDATE experiments SET title = ?, hypothesis = ?, baseline_note = ?, baseline_value = ?,
            metric_name = ?, unit = ?, target_value = ?, direction = ?, expected_result = ?, budget_amount = ?,
            risk_limit = ?, currency = ?, observation_due_at = ?, updated_at = ?, version = version + 1
            WHERE id = ? AND version = ?''',
            (*(plan[f] for f in PLAN_FIELDS), datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z'), ident, expected_version))
        conn.commit()
    return get_experiment(ident)


def record_observation(ident, *, idempotency_key, observed_at, value=None, evidence, notes=''):
    if not isinstance(idempotency_key, str) or not re.fullmatch(r'[A-Za-z0-9:_-]{1,80}', idempotency_key):
        raise ValueError('Invalid observation idempotency key')
    _reject_secret_like_text(idempotency_key)
    observed_at = _date(observed_at, 'observed_at')
    if datetime.datetime.fromisoformat(observed_at.replace('Z', '+00:00')) > datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=60):
        raise ValueError('An observation cannot claim a future measurement')
    value = _number(value, 'value', optional=True)
    evidence = _text(evidence, 'evidence', 12000)
    notes = _text(notes, 'notes', 4000, required=False)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('BEGIN IMMEDIATE')
        plan = cursor.execute('SELECT * FROM experiments WHERE id = ?', (ident,)).fetchone()
        if not plan:
            raise LookupError('Experiment not found')
        existing = cursor.execute('SELECT * FROM experiment_observations WHERE experiment_id = ? AND idempotency_key = ?', (ident, idempotency_key)).fetchone()
        if existing:
            if any(existing[f] != v for f, v in [('observed_at', observed_at), ('value', value), ('evidence', evidence), ('notes', notes)]):
                raise RuntimeError('Observation retry differs from its original record')
            return dict(existing)
        action = cursor.execute('SELECT status, reviewed_at FROM action_queue WHERE id = ?', (plan['action_id'],)).fetchone()
        if action['status'] not in {'executed', 'executed_dry_run', 'execution_failed', 'blocked_dangerous'}:
            raise ValueError('Record outcome observations after terminal action execution; use the baseline for prior measurements')
        if action['reviewed_at']:
            executed_at = datetime.datetime.fromisoformat(action['reviewed_at']).astimezone(datetime.timezone.utc)
            if datetime.datetime.fromisoformat(observed_at.replace('Z', '+00:00')) < executed_at:
                raise ValueError('Outcome measurement predates the action execution record')
        mode = 'simulation' if action['status'] == 'executed_dry_run' else 'live'
        now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
        cursor.execute('''INSERT INTO experiment_observations(experiment_id, idempotency_key,
            observed_at, value, evidence, notes, recorded_at, measurement_mode) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (ident, idempotency_key, observed_at, value, evidence, notes, now, mode))
        row = dict(cursor.execute('SELECT * FROM experiment_observations WHERE id = ?', (cursor.lastrowid,)).fetchone())
        conn.commit()
        return row


def get_experiment(ident):
    with get_connection() as conn:
        row = conn.execute('''SELECT e.*, q.status AS action_status, q.source_decision_id,
            o.actual_cost_amount, o.currency AS cost_currency
            FROM experiments e JOIN action_queue q ON q.id = e.action_id
            LEFT JOIN action_outcomes o ON o.action_id = e.action_id WHERE e.id = ?''', (ident,)).fetchone()
        if not row:
            return None
        plan = dict(row)
        latest = conn.execute('SELECT * FROM experiment_observations WHERE experiment_id = ? ORDER BY observed_at DESC, id DESC LIMIT 1', (ident,)).fetchone()
        plan['latest_observation'] = dict(latest) if latest else None
        value = latest['value'] if latest else None
        target = plan['target_value']
        assessment = 'no_measurement' if value is None else 'target_unknown' if target is None else 'met_target' if (value >= target if plan['direction'] == 'increase' else value <= target) else 'missed_target'
        if latest and latest['measurement_mode'] == 'simulation':
            assessment = 'simulation_only'
        elif plan['action_status'] == 'blocked_dangerous':
            assessment = 'execution_blocked'
        elif plan['action_status'] not in {'executed', 'execution_failed', 'blocked_dangerous'}:
            assessment = 'simulation_only' if plan['action_status'] == 'executed_dry_run' else 'not_live_executed'
        cost = plan['actual_cost_amount']
        cost_assessment = 'not_recorded' if cost is None else 'currency_mismatch' if plan['cost_currency'] != plan['currency'] else 'over_limit' if cost > min(plan['budget_amount'], plan['risk_limit']) + 1e-9 else 'within_limit'
        plan['comparison'] = {'assessment': assessment, 'value': value,
            'change_from_baseline': value - plan['baseline_value'] if value is not None and plan['baseline_value'] is not None else None,
            'cost_assessment': cost_assessment, 'evidence_scope': 'Owner-recorded source; not independently verified'}
        return plan


def list_experiments(limit=50, offset=0):
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError('Invalid experiment pagination')
    with get_connection() as conn:
        ids = [r[0] for r in conn.execute('SELECT id FROM experiments ORDER BY id DESC LIMIT ? OFFSET ?', (limit, offset))]
    return [get_experiment(ident) for ident in ids]


def list_observations(ident, limit=50, offset=0):
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError('Invalid observation pagination')
    with get_connection() as conn:
        if not conn.execute('SELECT id FROM experiments WHERE id = ?', (ident,)).fetchone():
            raise LookupError('Experiment not found')
        return [dict(r) for r in conn.execute('SELECT * FROM experiment_observations WHERE experiment_id = ? ORDER BY observed_at DESC, id DESC LIMIT ? OFFSET ?', (ident, limit, offset))]
