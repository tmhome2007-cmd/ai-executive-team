"""Virtual workforce metadata. Employees never gain executive tools or approval authority."""

import datetime
import json
import re
from memory.database import get_connection
from memory.experiments import _text, _number
from agents.identities import EXECUTIVE_NAMES
from workflows.capability_policy import normalize_executive_role

DEPARTMENTS = [
    ("leadership", "Leadership", "ceo", "03"),
    ("finance", "Finance & risk", "cfo", "03"),
    ("operations", "Operations", "coo", "02"),
    ("growth", "Growth", "cso", "02"),
    ("technology", "Product & technology", "cto", "01"),
]


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def init_organization(cursor):
    cursor.execute("""CREATE TABLE IF NOT EXISTS company_departments (
        id INTEGER PRIMARY KEY, department_key TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
        executive_key TEXT NOT NULL, floor TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
        version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL)""")
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS virtual_employees (
        id INTEGER PRIMARY KEY, creation_key TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
        job_title TEXT NOT NULL, department_id INTEGER NOT NULL,
        capacity_hours REAL NOT NULL, status TEXT NOT NULL DEFAULT 'onboarding',
        version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
    )
    cursor.execute("""CREATE TABLE IF NOT EXISTS employee_assignments (
        id INTEGER PRIMARY KEY, employee_id INTEGER NOT NULL, task_id INTEGER NOT NULL,
        hours REAL NOT NULL, status TEXT NOT NULL DEFAULT 'assigned',
        version INTEGER NOT NULL DEFAULT 1, note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL)""")
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS employee_open_task ON employee_assignments(employee_id,task_id) WHERE status IN ('assigned','in_progress')"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS employee_department ON virtual_employees(department_id,status,id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS employee_workload ON employee_assignments(employee_id,status)"
    )
    for key, name, executive, floor in DEPARTMENTS:
        cursor.execute(
            "INSERT OR IGNORE INTO company_departments(department_key,name,executive_key,floor,created_at) VALUES(?,?,?,?,?)",
            (key, name, executive, floor, now()),
        )


def _page(limit, offset):
    if (
        type(limit) is not int
        or not 1 <= limit <= 100
        or type(offset) is not int
        or offset < 0
    ):
        raise ValueError("Invalid pagination")


def departments(limit=50, offset=0):
    _page(limit, offset)
    with get_connection() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM company_departments ORDER BY id LIMIT ? OFFSET ?",
                (limit, offset),
            )
        ]


def save_department(*, department_key, name, executive_key, floor):
    if not isinstance(department_key, str) or not re.fullmatch(
        r"[a-z][a-z0-9_-]{0,49}", department_key
    ):
        raise ValueError("Invalid department key")
    name = _text(name, "department name", 120)
    if executive_key not in EXECUTIVE_NAMES or floor not in {"01", "02", "03"}:
        raise ValueError("Choose an existing executive and office floor")
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute(
            "SELECT 1 FROM company_departments WHERE department_key=?",
            (department_key,),
        ).fetchone():
            raise RuntimeError("Department key already exists")
        ident = conn.execute(
            "INSERT INTO company_departments(department_key,name,executive_key,floor,created_at) VALUES(?,?,?,?,?)",
            (department_key, name, executive_key, floor, now()),
        ).lastrowid
        conn.commit()
    return ident


def update_department(ident, expected_version, *, name, executive_key, floor, status):
    name = _text(name, "department name", 120)
    if (
        executive_key not in EXECUTIVE_NAMES
        or floor not in {"01", "02", "03"}
        or status not in {"active", "archived"}
    ):
        raise ValueError("Invalid department settings")
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM company_departments WHERE id=?", (ident,)
        ).fetchone()
        if not row:
            raise LookupError("Department not found")
        if type(expected_version) is not int or expected_version != row["version"]:
            raise RuntimeError("Department changed; refresh")
        if row["status"] == "archived":
            raise RuntimeError(
                "Archived departments are retained and cannot be reactivated"
            )
        if (
            status == "archived"
            and conn.execute(
                "SELECT 1 FROM virtual_employees WHERE department_id=? AND status!='retired'",
                (ident,),
            ).fetchone()
        ):
            raise ValueError(
                "Reassign or retire employees before archiving their department"
            )
        conn.execute(
            "UPDATE company_departments SET name=?,executive_key=?,floor=?,status=?,version=version+1 WHERE id=?",
            (name, executive_key, floor, status, ident),
        )
        conn.commit()
    return ident


def employees(limit=50, offset=0):
    _page(limit, offset)
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT e.*,d.name AS department_name,d.executive_key AS responsible_executive,COALESCE((SELECT SUM(a.hours) FROM employee_assignments a WHERE a.employee_id=e.id AND a.status IN ('assigned','in_progress')),0) AS allocated_hours FROM virtual_employees e JOIN company_departments d ON d.id=e.department_id ORDER BY e.id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [
        {
            **dict(r),
            "character_key": f"employee:{r['id']}",
            "execution_authority": "none",
            "adult": True,
        }
        for r in rows
    ]


def create_employee(*, creation_key, name, job_title, department_id, capacity_hours):
    from memory.character_profiles import default_presentation

    creation_key = _text(creation_key, "employee creation key", 80)
    name = _text(name, "employee name", 120)
    job_title = _text(job_title, "employee job title", 120)
    if normalize_executive_role(job_title) or normalize_executive_role(
        job_title.split(" (", 1)[0]
    ):
        raise ValueError("Employee titles cannot impersonate executive identities")
    capacity = _number(capacity_hours, "weekly capacity")
    if not 0 <= capacity <= 168:
        raise ValueError("Weekly capacity must be between zero and 168 hours")
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        department = conn.execute(
            "SELECT status FROM company_departments WHERE id=?", (department_id,)
        ).fetchone()
        if not department or department["status"] != "active":
            raise ValueError("Choose an active department")
        old = conn.execute(
            "SELECT * FROM virtual_employees WHERE creation_key=?", (creation_key,)
        ).fetchone()
        if old:
            if any(
                old[k] != v
                for k, v in dict(
                    name=name,
                    job_title=job_title,
                    department_id=department_id,
                    capacity_hours=capacity,
                ).items()
            ):
                raise RuntimeError("Employee creation key reused with different fields")
            return old["id"]
        ident = conn.execute(
            "INSERT INTO virtual_employees(creation_key,name,job_title,department_id,capacity_hours,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (creation_key, name, job_title, department_id, capacity, now(), now()),
        ).lastrowid
        presentation = default_presentation(f"employee:{ident}", ident)
        conn.execute(
            "INSERT INTO character_profiles(character_key,version,appearance,body,voice,created_at) VALUES(?,1,?,?,?,?)",
            (
                f"employee:{ident}",
                json.dumps(presentation["appearance"]),
                json.dumps(presentation["body"]),
                json.dumps(presentation["voice"]),
                now(),
            ),
        )
        conn.commit()
    return ident


def update_employee(ident, expected_version, *, department_id, capacity_hours, status):
    capacity = _number(capacity_hours, "weekly capacity")
    if not 0 <= capacity <= 168 or status not in {
        "onboarding",
        "active",
        "suspended",
        "retired",
    }:
        raise ValueError("Invalid employee settings")
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM virtual_employees WHERE id=?", (ident,)
        ).fetchone()
        if not row:
            raise LookupError("Employee not found")
        if type(expected_version) is not int or expected_version != row["version"]:
            raise RuntimeError("Employee changed; refresh")
        transitions = {
            "onboarding": {"onboarding", "active", "retired"},
            "active": {"active", "suspended", "retired"},
            "suspended": {"suspended", "active", "retired"},
            "retired": set(),
        }
        if status not in transitions[row["status"]]:
            raise ValueError("Invalid employee lifecycle transition")
        if not conn.execute(
            "SELECT 1 FROM company_departments WHERE id=? AND status='active'",
            (department_id,),
        ).fetchone():
            raise ValueError("Choose an active department")
        allocated = conn.execute(
            "SELECT COALESCE(SUM(hours),0) FROM employee_assignments WHERE employee_id=? AND status IN ('assigned','in_progress')",
            (ident,),
        ).fetchone()[0]
        if allocated > capacity or (
            allocated and (status != "active" or department_id != row["department_id"])
        ):
            raise ValueError(
                "Resolve assigned work before reducing capacity, moving, suspending or retiring an employee"
            )
        conn.execute(
            "UPDATE virtual_employees SET department_id=?,capacity_hours=?,status=?,version=version+1,updated_at=? WHERE id=?",
            (department_id, capacity, status, now(), ident),
        )
        conn.commit()
    return ident


def assignments(limit=50, offset=0):
    _page(limit, offset)
    with get_connection() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT a.*,e.name AS employee_name,t.title AS task_title FROM employee_assignments a JOIN virtual_employees e ON e.id=a.employee_id JOIN agile_tasks t ON t.id=a.task_id ORDER BY a.id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        ]


def assign_work(employee_id, task_id, hours):
    hours = _number(hours, "assigned hours")
    if not 0 < hours <= 168:
        raise ValueError("Assignment requires positive hours up to 168")
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        employee = conn.execute(
            "SELECT * FROM virtual_employees WHERE id=?", (employee_id,)
        ).fetchone()
        if not employee or employee["status"] != "active":
            raise ValueError("Only active employees can receive work")
        task = conn.execute(
            "SELECT t.*,b.kind FROM agile_tasks t JOIN agile_boards b ON b.id=t.board_id WHERE t.id=?",
            (task_id,),
        ).fetchone()
        if (
            not task
            or task["kind"] != "company"
            or task["status"] not in {"ready", "in_progress"}
        ):
            raise ValueError("Choose a ready or in-progress company task")
        if (
            task["goal_id"]
            and not conn.execute(
                "SELECT 1 FROM company_goals WHERE id=? AND status='active'",
                (task["goal_id"],),
            ).fetchone()
        ):
            raise ValueError("Linked goal must be active")
        if conn.execute(
            "SELECT 1 FROM employee_assignments WHERE employee_id=? AND task_id=? AND status IN ('assigned','in_progress')",
            (employee_id, task_id),
        ).fetchone():
            raise RuntimeError("Employee already has this assignment")
        allocated = conn.execute(
            "SELECT COALESCE(SUM(hours),0) FROM employee_assignments WHERE employee_id=? AND status IN ('assigned','in_progress')",
            (employee_id,),
        ).fetchone()[0]
        if allocated + hours > employee["capacity_hours"]:
            raise ValueError("Assignment exceeds employee weekly capacity")
        ident = conn.execute(
            "INSERT INTO employee_assignments(employee_id,task_id,hours,created_at,updated_at) VALUES(?,?,?,?,?)",
            (employee_id, task_id, hours, now(), now()),
        ).lastrowid
        conn.commit()
    return ident


def review_assignment(ident, expected_version, status, note):
    note = _text(note, "assignment review note", 2000)
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM employee_assignments WHERE id=?", (ident,)
        ).fetchone()
        if not row:
            raise LookupError("Assignment not found")
        if type(expected_version) is not int or expected_version != row["version"]:
            raise RuntimeError("Assignment changed; refresh")
        transitions = {
            "assigned": {"in_progress", "cancelled"},
            "in_progress": {"completed", "cancelled"},
            "completed": set(),
            "cancelled": set(),
        }
        if status not in transitions[row["status"]]:
            raise ValueError("Invalid assignment transition")
        if status in {"in_progress", "completed"}:
            task = conn.execute(
                "SELECT t.status,t.goal_id,e.status AS employee_status FROM agile_tasks t JOIN virtual_employees e ON e.id=? WHERE t.id=?",
                (row["employee_id"], row["task_id"]),
            ).fetchone()
            if (
                not task
                or task["status"] not in {"ready", "in_progress"}
                or task["employee_status"] != "active"
            ):
                raise ValueError("Employee or company task is no longer active")
            if (
                task["goal_id"]
                and not conn.execute(
                    "SELECT 1 FROM company_goals WHERE id=? AND status='active'",
                    (task["goal_id"],),
                ).fetchone()
            ):
                raise ValueError("Linked goal must be active")
        conn.execute(
            "UPDATE employee_assignments SET status=?,note=?,version=version+1,updated_at=? WHERE id=?",
            (status, note, now(), ident),
        )
        conn.commit()
    return ident


def office_roster(limit=50, offset=0, floor=None):
    from memory.character_profiles import _row

    _page(limit, offset)
    if floor is not None and floor not in {"01", "02", "03"}:
        raise ValueError("Invalid office floor")
    clause = "WHERE d.floor=?" if floor else ""
    params = (floor, limit, offset) if floor else (limit, offset)
    with get_connection() as conn:
        rows = conn.execute(
            f"""SELECT e.id,e.name,e.job_title,e.status,d.name AS department_name,d.floor,
            p.character_key,p.version,p.appearance,p.body,p.voice,
            COALESCE((SELECT SUM(a.hours) FROM employee_assignments a WHERE a.employee_id=e.id AND a.status IN ('assigned','in_progress')),0) AS allocated_hours
            FROM virtual_employees e JOIN company_departments d ON d.id=e.department_id
            JOIN character_profiles p ON p.character_key='employee:'||e.id AND p.version=(SELECT MAX(version) FROM character_profiles x WHERE x.character_key=p.character_key)
            {clause} ORDER BY e.id DESC LIMIT ? OFFSET ?""",  # nosec B608 # Fixed clause; floor/limits are bound.
            params,
        ).fetchall()
    return [
        {
            **{
                k: r[k]
                for k in (
                    "id",
                    "name",
                    "job_title",
                    "status",
                    "department_name",
                    "floor",
                    "allocated_hours",
                )
            },
            "presentation": _row(r),
        }
        for r in rows
    ]
