"""Owner-controlled task planning. Assignments never change execution authority."""
import datetime
from memory.database import get_connection, _reject_secret_like_text

STATUSES = {'backlog', 'ready', 'in_progress', 'review', 'done', 'blocked'}
PRIORITIES = {'critical', 'high', 'medium', 'low'}
OWNERS = {'owner', 'ceo', 'cfo', 'coo', 'cso', 'cmo', 'cto', 'chro', 'general_counsel', 'cpo', 'cco', 'board_director'}


def init_agile(cursor):
    cursor.execute("""CREATE TABLE IF NOT EXISTS agile_boards (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN ('development', 'company')),
        created_at TEXT NOT NULL
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS agile_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, board_id INTEGER NOT NULL REFERENCES agile_boards(id),
        title TEXT NOT NULL, description TEXT NOT NULL, acceptance_criteria TEXT NOT NULL,
        assignee TEXT NOT NULL DEFAULT 'owner', priority TEXT NOT NULL DEFAULT 'medium',
        status TEXT NOT NULL DEFAULT 'backlog', blocked_reason TEXT NOT NULL DEFAULT '',
        completion_note TEXT NOT NULL DEFAULT '', goal_id INTEGER, decision_id INTEGER, action_id INTEGER,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1
    )""")
    cursor.execute('CREATE INDEX IF NOT EXISTS agile_tasks_board ON agile_tasks(board_id, id)')


def _text(value, name, maximum, required=False):
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ValueError(f'Invalid {name}')
    _reject_secret_like_text(value)
    return value.strip()


def create_board(name, kind):
    name = _text(name, 'board name', 120, True)
    if kind not in {'development', 'company'}:
        raise ValueError('Invalid board kind')
    with get_connection() as conn:
        cursor = conn.execute('INSERT INTO agile_boards(name, kind, created_at) VALUES (?, ?, ?)',
                              (name, kind, datetime.datetime.now().isoformat()))
        ident = cursor.lastrowid
        conn.commit()
        return ident


def list_boards(limit=100, offset=0):
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError('Invalid pagination')
    with get_connection() as conn:
        return [dict(r) for r in conn.execute('SELECT * FROM agile_boards ORDER BY id DESC LIMIT ? OFFSET ?', (limit, offset))]


def list_tasks(board_id, limit=100, offset=0):
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError('Invalid pagination')
    with get_connection() as conn:
        if not conn.execute('SELECT id FROM agile_boards WHERE id = ?', (board_id,)).fetchone():
            raise LookupError('Board not found')
        return [dict(r) for r in conn.execute("SELECT * FROM agile_tasks WHERE board_id = ? ORDER BY CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, id ASC LIMIT ? OFFSET ?", (board_id, limit, offset))]


def _validate_task(cursor, board, task):
    for field, maximum, required in [('title', 200, True), ('description', 10000, False), ('acceptance_criteria', 10000, False), ('blocked_reason', 2000, False), ('completion_note', 10000, False)]:
        task[field] = _text(task[field], field, maximum, required)
    if task['status'] not in STATUSES or task['priority'] not in PRIORITIES or task['assignee'] not in OWNERS:
        raise ValueError('Invalid status, priority or assignee')
    if task['status'] == 'blocked' and not task['blocked_reason']:
        raise ValueError('A blocked task needs a reason')
    if task['status'] == 'done' and not task['completion_note']:
        raise ValueError('A done task needs a completion note')
    if task['status'] in {'ready', 'in_progress', 'review', 'done'} and not task['acceptance_criteria']:
        raise ValueError('Define acceptance criteria before starting work')
    links = [task['goal_id'], task['decision_id'], task['action_id']]
    if board['kind'] == 'development' and any(link is not None for link in links):
        raise ValueError('Business record links belong on the company board')
    if any(value is not None and (not isinstance(value, int) or value < 1) for value in links):
        raise ValueError('Invalid company record link')
    goal = cursor.execute('SELECT id FROM company_goals WHERE id = ?', (task['goal_id'],)).fetchone() if task['goal_id'] else None
    decision = cursor.execute('SELECT id, goal_id FROM decisions WHERE id = ?', (task['decision_id'],)).fetchone() if task['decision_id'] else None
    action = cursor.execute('SELECT id, source_decision_id FROM action_queue WHERE id = ?', (task['action_id'],)).fetchone() if task['action_id'] else None
    if any(ident and record is None for ident, record in zip(links, [goal, decision, action])):
        raise ValueError('Linked company record not found')
    if action and decision and action['source_decision_id'] != decision['id']:
        raise ValueError('Action does not belong to the linked decision')
    if goal and decision and decision['goal_id'] != goal['id']:
        raise ValueError('Decision does not belong to the linked goal')
    if goal and action:
        source = cursor.execute('SELECT goal_id FROM decisions WHERE id = ?', (action['source_decision_id'],)).fetchone()
        if not source or source['goal_id'] != goal['id']:
            raise ValueError('Action does not belong to the linked goal')


def create_task(board_id, **fields):
    task = dict(title='', description='', acceptance_criteria='', assignee='owner', priority='medium',
                status='backlog', blocked_reason='', completion_note='', goal_id=None, decision_id=None, action_id=None)
    if set(fields) - set(task):
        raise ValueError('Unknown task fields')
    task.update(fields)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('BEGIN IMMEDIATE')
        board = cursor.execute('SELECT * FROM agile_boards WHERE id = ?', (board_id,)).fetchone()
        if not board:
            raise LookupError('Board not found')
        _validate_task(cursor, board, task)
        now = datetime.datetime.now().isoformat()
        cursor.execute('''INSERT INTO agile_tasks(board_id, title, description, acceptance_criteria, assignee,
            priority, status, blocked_reason, completion_note, goal_id, decision_id, action_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (board_id, task['title'], task['description'], task['acceptance_criteria'], task['assignee'], task['priority'], task['status'], task['blocked_reason'], task['completion_note'], task['goal_id'], task['decision_id'], task['action_id'], now, now))
        ident = cursor.lastrowid
        conn.commit()
        return dict(conn.execute('SELECT * FROM agile_tasks WHERE id = ?', (ident,)).fetchone())


def update_task(task_id, expected_version, **fields):
    allowed = {'title', 'description', 'acceptance_criteria', 'assignee', 'priority', 'status', 'blocked_reason', 'completion_note', 'goal_id', 'decision_id', 'action_id'}
    if not fields or set(fields) - allowed:
        raise ValueError('Invalid task update')
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('BEGIN IMMEDIATE')
        existing = cursor.execute('SELECT * FROM agile_tasks WHERE id = ?', (task_id,)).fetchone()
        if not existing:
            raise LookupError('Task not found')
        if existing['version'] != expected_version:
            raise RuntimeError('Task changed since it was loaded. Refresh before editing.')
        task = dict(existing)
        task.update(fields)
        board = cursor.execute('SELECT * FROM agile_boards WHERE id = ?', (task['board_id'],)).fetchone()
        _validate_task(cursor, board, task)
        cursor.execute('''UPDATE agile_tasks SET title = ?, description = ?, acceptance_criteria = ?, assignee = ?,
            priority = ?, status = ?, blocked_reason = ?, completion_note = ?, goal_id = ?, decision_id = ?, action_id = ?,
            updated_at = ?, version = version + 1 WHERE id = ? AND version = ?''',
            (task['title'], task['description'], task['acceptance_criteria'], task['assignee'], task['priority'], task['status'], task['blocked_reason'], task['completion_note'], task['goal_id'], task['decision_id'], task['action_id'], datetime.datetime.now().isoformat(), task_id, expected_version))
        conn.commit()
        return dict(conn.execute('SELECT * FROM agile_tasks WHERE id = ?', (task_id,)).fetchone())


ROADMAP_TASKS = [{'title': 'BE-01 · Development and company agile boards',
  'description': 'Dependencies: Existing owner auth and company records. Planning priority: First sprint.',
  'acceptance_criteria': 'Separate boards; task owner, priority, status and acceptance criteria; company '
                         'tasks link to valid goals/decisions/actions; stale updates rejected; completion '
                         'note required; board movement does not execute work',
  'priority': 'high'},
 {'title': 'BE-02 · Append-only activity event ledger',
  'description': 'Dependencies: BE-01 and existing workflow state functions. Planning priority: First '
                 'sprint.',
  'acceptance_criteria': 'New transitions retain actor, source, previous/new state and timestamp; retries do '
                         'not duplicate events; timeline reads retained events; legacy gaps are explicit',
  'priority': 'high'},
 {'title': 'BE-03 · Experiments and observation plans',
  'description': 'Dependencies: Existing outcomes, treasury and follow-ups. Planning priority: First sprint.',
  'acceptance_criteria': 'Hypothesis, baseline, expected result, budget/risk limit, linked action, '
                         'observation dates and evidence; compare results without inventing missing '
                         'measurements',
  'priority': 'high'},
 {'title': 'BE-04 · Evidence/source registry',
  'description': 'Dependencies: BE-03. Planning priority: Next.',
  'acceptance_criteria': 'Conclusions and observations reference dated sources; provenance and freshness '
                         'visible; missing/conflicting evidence stays explicit',
  'priority': 'medium'},
 {'title': 'BE-05 · Executive planning and workload',
  'description': 'Dependencies: BE-01, BE-02. Planning priority: Next.',
  'acceptance_criteria': 'Executives propose assigned tasks and dependencies; owner reviews plan; scheduler '
                         'respects active goals, budgets and execution gates; no duplicate runs',
  'priority': 'medium'},
 {'title': 'BE-06 · Structured executive discussion rounds',
  'description': 'Dependencies: Existing contributions, BE-04. Planning priority: Next.',
  'acceptance_criteria': 'Persist published proposals, critiques, revisions and final synthesis with speaker '
                         'and round; persona retained; guard unsupported owner claims',
  'priority': 'medium'},
 {'title': 'BE-07 · Scoped connector/capability inventory',
  'description': 'Dependencies: Existing resources/capabilities. Planning priority: Next.',
  'acceptance_criteria': 'Track requested/provided/verified access separately; credentials stay in secret '
                         'storage; health/revocation checks; resource fulfillment grants only configured '
                         'scope',
  'priority': 'medium'},
 {'title': 'BE-08 · Structured operating policies',
  'description': 'Dependencies: Existing treasury and approval gates. Planning priority: Later.',
  'acceptance_criteria': 'Owner-defined risk limits, spending limits, approval boundaries and prohibited '
                         'activities persist and are checked consistently',
  'priority': 'low'},
 {'title': 'BE-09 · Memory reconciliation',
  'description': 'Dependencies: BE-04, existing memory. Planning priority: Later.',
  'acceptance_criteria': 'Source-backed memories can be corrected, superseded or expired without deleting '
                         'provenance; contradictory lessons surface for review',
  'priority': 'low'},
 {'title': 'BE-10 · Reliable observation scheduling',
  'description': 'Dependencies: BE-03, existing checkpoints. Planning priority: Later.',
  'acceptance_criteria': 'Persist due dates, retries and claimed observation jobs; restart-safe execution; '
                         'data collection uses approved capabilities',
  'priority': 'low'},
 {'title': 'BE-11 · Agent activity stream',
  'description': 'Dependencies: BE-02, BE-05. Planning priority: Office support.',
  'acceptance_criteria': 'Authorized consumers receive real task/meeting/role events; reconnect/resume '
                         'supported; idle/unknown distinct; bounded retention',
  'priority': 'low'},
 {'title': 'BE-12 · Face, body and voice profiles',
  'description': 'Dependencies: Existing profiles. Planning priority: Office support.',
  'acceptance_criteria': 'Versioned per-agent visual/voice references and preferences; existing '
                         'identity/personality preserved; owner chooses assets/providers',
  'priority': 'low'},
 {'title': 'BE-13 · Departments and employee lifecycle',
  'description': 'Dependencies: BE-05, BE-08. Planning priority: Office support.',
  'acceptance_criteria': 'Persist organizational roles, capacity and relationships to work; employees cannot '
                         'inherit executive authority automatically',
  'priority': 'low'},
 {'title': 'BE-14 · Virtual personal lives',
  'description': 'Dependencies: BE-12, BE-13. Planning priority: Future simulation.',
  'acceptance_criteria': 'Separate simulation records for relationships, marriages/divorces and personal '
                         'events; clearly fictional; no influence on real approvals or business evidence '
                         'unless owner defines a policy',
  'priority': 'low'}]


def create_roadmap_board():
    """Create the planning template once, atomically; no business actions."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('BEGIN IMMEDIATE')
        existing = cursor.execute("SELECT * FROM agile_boards WHERE kind = 'development' AND name = 'Backend development roadmap' ORDER BY id LIMIT 1").fetchone()
        if existing:
            return dict(existing)
        now = datetime.datetime.now().isoformat()
        cursor.execute("INSERT INTO agile_boards(name, kind, created_at) VALUES ('Backend development roadmap', 'development', ?)", (now,))
        board_id = cursor.lastrowid
        for item in ROADMAP_TASKS:
            cursor.execute("""INSERT INTO agile_tasks(board_id, title, description, acceptance_criteria, assignee,
                priority, status, blocked_reason, completion_note, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'owner', ?, ?, '', ?, ?, ?)""",
                (board_id, item['title'], item['description'], item['acceptance_criteria'], item['priority'],
                 'done', 'Owner accepted Sprint 1 on 9 October 2026; appearance and voice refinements deferred to Sprint 2.', now, now))
        conn.commit()
        return dict(conn.execute('SELECT * FROM agile_boards WHERE id = ?', (board_id,)).fetchone())
