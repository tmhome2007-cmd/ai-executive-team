"""Safe run summaries and cooperative cancellation; existing ledgers own results."""

import datetime
import hashlib
import json
import threading
from memory.database import get_connection

_ACTIVE = set()
_ACTIVE_LOCK = threading.Lock()


def init_inspector(cursor):
    cursor.execute("""CREATE TABLE IF NOT EXISTS workflow_run_inspection (
        id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, step_id TEXT NOT NULL,
        brief_id INTEGER NOT NULL, stage TEXT NOT NULL, claimed_version INTEGER NOT NULL,
        prompt_digest TEXT NOT NULL, prompt_version TEXT NOT NULL, model_version TEXT NOT NULL,
        phase TEXT NOT NULL DEFAULT 'queued', error_category TEXT NOT NULL DEFAULT '',
        stop_requested INTEGER NOT NULL DEFAULT 0, control_version INTEGER NOT NULL DEFAULT 1,
        continued_from INTEGER, continued_by INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        UNIQUE(run_id,step_id))""")

    columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(workflow_run_inspection)")
    }
    for name in ("model_digest", "model_config_json"):
        if name not in columns:
            cursor.execute(
                f"ALTER TABLE workflow_run_inspection ADD COLUMN {name} TEXT"
            )  # nosec B608 # Fixed identifiers only.


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def register_run(
    brief_id,
    stage,
    claimed_version,
    prompt_digest,
    prompt_version,
    model_version,
    continued_from=None,
    *,
    model_identity=None,
):
    from workflows.step_checkpoints import init_step_checkpoints

    init_step_checkpoints()
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        step = f"{stage}:{claimed_version}"
        run = f"business:{brief_id}"
        now = _now()
        row = conn.execute(
            """INSERT INTO workflow_run_inspection(run_id,step_id,brief_id,stage,claimed_version,
            prompt_digest,prompt_version,model_version,continued_from,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                run,
                step,
                brief_id,
                stage,
                claimed_version,
                prompt_digest,
                prompt_version,
                model_version,
                continued_from,
                now,
                now,
            ),
        )
        ident = row.lastrowid
        if model_identity is not None:
            conn.execute(
                "UPDATE workflow_run_inspection SET model_digest=?,model_config_json=? WHERE id=?",
                (
                    model_identity["digest"],
                    json.dumps(
                        model_identity["configuration"], sort_keys=True, allow_nan=False
                    ),
                    ident,
                ),
            )
        if continued_from is not None:
            cursor = conn.execute(
                """UPDATE workflow_run_inspection SET continued_by=?,control_version=control_version+1,updated_at=?
                WHERE id=? AND continued_by IS NULL""",
                (ident, now, continued_from),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("This run already has a continuation; refresh")
        conn.commit()
    return ident, run, step


def live(ident, value):
    with _ACTIVE_LOCK:
        if value:
            _ACTIVE.add(ident)
        else:
            _ACTIVE.discard(ident)


def assert_running(ident):
    with get_connection() as conn:
        row = conn.execute(
            """SELECT i.stop_requested,i.claimed_version,i.stage,b.state,b.version
            FROM workflow_run_inspection i JOIN business_discovery b ON b.id=i.brief_id WHERE i.id=?""",
            (ident,),
        ).fetchone()
    if (
        not row
        or row["stop_requested"]
        or row["version"] != row["claimed_version"]
        or row["state"] != row["stage"] + "_running"
    ):
        raise RuntimeError(
            "Private run stopped or superseded; its output will not be published"
        )


def phase(ident, value, category=""):
    if value not in {
        "queued",
        "generating",
        "repairing",
        "publishing",
        "completed",
        "stopped",
        "interrupted",
        "failed",
    } or category not in {
        "",
        "owner_stop",
        "invalid_output",
        "generation_error",
        "interrupted",
        "publication_error",
    }:
        raise ValueError("Invalid inspection classification")
    with get_connection() as conn:
        conn.execute(
            """UPDATE workflow_run_inspection SET phase=?,error_category=?,updated_at=? WHERE id=? AND phase!='completed' AND (stop_requested=0 OR ?='stopped')""",
            (value, category, _now(), ident, value),
        )
        conn.commit()


def recover_inspector():
    """Startup never schedules another run; claims remain inconclusive."""
    with get_connection() as conn:
        conn.execute(
            """UPDATE workflow_run_inspection SET phase=CASE WHEN stop_requested=1 THEN 'stopped' ELSE 'interrupted' END,
            error_category=CASE WHEN stop_requested=1 THEN 'owner_stop' ELSE 'interrupted' END,
            updated_at=? WHERE phase IN ('queued','generating','repairing','publishing')""",
            (_now(),),
        )
        conn.commit()


def _row(conn, ident):
    row = conn.execute(
        "SELECT * FROM workflow_run_inspection WHERE id=?", (ident,)
    ).fetchone()
    if not row:
        raise LookupError("Inspectable private run not found")
    return dict(row)


def _elapsed(start, end):
    try:
        return max(
            0,
            round(
                (
                    datetime.datetime.fromisoformat(end)
                    - datetime.datetime.fromisoformat(start)
                ).total_seconds(),
                1,
            ),
        )
    except (TypeError, ValueError):
        return None


def _binding_guidance(cursor, brief_id):
    """Fixed owner-facing messages; never expose approval notes or exception text."""
    from memory.workflow_templates import template_context
    from memory.practice_quality import assert_specification
    from memory.executive_skills import skill_context

    try:
        template = template_context(cursor, brief_id, require_reviewed=False)
        if template and not template["usable"]:
            return (
                "template_withdrawn",
                "Bound workflow version was withdrawn.",
                "Review a new workflow version and create a new brief; earlier artifacts remain available under their retention policy.",
            )
        assert_specification(cursor, brief_id)
        skill = skill_context(cursor, brief_id, require_usable=False)
        if skill and not skill["usable"]:
            revoked = skill["state"] == "revoked"
            return (
                "skill_revoked" if revoked else "assessments_corrected",
                (
                    "Skill version revoked."
                    if revoked
                    else "Source assessments changed or skill acceptance is missing."
                ),
                "Propose and review a new skill version using current assessments, then create a new private exercise. Earlier samples stay in history.",
            )
    except (ValueError, RuntimeError, LookupError):
        return (
            "exercise_changed",
            "The approved exercise or its bindings cannot be validated.",
            "Refresh and review the exercise; create a new owner-reviewed brief if its approved inputs changed.",
        )
    return "", "", ""


def _summary(conn, row, checkpoint=None):
    with _ACTIVE_LOCK:
        active = row["id"] in _ACTIVE
    b = conn.execute(
        "SELECT state,version,sample,review_json FROM business_discovery WHERE id=?",
        (row["brief_id"],),
    ).fetchone()
    latest = conn.execute(
        "SELECT MAX(id) FROM workflow_run_inspection WHERE brief_id=?",
        (row["brief_id"],),
    ).fetchone()[0]
    can_continue = bool(
        b
        and latest == row["id"]
        and b["version"] == row["claimed_version"] + 1
        and b["state"] == "needs_review"
        and row["stage"] in {"practice", "revision"}
        and row["phase"] in {"stopped", "interrupted", "failed"}
        and not active
        and row["continued_by"] is None
    )
    if row["stage"] == "practice" and b and b["sample"]:
        can_continue = False
    if row["stage"] == "revision" and b:
        count = conn.execute(
            "SELECT COUNT(*) FROM business_practice_samples WHERE brief_id=?",
            (row["brief_id"],),
        ).fetchone()[0]
        if not (b["sample"] and b["review_json"] and 1 <= count < 10):
            can_continue = False
    continuation_blocked_reason = ""
    recovery_code, recovery_action = (
        "refresh",
        "Refresh runs to check the current brief and controls.",
    )
    if can_continue and not (row.get("model_digest") and row.get("model_config_json")):
        can_continue = False
        continuation_blocked_reason = "Earlier model identity is unknown."
        recovery_code = "model_identity_unknown"
        recovery_action = "Create a new owner-reviewed exercise; this legacy run cannot be reused. Existing output stays in history."
    if can_continue:
        # The same eligibility check is used inside the transactional claim.
        recovery_code, continuation_blocked_reason, recovery_action = _binding_guidance(
            conn.cursor(), row["brief_id"]
        )
        if continuation_blocked_reason:
            can_continue = False
        else:
            recovery_code = "continue_private"
            recovery_action = "Continue this private exercise explicitly; the resulting sample still needs owner review."
    elif continuation_blocked_reason:
        pass
    elif active and row["stop_requested"]:
        recovery_code = "wait_for_worker"
        recovery_action = "Wait for the current local model call to finish; its output will be discarded. Then refresh runs."
    elif row["continued_by"] is not None or latest != row["id"]:
        recovery_code = "superseded"
        recovery_action = "Inspect the latest run for this brief; this earlier attempt cannot continue."
    elif row["phase"] == "completed":
        recovery_code = "review_sample"
        recovery_action = "Review the saved research or sample in Research & practice."
    elif row["stage"] == "research" and not active:
        recovery_code = "new_research"
        recovery_action = (
            "Create a new research brief; existing evidence snapshots stay unchanged."
        )
    terminal = row["phase"] in {"completed", "failed", "stopped", "interrupted"}
    return dict(
        id=row["id"],
        family="private_business_generation",
        brief_id=row["brief_id"],
        stage=row["stage"],
        phase=row["phase"],
        checkpoint_status=checkpoint["status"] if checkpoint else "not_claimed",
        duration_seconds=_elapsed(
            row["created_at"], row["updated_at"] if terminal else _now()
        ),
        error_category=row["error_category"]
        or (
            "unknown_outcome"
            if checkpoint and checkpoint["status"] == "inconclusive"
            else ""
        ),
        continuation_blocked_reason=continuation_blocked_reason,
        recovery_code=recovery_code,
        recovery_action=recovery_action,
        pending_input=(
            continuation_blocked_reason
            if continuation_blocked_reason
            else (
                "Wait for the current local model call to finish; its output will be discarded."
                if active and row["stop_requested"]
                else (
                    "Owner may continue the same private exercise."
                    if can_continue
                    else (
                        "Create a new research brief; existing evidence snapshots stay unchanged."
                        if terminal
                        and row["stage"] == "research"
                        and row["phase"] != "completed"
                        else (
                            "Owner sample assessment remains separate."
                            if row["phase"] == "completed"
                            else ""
                        )
                    )
                )
            )
        ),
        prompt_digest=row["prompt_digest"],
        prompt_version=row["prompt_version"],
        model_version=row["model_version"],
        model_digest=row.get("model_digest"),
        model_configuration=(
            json.loads(row["model_config_json"])
            if row.get("model_config_json")
            else None
        ),
        model_note=(
            "Resolved local Ollama digest and recorded inference settings."
            if row.get("model_digest")
            else "Unknown: legacy configured tag only; no digest was captured."
        ),
        control_version=row["control_version"],
        can_stop=bool(
            b
            and active
            and not row["stop_requested"]
            and b["version"] == row["claimed_version"]
            and b["state"] == row["stage"] + "_running"
        ),
        can_continue=can_continue,
        worker_active=active,
        stop_requested=bool(row["stop_requested"]),
        continued_from=row["continued_from"],
        continued_by=row["continued_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def get_run(ident):
    from workflows.step_checkpoints import init_step_checkpoints

    init_step_checkpoints()
    with get_connection() as conn:
        row = _row(conn, ident)
        checkpoint = conn.execute(
            "SELECT status FROM workflow_step_checkpoints WHERE run_id=? AND step_id=?",
            (row["run_id"], row["step_id"]),
        ).fetchone()
        return _summary(conn, row, checkpoint)


def list_runs(limit=50, offset=0):
    from workflows.step_checkpoints import init_step_checkpoints

    init_step_checkpoints()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM workflow_run_inspection ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        private = []
        for row in rows:
            row = dict(row)
            checkpoint = conn.execute(
                "SELECT status FROM workflow_step_checkpoints WHERE run_id=? AND step_id=?",
                (row["run_id"], row["step_id"]),
            ).fetchone()
            private.append(_summary(conn, row, checkpoint))
        legacy = []
        for row in conn.execute(
            """SELECT c.run_id,c.step_id,c.status,c.created_at,c.updated_at FROM workflow_step_checkpoints c
            WHERE NOT EXISTS(SELECT 1 FROM workflow_run_inspection i WHERE i.run_id=c.run_id AND i.step_id=c.step_id)
            ORDER BY c.updated_at DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        ):
            # Never expose raw keys or result_json, which can contain private data.
            legacy.append(
                dict(
                    reference=hashlib.sha256(
                        (row["run_id"] + "\0" + row["step_id"]).encode()
                    ).hexdigest()[:16],
                    family="existing_workflow",
                    checkpoint_status=row["status"],
                    duration_seconds=_elapsed(
                        row["created_at"],
                        _now() if row["status"] == "running" else row["updated_at"],
                    ),
                    error_category=(
                        "unknown_outcome" if row["status"] == "inconclusive" else ""
                    ),
                    pending_input=(
                        "Reconcile uncertain outcomes; this inspector cannot replay existing actions."
                        if row["status"] == "inconclusive"
                        else ""
                    ),
                    prompt_version=None,
                    model_version=None,
                    can_stop=False,
                    can_continue=False,
                )
            )
    return dict(
        private_runs=private,
        existing_steps=legacy,
        scope="Metadata only. Duration includes waiting and laptop sleep; elapsed time alone never authorizes retry.",
    )


def stop_run(ident, expected_version):
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = _row(conn, ident)
        if row["control_version"] != expected_version:
            raise RuntimeError("Run controls changed; refresh")
        summary = _summary(conn, row)
        if not summary["can_stop"]:
            raise RuntimeError("This private run is not stoppable; refresh")
        cursor = conn.execute(
            "UPDATE business_discovery SET state='needs_review',version=version+1 WHERE id=? AND version=? AND state=?",
            (row["brief_id"], row["claimed_version"], row["stage"] + "_running"),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("Run already published or changed; refresh")
        conn.execute(
            "UPDATE workflow_run_inspection SET stop_requested=1,phase='stopped',error_category='owner_stop',control_version=control_version+1,updated_at=? WHERE id=?",
            (_now(), ident),
        )
        conn.execute(
            "UPDATE workflow_step_checkpoints SET status='inconclusive',updated_at=? WHERE run_id=? AND step_id=? AND status='running'",
            (_now(), row["run_id"], row["step_id"]),
        )
        conn.commit()
    return get_run(ident)


def claim_continuation(ident, expected_control, expected_brief):
    """Atomically claim a fresh private attempt, retaining the same approved rubric."""
    from memory.practice_quality import assert_specification
    from memory.executive_skills import skill_context

    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = _row(conn, ident)
        if (
            row["control_version"] != expected_control
            or not _summary(conn, row)["can_continue"]
        ):
            raise RuntimeError("Run cannot continue or controls changed; refresh")
        from memory.workflow_templates import template_context

        template_context(conn.cursor(), row["brief_id"])
        assert_specification(conn.cursor(), row["brief_id"])
        skill_context(conn.cursor(), row["brief_id"])
        cursor = conn.execute(
            "UPDATE business_discovery SET state=?,version=version+1 WHERE id=? AND version=? AND state='needs_review'",
            (row["stage"] + "_running", row["brief_id"], expected_brief),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("Brief changed; refresh before continuing")
        conn.commit()
    from memory.business_discovery import get_brief

    return row, get_brief(row["brief_id"])


def cached_result(previous, prompt_digest, prompt_version):
    """Reuse a durably completed result only if current inputs and code still match."""
    if not previous.get("model_digest") or not previous.get("model_config_json"):
        raise RuntimeError(
            "Earlier model identity is unknown; create a new owner-reviewed exercise"
        )
    if (
        previous["prompt_digest"] != prompt_digest
        or previous["prompt_version"] != prompt_version
    ):
        raise RuntimeError(
            "Prompt or inputs changed; create a new owner-reviewed exercise"
        )
    with get_connection() as conn:
        row = conn.execute(
            "SELECT status,input_digest,result_json FROM workflow_step_checkpoints WHERE run_id=? AND step_id=?",
            (previous["run_id"], previous["step_id"]),
        ).fetchone()
    if (
        row
        and row["status"] == "succeeded"
        and row["input_digest"] == prompt_digest
        and row["result_json"] is not None
    ):
        value = json.loads(row["result_json"])
        if not isinstance(value, str):
            raise ValueError("Unexpected private checkpoint result")
        return value
    return None


def complete_publication(cursor, run_ident, brief_id, claimed_version):
    """Acknowledge the authoritative sample write in its transaction."""
    result = cursor.execute(
        "UPDATE workflow_run_inspection SET phase='completed',error_category='',updated_at=? WHERE id=? AND brief_id=? AND claimed_version=? AND stop_requested=0",
        (_now(), run_ident, brief_id, claimed_version),
    )
    if result.rowcount != 1:
        raise RuntimeError("Private run publication no longer owned; refresh")
