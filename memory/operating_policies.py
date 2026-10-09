"""Versioned owner policy, checked inside approval/execution transactions."""
import datetime
import json
import re
from memory.database import get_connection
from memory.experiments import _number, _text


def init_policies(cursor):
    cursor.execute('''CREATE TABLE IF NOT EXISTS operating_policies (
        version INTEGER PRIMARY KEY, currency TEXT NOT NULL,
        max_action_cost REAL, max_daily_cost REAL, max_experiment_risk REAL,
        require_known_cost INTEGER NOT NULL, prohibited_types TEXT NOT NULL,
        note TEXT NOT NULL, created_at TEXT NOT NULL)''')
    cursor.execute("INSERT OR IGNORE INTO operating_policies VALUES(1,'EUR',NULL,NULL,NULL,0,'[]','Existing approval gates remain mandatory',?)", (datetime.datetime.now(datetime.timezone.utc).isoformat(),))
    for operation in ('UPDATE', 'DELETE'):
        cursor.execute(f"CREATE TRIGGER IF NOT EXISTS policy_no_{operation.lower()} BEFORE {operation} ON operating_policies BEGIN SELECT RAISE(ABORT,'Policy history is immutable'); END")  # nosec B608 # Literal operations only.


def current_policy(cursor):
    item = dict(cursor.execute('SELECT * FROM operating_policies ORDER BY version DESC LIMIT 1').fetchone())
    item['prohibited_types'] = json.loads(item['prohibited_types'])
    item['require_known_cost'] = bool(item['require_known_cost'])
    item['approval_boundary'] = 'Owner approval required; policy never grants execution authority'
    return item


def get_policy():
    with get_connection() as conn:
        return current_policy(conn.cursor())


def save_policy(*, expected_version, currency, max_action_cost=None, max_daily_cost=None, max_experiment_risk=None, require_known_cost=False, prohibited_types=None, note):
    if not isinstance(currency, str) or not re.fullmatch(r'[A-Z]{3}', currency):
        raise ValueError('Currency must be three uppercase letters')
    values = [_number(v, name, optional=True, positive=True) for v, name in ((max_action_cost,'action limit'),(max_daily_cost,'daily limit'),(max_experiment_risk,'risk limit'))]
    if prohibited_types is None: prohibited_types = []
    if type(require_known_cost) is not bool or not isinstance(prohibited_types, list) or len(prohibited_types) > 3 or any(type(t) is not str or t not in {'shell','file_operation','browser_action'} for t in prohibited_types) or len(set(prohibited_types)) != len(prohibited_types):
        raise ValueError('Invalid policy flags or prohibited action types')
    note = _text(note, 'policy note', 2000)
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        previous = current_policy(conn.cursor())
        if type(expected_version) is not int or previous['version'] != expected_version:
            raise RuntimeError('Policy changed; refresh before saving')
        conn.execute('INSERT INTO operating_policies VALUES(?,?,?,?,?,?,?,?,?)', (expected_version+1,currency,*values,int(require_known_cost),json.dumps(sorted(prohibited_types)),note,datetime.datetime.now(datetime.timezone.utc).isoformat()))
        conn.commit()
    return get_policy()


def check_policy(cursor, action):
    policy = current_policy(cursor)
    if action['action_type'] in policy['prohibited_types']:
        raise ValueError('Action type prohibited by operating policy')
    cost = action.get('expected_cost_amount')
    if cost is None and (policy['require_known_cost'] or any(policy[f] is not None for f in ('max_action_cost','max_daily_cost'))):
        raise ValueError('Operating policy requires a known estimated cost, including zero')
    if cost is not None:
        cost = _number(cost, 'estimated action cost', positive=True)
        if cost > 0 and any(policy[f] is not None for f in ('max_action_cost','max_daily_cost','max_experiment_risk')) and action.get('currency') != policy['currency']:
            raise ValueError('Limited spending must use the policy currency; no implicit exchange conversion')
        if policy['max_action_cost'] is not None and cost > policy['max_action_cost']:
            raise ValueError('Action exceeds the operating cost limit')
        if policy['max_daily_cost'] is not None:
            # Count all active commitments, even older ones; never release exposure merely by waiting.
            reserved = cursor.execute("SELECT COALESCE(SUM(amount),0) FROM treasury_reservations WHERE status='active' AND currency=? AND source_action_id != ?", (policy['currency'], action['id'])).fetchone()[0]
            spent = cursor.execute("SELECT COALESCE(SUM(amount),0) FROM treasury_entries WHERE entry_type='spend' AND currency=? AND (CASE WHEN substr(timestamp,-1)='Z' OR substr(timestamp,-6,1) IN ('+','-') THEN julianday(timestamp) ELSE julianday(timestamp,'utc') END)>=julianday('now','-1 day')", (policy['currency'],)).fetchone()[0]
            if cost + float(reserved) + float(spent) > policy['max_daily_cost']:
                raise ValueError('Action exceeds daily spend plus active-commitment limit')
    experiment = cursor.execute('SELECT risk_limit,currency FROM experiments WHERE action_id=?', (action['id'],)).fetchone()
    if experiment and policy['max_experiment_risk'] is not None and (experiment['currency'] != policy['currency'] or experiment['risk_limit'] > policy['max_experiment_risk']):
        raise ValueError('Experiment exceeds operating risk policy')
    return policy['version']


def policy_context():
    policy=get_policy()
    fields=('version','currency','max_action_cost','max_daily_cost','max_experiment_risk','require_known_cost','prohibited_types')
    return 'Company operating limits (owner approval still required): '+json.dumps({key:policy[key] for key in fields},sort_keys=True)
