"""Fictional adult presentation/workforce/social tests; no external services or business effects."""

import copy
import datetime
import sqlite3
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import test_experiments as experiments_tests
from memory.database import (
    get_connection,
    get_company_activity,
    create_company_goal,
    get_executive_memories,
)
from memory.character_profiles import (
    get_character,
    save_character,
    character_history,
    validate_presentation,
)
from memory.organization import (
    departments,
    create_employee,
    update_employee,
    employees,
    assign_work,
    assignments,
    review_assignment,
    update_department,
)
from memory.personal_simulation import (
    settings,
    set_enabled,
    record_personal_event,
    relationship,
    events,
)
from memory.agile import create_board, create_task
from workflows.capability_policy import require_action_capability
from agents.executive_agents import get_executive_profiles, EXECUTIVE_AGENTS_NO_TOOLS


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class PeopleSimulationTests(unittest.TestCase):
    setUp = experiments_tests.ExperimentTests.setUp
    tearDown = experiments_tests.ExperimentTests.tearDown

    def employee(self, key="synthetic-employee", capacity=10):
        ident = create_employee(
            creation_key=key,
            name="Synthetic adult employee",
            job_title="Research assistant",
            department_id=departments()[0]["id"],
            capacity_hours=capacity,
        )
        update_employee(
            ident,
            1,
            department_id=departments()[0]["id"],
            capacity_hours=capacity,
            status="active",
        )
        return ident

    def task(self, title="Synthetic company task"):
        board = create_board("Synthetic company board", "company")
        return create_task(
            board,
            title=title,
            acceptance_criteria="Owner reviews recorded work",
            status="ready",
        )["id"]

    def enable(self):
        set_enabled(settings()["version"], True, "Owner enables fictional simulation")

    def event(
        self,
        key,
        kind,
        left="executive:ceo",
        right="executive:cfo",
        version=0,
        **changes,
    ):
        return record_personal_event(
            event_key=key,
            kind=kind,
            character_key=left,
            partner_key=right,
            expected_relationship_version=version,
            narrative="FICTIONAL: synthetic personal event",
            simulated_at=stamp(),
            **changes,
        )

    def test_kai_specification_and_other_profiles_are_seeded_once(self):
        profile = get_character("executive:ceo")
        self.assertIn("Black man", profile["appearance"]["description"])
        self.assertFalse(profile["appearance"]["beard"])
        self.assertEqual(profile["appearance"]["hair_style"], "dreadlocks")
        self.assertEqual(profile["appearance"]["hair_color"], "#111111")
        self.assertEqual(profile["appearance"]["eye_color"], "#171717")
        self.assertEqual(profile["appearance"]["eye_tint"], "#991b1b")
        self.assertEqual(profile["body"]["height_cm"], 190)
        self.assertEqual(profile["body"]["build"], "well_built")
        all_profiles = get_executive_profiles(include_presentation=True)
        self.assertEqual(len(all_profiles), 11)
        self.assertTrue(all(p["presentation"]["adult"] for p in all_profiles.values()))
        from memory.database import init_db

        init_db()
        self.assertEqual(len(character_history("executive:ceo")), 1)

    def test_profile_version_history_retains_reasoning_personality_and_rejects_stale_update(
        self,
    ):
        old = get_character("executive:ceo")
        personas = get_executive_profiles()
        changed = copy.deepcopy(old)
        changed["voice"]["rate"] = 1.1
        updated = save_character(
            "executive:ceo", 1, changed["appearance"], changed["body"], changed["voice"]
        )
        self.assertEqual(updated["version"], 2)
        self.assertEqual(get_executive_profiles(), personas)
        self.assertEqual(character_history("executive:ceo")[-1]["voice"]["rate"], 0.9)
        with self.assertRaises(RuntimeError):
            save_character(
                "executive:ceo", 1, old["appearance"], old["body"], old["voice"]
            )
        with get_connection() as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("DELETE FROM character_profiles")

    def test_presentation_rejects_remote_assets_secrets_and_malformed_styles(self):
        original = get_character("executive:ceo")
        for field, value in [
            ("hair_style", []),
            ("skin_tone", "url(https://example.test/collect)"),
            ("description", "api_key=do-not-store"),
        ]:
            changed = copy.deepcopy(original)
            changed["appearance"][field] = value
            with self.assertRaises(ValueError):
                validate_presentation(
                    changed["appearance"], changed["body"], changed["voice"]
                )
        for field, value in [
            ("asset_ref", "https://example.test/avatar"),
            ("build", {}),
            ("height_cm", float("nan")),
        ]:
            changed = copy.deepcopy(original)
            changed["body"][field] = value
            with self.assertRaises(ValueError):
                validate_presentation(
                    changed["appearance"], changed["body"], changed["voice"]
                )
        changed = copy.deepcopy(original)
        changed["voice"]["provider"] = "remote_clone"
        with self.assertRaises(ValueError):
            validate_presentation(
                changed["appearance"], changed["body"], changed["voice"]
            )

    def test_owner_selected_portrait_defaults_and_natural_voice_pitch(self):
        for key in ("cfo", "general_counsel", "cmo", "board_director", "cto"):
            profile = get_character(f"executive:{key}")
            self.assertEqual(profile["appearance"]["portrait_style"], "feminine")
            self.assertIn("woman", profile["appearance"]["description"])
            self.assertFalse(profile["appearance"]["beard"])
            self.assertEqual(profile["voice"]["pitch"], 1.0)
        self.assertEqual(
            get_character("executive:chro")["appearance"]["portrait_style"],
            "androgynous",
        )
        profile = get_character("executive:ceo")
        changed = copy.deepcopy(profile)
        changed["appearance"]["portrait_style"] = "invalid"
        with self.assertRaises(ValueError):
            validate_presentation(
                changed["appearance"], changed["body"], changed["voice"]
            )
        del changed["appearance"]["portrait_style"]
        appearance, _, _ = validate_presentation(
            changed["appearance"], changed["body"], changed["voice"]
        )
        self.assertEqual(appearance["portrait_style"], "androgynous")

    def test_legacy_default_upgrade_retains_history_and_skips_owner_edits(self):
        import json
        from memory.character_profiles import default_presentation
        from agents.identities import EXECUTIVE_NAMES
        from memory.database import init_db

        for key in ("cfo", "cto"):
            old = default_presentation(
                key, list(EXECUTIVE_NAMES).index(key), legacy=True
            )
            if key == "cto":
                old["appearance"]["description"] = "Owner chosen appearance"
            with get_connection() as conn:
                # Disposable fixture only: emulate a pre-upgrade database.
                conn.execute("DROP TRIGGER character_no_update")
                conn.execute(
                    "UPDATE character_profiles SET appearance=?,body=?,voice=? WHERE character_key=?",
                    (
                        json.dumps(old["appearance"]),
                        json.dumps(old["body"]),
                        json.dumps(old["voice"]),
                        f"executive:{key}",
                    ),
                )
                conn.commit()
            init_db()
        self.assertEqual(get_character("executive:cfo")["version"], 2)
        self.assertEqual(len(character_history("executive:cfo")), 2)
        self.assertNotIn(
            "portrait_style", character_history("executive:cfo")[-1]["appearance"]
        )
        self.assertEqual(get_character("executive:cto")["version"], 2)
        self.assertEqual(
            get_character("executive:cto")["appearance"]["portrait_style"], "feminine"
        )
        self.assertEqual(
            get_character("executive:cto")["voice"],
            default_presentation(
                "cto", list(EXECUTIVE_NAMES).index("cto"), legacy=True
            )["voice"],
        )
        self.assertEqual(
            get_character("executive:cto")["appearance"]["description"],
            "Owner chosen appearance",
        )
        init_db()
        self.assertEqual(len(character_history("executive:cfo")), 2)

    def test_employee_creation_idempotence_and_no_executive_authority(self):
        ident = create_employee(
            creation_key="same",
            name="Fictional employee",
            job_title="Test assistant",
            department_id=1,
            capacity_hours=8,
        )
        self.assertEqual(
            create_employee(
                creation_key="same",
                name="Fictional employee",
                job_title="Test assistant",
                department_id=1,
                capacity_hours=8,
            ),
            ident,
        )
        with self.assertRaises(RuntimeError):
            create_employee(
                creation_key="same",
                name="Other employee",
                job_title="Test assistant",
                department_id=1,
                capacity_hours=8,
            )
        self.assertEqual(get_character(f"employee:{ident}")["version"], 1)
        self.assertEqual(employees()[0]["execution_authority"], "none")
        self.assertNotIn(f"employee:{ident}", EXECUTIVE_AGENTS_NO_TOOLS)
        with self.assertRaises(ValueError):
            require_action_capability(f"employee:{ident}", "shell")
        with self.assertRaises(ValueError):
            create_employee(
                creation_key="spoof",
                name="Fake executive",
                job_title="Chief Executive Officer (CEO)",
                department_id=1,
                capacity_hours=8,
            )

    def test_employee_work_capacity_is_atomic_and_only_company_tasks_are_allowed(self):
        employee = self.employee(capacity=5)
        tasks = [self.task("First task"), self.task("Second task")]
        barrier = threading.Barrier(2)

        def assign(task):
            barrier.wait()
            try:
                assign_work(employee, task, 5)
                return True
            except ValueError:
                return False

        with ThreadPoolExecutor(2) as workers:
            self.assertEqual(sum(workers.map(assign, tasks)), 1)
        self.assertEqual(len(assignments()), 1)
        board = create_board("Development work", "development")
        development = create_task(
            board, title="Code work", acceptance_criteria="Tests", status="ready"
        )["id"]
        with self.assertRaises(ValueError):
            assign_work(employee, development, 1)
        with self.assertRaises(ValueError):
            update_employee(
                employee, 2, department_id=1, capacity_hours=0, status="active"
            )
        with self.assertRaises(ValueError):
            update_employee(
                employee, 2, department_id=1, capacity_hours=5, status="retired"
            )

    def test_assignment_lifecycle_releases_capacity_without_executing_company_task(
        self,
    ):
        employee = self.employee()
        task = self.task()
        ident = assign_work(employee, task, 5)
        review_assignment(ident, 1, "in_progress", "Owner records synthetic start")
        review_assignment(
            ident, 2, "completed", "Owner confirms fictional worker progress"
        )
        self.assertEqual(employees()[0]["allocated_hours"], 0)
        with get_connection() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT status FROM agile_tasks WHERE id=?", (task,)
                ).fetchone()[0],
                "ready",
            )
            self.assertEqual(
                conn.execute(
                    "SELECT status FROM action_queue WHERE id=?", (self.action,)
                ).fetchone()[0],
                "pending",
            )
        with self.assertRaises(ValueError):
            review_assignment(ident, 3, "in_progress", "Cannot replay terminal work")
        update_employee(
            employee, 2, department_id=1, capacity_hours=10, status="retired"
        )
        with self.assertRaises(ValueError):
            update_employee(
                employee, 3, department_id=1, capacity_hours=10, status="active"
            )

    def test_department_and_employee_stale_updates_and_archival_gates(self):
        employee = self.employee()
        d = departments()[0]
        with self.assertRaises(ValueError):
            update_department(
                d["id"],
                1,
                name=d["name"],
                executive_key=d["executive_key"],
                floor=d["floor"],
                status="archived",
            )
        with self.assertRaises(RuntimeError):
            update_employee(
                employee, 1, department_id=d["id"], capacity_hours=10, status="active"
            )
        update_employee(
            employee, 2, department_id=d["id"], capacity_hours=10, status="retired"
        )
        update_department(
            d["id"],
            1,
            name=d["name"],
            executive_key=d["executive_key"],
            floor=d["floor"],
            status="archived",
        )
        with self.assertRaises(ValueError):
            create_employee(
                creation_key="archived",
                name="Adult test",
                job_title="Assistant",
                department_id=d["id"],
                capacity_hours=2,
            )

    def test_personal_events_are_disabled_by_default_and_isolated_from_business(self):
        self.assertFalse(settings()["enabled"])
        with self.assertRaises(ValueError):
            self.event("disabled", "friendship")
        self.enable()
        before = get_company_activity(100)
        with get_connection() as conn:
            counts = {
                table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "decisions",
                    "action_queue",
                    "treasury_entries",
                    "executive_memories",
                    "evidence_sources",
                )
            }  # nosec B608 # Literal table tuple.
        self.event("friends", "friendship")
        self.event("dating", "dating", version=1)
        self.event("marriage", "marriage", version=2)
        self.assertEqual(get_company_activity(100), before)
        with get_connection() as conn:
            for table, total in counts.items():
                self.assertEqual(
                    conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], total
                )  # nosec B608 # Fixed table keys.
        self.assertEqual(get_executive_memories("ceo"), [])
        self.assertEqual(
            relationship("executive:ceo", "executive:cfo")["state"], "married"
        )

    def test_relationship_state_history_idempotence_and_invalid_divorce(self):
        self.enable()
        time = stamp()
        first = record_personal_event(
            event_key="dating",
            kind="dating",
            character_key="executive:ceo",
            partner_key="executive:cfo",
            narrative="Fictional dating",
            simulated_at=time,
        )
        again = record_personal_event(
            event_key="dating",
            kind="dating",
            character_key="executive:ceo",
            partner_key="executive:cfo",
            narrative="Fictional dating",
            simulated_at=time,
        )
        self.assertEqual(first, again)
        with self.assertRaises(ValueError):
            self.event("invalid-divorce", "divorce", version=1)
        self.event("marry", "marriage", version=1)
        self.event("separate", "separation", version=2)
        self.event("divorce", "divorce", version=3)
        self.assertEqual(
            relationship("executive:cfo", "executive:ceo")["state"], "divorced"
        )
        self.assertEqual(len(events()), 4)
        with get_connection() as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE personal_events SET fictional=0")

    def test_social_stale_version_marriage_exclusivity_and_chronology(self):
        self.enable()
        self.event("date-a", "dating")
        self.event("date-b", "dating", right="executive:cso")
        self.event("marry-a", "marriage", version=1)
        with self.assertRaises(ValueError):
            self.event("marry-b", "marriage", right="executive:cso", version=1)
        with self.assertRaises(RuntimeError):
            self.event("stale", "divorce", version=1)
        with self.assertRaises(ValueError):
            record_personal_event(
                event_key="past",
                kind="divorce",
                character_key="executive:ceo",
                partner_key="executive:cfo",
                expected_relationship_version=2,
                narrative="Fictional backdated divorce",
                simulated_at="2020-01-01T00:00:00Z",
            )
        with self.assertRaises(ValueError):
            self.event("self", "dating", right="executive:ceo")
        with self.assertRaises(LookupError):
            self.event("missing", "dating", right="real-person:someone")

    def test_retired_employee_cannot_receive_new_personal_events(self):
        employee = self.employee()
        self.enable()
        update_employee(
            employee, 2, department_id=1, capacity_hours=10, status="retired"
        )
        with self.assertRaises(ValueError):
            record_personal_event(
                event_key="retired",
                kind="hobby",
                character_key=f"employee:{employee}",
                narrative="Fictional hobby",
                simulated_at=stamp(),
            )

    def test_office_roster_uses_latest_profile_and_bounds_floor(self):
        from memory.organization import office_roster

        ident = self.employee()
        key = f"employee:{ident}"
        profile = get_character(key)
        profile["voice"]["rate"] = 1.1
        save_character(key, 1, profile["appearance"], profile["body"], profile["voice"])
        roster = office_roster(floor="03")
        self.assertEqual(roster[0]["presentation"]["version"], 2)
        self.assertEqual(roster[0]["status"], "active")
        self.assertEqual(office_roster(floor="01"), [])
        with self.assertRaises(ValueError):
            office_roster(floor="03' OR 1=1--")

    def test_concurrent_marriage_cannot_give_one_character_two_spouses(self):
        self.enable()
        self.event("date-one", "dating")
        self.event("date-two", "dating", right="executive:cso")
        barrier = threading.Barrier(2)

        def marry(partner):
            barrier.wait()
            try:
                self.event("marry-" + partner, "marriage", right=partner, version=1)
                return True
            except ValueError:
                return False

        with ThreadPoolExecutor(2) as workers:
            self.assertEqual(
                sum(workers.map(marry, ["executive:cfo", "executive:cso"])), 1
            )
        self.assertEqual(
            sum(
                relationship("executive:ceo", key)["state"] == "married"
                for key in ["executive:cfo", "executive:cso"]
            ),
            1,
        )

    def test_owner_api_strict_schema_and_no_remote_voice_or_simulation_evidence(self):
        from fastapi.testclient import TestClient
        from main import app
        from config import config

        client = TestClient(app)
        headers = {"X-API-Key": config.API_SECRET_KEY}
        for path in [
            "/characters/executive:ceo",
            "/organization/departments",
            "/organization/employees",
            "/simulation/settings",
            "/simulation/events",
        ]:
            self.assertEqual(client.get(path).status_code, 401)
        presentation = get_character("executive:ceo")
        payload = {k: presentation[k] for k in ("appearance", "body", "voice")}
        payload["expected_version"] = 1
        payload["voice"]["provider"] = "remote"
        self.assertEqual(
            client.put(
                "/characters/executive:ceo", headers=headers, json=payload
            ).status_code,
            422,
        )
        self.assertEqual(
            client.post(
                "/organization/employees",
                headers=headers,
                json=dict(
                    creation_key="minor",
                    name="Synthetic",
                    job_title="Assistant",
                    department_id=1,
                    capacity_hours=2,
                    adult=False,
                ),
            ).status_code,
            422,
        )
        self.assertEqual(
            client.get("/simulation/events?limit=101", headers=headers).status_code, 422
        )
        self.assertEqual(
            client.post(
                "/evidence",
                headers=headers,
                json=dict(
                    source_key="fiction",
                    title="Synthetic",
                    reference="simulation",
                    summary="Fictional only",
                    observed_at=stamp(),
                    source_kind="personal_event",
                ),
            ).status_code,
            422,
        )

        self.assertEqual(
            client.get(
                "/organization/office-roster?offset=999999999999999999999999999999",
                headers=headers,
            ).status_code,
            422,
        )
        self.assertEqual(
            client.post(
                "/organization/assignments",
                headers=headers,
                json=dict(employee_id=2**80, task_id=1, hours=1),
            ).status_code,
            422,
        )
        self.assertEqual(
            client.put(
                "/organization/employees/" + str(2**80),
                headers=headers,
                json=dict(
                    expected_version=1,
                    department_id=1,
                    capacity_hours=8,
                    status="active",
                ),
            ).status_code,
            422,
        )
