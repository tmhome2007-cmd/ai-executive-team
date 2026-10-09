"""Transactional activity history, without copying prompts, credentials or tool output.

Triggers capture changes through every database workflow, including recovery/import.
The fixed specification below is the only source of SQL identifiers/expressions.
"""
import contextvars
import json
import re
from contextlib import contextmanager

_origin = contextvars.ContextVar('activity_origin', default=('system', 'internal'))


@contextmanager
def activity_origin(actor, source):
    if actor not in {'owner', 'system', 'import', 'migration'}:
        raise ValueError('Invalid activity actor')
    if not isinstance(source, str) or not re.fullmatch(r'[A-Za-z0-9_/:. -]{1,180}', source):
        raise ValueError('Invalid activity source')
    token = _origin.set((actor, source))
    try:
        yield
    finally:
        _origin.reset(token)


def configure_connection(conn):
    conn.create_function('activity_actor', 0, lambda: _origin.get()[0])
    conn.create_function('activity_source', 0, lambda: _origin.get()[1])


# table, primary key, category, retained fields, other watched fields,
# decision/action/resource/goal link expressions, company visibility condition.
# No free-text contents are copied into the ledger. Edits record changed field names.
SPECS = (
    ('experiments', 'id', 'experiment', ('budget_amount', 'risk_limit', 'currency', 'version'), ('hypothesis', 'baseline_value', 'target_value', 'observation_due_at'), ('(SELECT source_decision_id FROM action_queue WHERE id = NEW.action_id)', 'NEW.action_id', 'NULL', 'NULL'), '1'),
    ('experiment_observations', 'id', 'experiment', ('value', 'observed_at', 'measurement_mode'), (), ('(SELECT q.source_decision_id FROM experiments e JOIN action_queue q ON q.id = e.action_id WHERE e.id = NEW.experiment_id)', '(SELECT action_id FROM experiments WHERE id = NEW.experiment_id)', 'NULL', 'NULL'), '1'),
    ('decisions', 'id', 'meeting', ('meeting_type',), (), ('NEW.id', 'NULL', 'NULL', 'NEW.goal_id'), '1'),
    ('decision_contributions', 'id', 'conversation', ('phase', 'sequence', 'executive_key'), (), ('NEW.decision_id', 'NULL', 'NULL', 'NULL'), '1'),
    ('decision_approvals', 'decision_id', 'approval', ('status', 'preparation_status'), ('preparation_outcome',), ('NEW.decision_id', 'NULL', 'NULL', 'NULL'), '1'),
    ('action_queue', 'id', 'action', ('status', 'action_type'), ('result_detail',), ('NEW.source_decision_id', 'NEW.id', 'NULL', 'NULL'), '1'),
    ('action_outcomes', 'action_id', 'result', ('outcome_status', 'actual_cost_amount', 'currency', 'measured_at'), ('actual_outcome', 'actual_impact', 'expected_outcome', 'expected_cost_amount', 'next_recommendation', 'notes'), ('(SELECT source_decision_id FROM action_queue WHERE id = NEW.action_id)', 'NEW.action_id', 'NULL', 'NULL'), '1'),
    ('resource_requests', 'id', 'resource', ('status',), ('fulfillment_note',), ('NEW.source_decision_id', 'NULL', 'NEW.id', 'NULL'), '1'),
    ('treasury_entries', 'id', 'treasury', ('entry_type', 'amount', 'currency'), (), ('NEW.source_decision_id', 'NEW.source_action_id', 'NULL', 'NULL'), '1'),
    ('treasury_reservations', 'id', 'treasury', ('status', 'amount', 'currency'), (), ('NEW.source_decision_id', 'NEW.source_action_id', 'NULL', 'NULL'), '1'),
    ('company_goals', 'id', 'goal', ('status', 'priority'), ('title', 'description', 'success_criteria', 'completion_note', 'target_date'), ('NULL', 'NULL', 'NULL', 'NEW.id'), '1'),
    ('followup_events', 'id', 'followup', ('status', 'attempt_count', 'generated_decision_id'), ('last_error',), ('NEW.source_decision_id', 'NEW.source_action_id', 'NULL', 'NEW.goal_id'), '1'),
    ('executive_memories', 'id', 'memory', ('is_active', 'confidence', 'memory_kind', 'executive_key'), ('lesson', 'supporting_evidence'), ('NEW.source_decision_id', 'NEW.source_action_id', 'NULL', 'NEW.source_goal_id'), '1'),
    ('agile_tasks', 'id', 'task', ('status', 'assignee', 'priority', 'version'), ('title', 'description', 'acceptance_criteria', 'blocked_reason', 'completion_note', 'goal_id', 'decision_id', 'action_id'), ('NEW.decision_id', 'NEW.action_id', 'NULL', 'NEW.goal_id'), "(SELECT kind = 'company' FROM agile_boards WHERE id = NEW.board_id)"),
)


def _state(prefix, fields):
    return 'json_object(' + ', '.join(f"'{field}', {prefix}.{field}" for field in fields) + ')'


def init_activity(conn):
    """One atomic migration; legacy snapshots identify gaps, never invent transitions."""
    conn.execute('BEGIN IMMEDIATE')
    conn.execute('''CREATE TABLE IF NOT EXISTS activity_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL, actor TEXT NOT NULL, source TEXT NOT NULL,
        category TEXT NOT NULL, entity_table TEXT NOT NULL, entity_id INTEGER NOT NULL,
        operation TEXT NOT NULL, previous_state TEXT, new_state TEXT,
        changed_fields TEXT NOT NULL, decision_id INTEGER, action_id INTEGER,
        resource_id INTEGER, goal_id INTEGER, company_visible INTEGER NOT NULL,
        legacy_snapshot INTEGER NOT NULL DEFAULT 0
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS activity_company_order ON activity_events(company_visible, id DESC)')
    conn.execute('CREATE TABLE IF NOT EXISTS activity_migrations (version INTEGER PRIMARY KEY, installed_at TEXT NOT NULL)')
    first = not conn.execute('SELECT 1 FROM activity_migrations WHERE version = 1').fetchone()
    for table, key, category, fields, watched, links, visible in SPECS:
        state = _state('NEW', fields)
        old = _state('OLD', fields)
        changes = fields + watched
        changed = 'json_object(' + ', '.join(f"'{f}', OLD.{f} IS NOT NEW.{f}" for f in changes) + ')'
        when = ' OR '.join(f'OLD.{f} IS NOT NEW.{f}' for f in changes)
        link_sql = ', '.join(links)
        if first:
            snapshot_state = state.replace('NEW.', 'record.')
            snapshot_links = link_sql.replace('NEW.', 'record.')
            snapshot_visible = visible.replace('NEW.', 'record.')
            conn.execute(f'''INSERT INTO activity_events(timestamp, actor, source, category, entity_table,
                entity_id, operation, previous_state, new_state, changed_fields, decision_id,
                action_id, resource_id, goal_id, company_visible, legacy_snapshot)
                SELECT strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), 'migration', 'activity-ledger-v1',
                '{category}', '{table}', record.{key}, 'snapshot', NULL, {snapshot_state}, '{{}}',
                {snapshot_links}, {snapshot_visible}, 1 FROM {table} AS record''')  # nosec B608 # Only fixed SPECS identifiers/expressions.
        for operation in ('insert', 'update'):
            previous = 'NULL' if operation == 'insert' else old
            changed_sql = "'{}'" if operation == 'insert' else changed
            condition = '' if operation == 'insert' else f'WHEN {when}'
            conn.execute(f'''CREATE TRIGGER IF NOT EXISTS activity_{table}_{operation}
                AFTER {operation.upper()} ON {table} {condition} BEGIN
                INSERT INTO activity_events(timestamp, actor, source, category, entity_table, entity_id,
                    operation, previous_state, new_state, changed_fields, decision_id, action_id,
                    resource_id, goal_id, company_visible)
                VALUES(strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), activity_actor(), activity_source(),
                    '{category}', '{table}', NEW.{key}, '{operation}', {previous}, {state},
                    {changed_sql}, {link_sql}, {visible}); END''')  # nosec B608 # Fixed SPECS; no runtime user values.
    conn.execute("INSERT OR IGNORE INTO activity_migrations VALUES (1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))")
    conn.execute("""CREATE TRIGGER IF NOT EXISTS activity_no_update BEFORE UPDATE ON activity_events
        BEGIN SELECT RAISE(ABORT, 'Activity events are append-only'); END""")
    conn.execute("""CREATE TRIGGER IF NOT EXISTS activity_no_delete BEFORE DELETE ON activity_events
        BEGIN SELECT RAISE(ABORT, 'Activity events are append-only'); END""")
    conn.commit()


def list_activity(limit=50, offset=0, before_id=None):
    from memory.database import get_connection
    if not 1 <= limit <= 100 or offset < 0 or (before_id is not None and before_id < 1):
        raise ValueError('Invalid activity pagination')
    with get_connection() as conn:
        rows = conn.execute('''SELECT * FROM activity_events WHERE company_visible = 1
            AND (? IS NULL OR id < ?) ORDER BY id DESC LIMIT ? OFFSET ?''',
            (before_id, before_id, limit, offset)).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item['previous_state'] = json.loads(item['previous_state']) if item['previous_state'] else None
        item['new_state'] = json.loads(item['new_state'])
        item['changed_fields'] = [f for f, changed in json.loads(item['changed_fields']).items() if changed]
        item['event_key'] = f"event:{item['id']}"
        label = 'Legacy snapshot' if item['legacy_snapshot'] else ('Recorded' if item['operation'] == 'insert' else 'Updated')
        item['title'] = f"{label}: {item['entity_table'].replace('_', ' ')} #{item['entity_id']}"
        item['detail'] = ('Current state at ledger installation; earlier transitions unknown.' if item['legacy_snapshot']
                          else 'Changed: ' + ', '.join(item['changed_fields']) if item['changed_fields'] else 'New record persisted.')
        items.append(item)
    return items
