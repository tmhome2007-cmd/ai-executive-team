"""Disposable experiments: evidence, risk enforcement, approval binding and honest gaps."""

import datetime
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from config import config
from memory.database import (
    init_db,
    propose_action,
    approve_action_with_treasury,
    claim_action_for_execution,
    update_action_status,
    get_action_by_id,
    add_treasury_entry,
    update_action_outcome_with_treasury,
    get_connection,
    get_company_activity,
)
from memory.experiments import (
    create_experiment,
    update_experiment,
    record_observation,
    get_experiment,
    list_experiments,
    list_observations,
)


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.saved = config.DATABASE_PATH
        config.DATABASE_PATH = str(Path(self.temp.name).resolve() / "experiments.db")
        self.key = patch.object(
            config, "API_SECRET_KEY", "synthetic-experiment-test-key-1234567890"
        )
        self.key.start()
        init_db()
        self.action = propose_action(
            "CTO",
            "Synthetic trial",
            "printf synthetic",
            expected_cost_amount=5,
            currency="EUR",
        )
        self.plan = dict(
            title="Synthetic experiment",
            hypothesis="More measured requests",
            baseline_note="Synthetic source baseline",
            baseline_value=10,
            metric_name="requests",
            unit="count",
            target_value=20,
            direction="increase",
            expected_result="At least twenty observed requests",
            budget_amount=10,
            risk_limit=5,
            currency="EUR",
            observation_due_at=(
                datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(days=1)
            ).isoformat(),
        )

    def tearDown(self):
        self.key.stop()
        config.DATABASE_PATH = self.saved
        self.temp.cleanup()

    def experiment(self, **fields):
        return create_experiment(self.action, **{**self.plan, **fields})

    def terminal(self, status="executed"):
        add_treasury_entry("funding", 20, "EUR")
        approve_action_with_treasury(self.action)
        self.assertTrue(claim_action_for_execution(self.action))
        update_action_status(
            self.action, status
        )  # Synthetic state only; no executor or external effect.

    def observe(self, ident, **fields):
        return record_observation(
            ident,
            **dict(
                idempotency_key="measurement-1",
                observed_at=now(),
                value=25,
                evidence="Synthetic source: recorded request counter = 25",
                **fields,
            ),
        )

    def test_risk_gate_rejects_approval_atomically(self):
        plan = self.experiment(risk_limit=4)
        add_treasury_entry("funding", 20, "EUR")
        before = get_company_activity(100)
        with self.assertRaisesRegex(ValueError, "risk limit"):
            approve_action_with_treasury(self.action)
        self.assertEqual(get_action_by_id(self.action)["status"], "pending")
        self.assertEqual(get_company_activity(100), before)
        with get_connection() as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM treasury_reservations").fetchone()[
                    0
                ],
                0,
            )
        update_experiment(plan["id"], 1, risk_limit=5)
        approve_action_with_treasury(self.action)
        self.assertTrue(claim_action_for_execution(self.action))

    def test_plan_frozen_and_bound_to_approval_seal(self):
        plan = self.experiment()
        add_treasury_entry("funding", 20, "EUR")
        approve_action_with_treasury(self.action)
        with self.assertRaises(ValueError):
            update_experiment(plan["id"], 1, risk_limit=10)
        with get_connection() as conn:
            conn.execute(
                "UPDATE experiments SET risk_limit = 4 WHERE id = ?", (plan["id"],)
            )
            conn.commit()
        with self.assertRaisesRegex(ValueError, "integrity"):
            claim_action_for_execution(self.action)
        self.assertEqual(get_action_by_id(self.action)["status"], "pending")
        with get_connection() as conn:
            self.assertEqual(
                conn.execute("SELECT status FROM treasury_reservations").fetchone()[0],
                "released",
            )

    def test_measurement_retry_immutable_history_and_real_cost_breach(self):
        plan = self.experiment()
        self.terminal()
        payload = dict(
            idempotency_key="measurement-1",
            observed_at=now(),
            value=25,
            evidence="Synthetic counter result",
        )
        first = record_observation(plan["id"], **payload)
        before = get_company_activity(100)
        self.assertEqual(record_observation(plan["id"], **payload), first)
        self.assertEqual(get_company_activity(100), before)
        with self.assertRaises(RuntimeError):
            record_observation(plan["id"], **{**payload, "value": 30})
        update_action_outcome_with_treasury(
            self.action, actual_cost_amount=7, currency="EUR"
        )
        result = get_experiment(plan["id"])
        self.assertEqual(result["comparison"]["assessment"], "met_target")
        self.assertEqual(result["comparison"]["change_from_baseline"], 15)
        self.assertEqual(result["comparison"]["cost_assessment"], "over_limit")
        self.assertEqual(result["actual_cost_amount"], 7)
        with get_connection() as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("DELETE FROM experiment_observations")
        self.assertEqual(len(list_observations(plan["id"])), 1)

    def test_unknowns_simulations_and_observation_timing(self):
        plan = self.experiment(baseline_value=None, target_value=None)
        self.assertEqual(plan["comparison"]["assessment"], "not_live_executed")
        self.assertEqual(plan["comparison"]["cost_assessment"], "not_recorded")
        with self.assertRaisesRegex(ValueError, "terminal"):
            self.observe(plan["id"])
        self.terminal("executed_dry_run")
        self.observe(plan["id"])
        result = get_experiment(plan["id"])
        self.assertEqual(result["comparison"]["assessment"], "simulation_only")
        self.assertIsNone(result["comparison"]["change_from_baseline"])
        update_action_status(self.action, "executed")
        self.assertEqual(
            get_experiment(plan["id"])["comparison"]["assessment"], "simulation_only"
        )
        record_observation(
            plan["id"],
            idempotency_key="missing",
            observed_at=now(),
            value=None,
            evidence="Synthetic result is not measured yet",
        )
        self.assertEqual(
            get_experiment(plan["id"])["comparison"]["assessment"], "no_measurement"
        )
        record_observation(
            plan["id"],
            idempotency_key="no-target",
            observed_at=now(),
            value=25,
            evidence="Synthetic counter result",
        )
        self.assertEqual(
            get_experiment(plan["id"])["comparison"]["assessment"], "target_unknown"
        )
        with self.assertRaisesRegex(ValueError, "future"):
            record_observation(
                plan["id"],
                idempotency_key="future",
                observed_at="2999-01-01T00:00:00Z",
                evidence="Synthetic evidence",
            )
        with self.assertRaisesRegex(ValueError, "predates"):
            record_observation(
                plan["id"],
                idempotency_key="past",
                observed_at="2000-01-01T00:00:00Z",
                evidence="Synthetic evidence",
            )

    def test_validation_stale_edit_sources_and_unknown_cost(self):
        for fields in [
            dict(risk_limit=11),
            dict(baseline_value=float("nan")),
            dict(target_value=float("inf")),
            dict(hypothesis="api_key=do-not-store"),
            dict(observation_due_at="2026-10-10T12:00:00"),
        ]:
            with self.assertRaises(ValueError):
                self.experiment(**fields)
        self.assertEqual(list_experiments(), [])
        plan = self.experiment()
        update_experiment(plan["id"], 1, baseline_value=None, title="Changed plan")
        with self.assertRaises(RuntimeError):
            update_experiment(plan["id"], 1, title="Stale plan")
        with self.assertRaises(RuntimeError):
            self.experiment()
        with get_connection() as conn:
            conn.execute(
                "UPDATE action_outcomes SET expected_cost_amount = NULL WHERE action_id = ?",
                (self.action,),
            )
            conn.commit()
        with self.assertRaisesRegex(ValueError, "known expected cost"):
            approve_action_with_treasury(self.action)

    def test_authenticated_api_bounds_and_no_financial_side_effects(self):
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        payload = {**self.plan, "action_id": self.action}
        self.assertEqual(client.post("/experiments", json=payload).status_code, 401)
        headers = {"X-API-Key": config.API_SECRET_KEY}
        response = client.post("/experiments", headers=headers, json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        ident = response.json()["id"]
        self.assertEqual(
            client.post(
                "/experiments",
                headers=headers,
                json={**payload, "actual_cost_amount": 20},
            ).status_code,
            422,
        )
        self.assertEqual(
            client.get("/experiments?limit=101", headers=headers).status_code, 422
        )
        self.assertEqual(
            client.get(
                f"/experiments/{ident}/observations?offset=-1", headers=headers
            ).status_code,
            422,
        )
        self.assertEqual(
            client.get("/experiments/99999", headers=headers).status_code, 404
        )
        self.assertEqual(
            client.patch(
                f"/experiments/{ident}",
                headers=headers,
                json={"expected_version": 1, "title": "Updated plan"},
            ).status_code,
            200,
        )
        self.assertEqual(
            client.patch(
                f"/experiments/{ident}",
                headers=headers,
                json={"expected_version": 1, "title": "Stale plan"},
            ).status_code,
            409,
        )
        self.assertEqual(get_action_by_id(self.action)["status"], "pending")
        with get_connection() as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM treasury_entries").fetchone()[0], 0
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM treasury_reservations").fetchone()[
                    0
                ],
                0,
            )


if __name__ == "__main__":
    unittest.main()
