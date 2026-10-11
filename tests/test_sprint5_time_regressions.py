"""Fixed-clock calendar and microsecond observation regressions on disposable data."""

import datetime
import unittest
from unittest.mock import patch

from tests import test_experiments as experiment_tests
from memory.database import get_connection
from memory.experiments import (
    _date,
    record_observation,
    list_observations,
    get_experiment,
)
from memory.business_evidence import publication_age

INSTANT = datetime.datetime(2026, 10, 11, 12, 0, 1, tzinfo=datetime.timezone.utc)


def record(ident, key, time, value, evidence):
    return record_observation(
        ident, idempotency_key=key, observed_at=time, value=value, evidence=evidence
    )


class Clock(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return INSTANT.astimezone(tz) if tz else INSTANT.replace(tzinfo=None)


class CalendarTests(unittest.TestCase):
    def test_worldwide_calendar_boundary_is_independent_of_clock_timezone(self):
        for hours in (-12, 0, 2, 14):
            zone = datetime.timezone(datetime.timedelta(hours=hours))
            before = datetime.datetime(
                2026, 10, 10, 9, 59, tzinfo=datetime.timezone.utc
            ).astimezone(zone)
            after = datetime.datetime(
                2026, 10, 10, 10, 0, tzinfo=datetime.timezone.utc
            ).astimezone(zone)
            with self.subTest(offset=hours):
                self.assertIsNone(publication_age("2026-10-11", before))
                self.assertEqual(publication_age("2026-10-11", after), 0)
                self.assertIsNone(publication_age("2026-10-12", after))
                self.assertEqual(publication_age("2026-10-09", after), 1)

    def test_leap_day_and_invalid_date_do_not_depend_on_today(self):
        now = datetime.datetime(2024, 3, 1, tzinfo=datetime.timezone.utc)
        self.assertEqual(publication_age("2024-02-29", now), 1)
        for value in ("2023-02-29", "not-a-date", None):
            self.assertIsNone(publication_age(value, now))

    def test_timestamp_normalization_uses_fixed_microsecond_precision(self):
        for value in ("2026-10-11T12:00:00Z", "2026-10-11T14:00:00.000+02:00"):
            self.assertEqual(_date(value, "test"), "2026-10-11T12:00:00.000000Z")
        self.assertEqual(
            _date("2026-10-11T14:00:00.1+02:00", "test"), "2026-10-11T12:00:00.100000Z"
        )
        with self.assertRaises(ValueError):
            _date("2026-10-11T12:00:00", "test")


class ObservationTimeTests(unittest.TestCase):
    setUp = experiment_tests.ExperimentTests.setUp
    tearDown = experiment_tests.ExperimentTests.tearDown
    experiment = experiment_tests.ExperimentTests.experiment
    terminal = experiment_tests.ExperimentTests.terminal

    def prepare(self, execution="2026-10-11T12:00:00+00:00"):
        plan = self.experiment()
        self.terminal()
        with get_connection() as conn:
            conn.execute(
                "UPDATE action_queue SET reviewed_at=? WHERE id=?",
                (execution, self.action),
            )
            conn.commit()
        return plan

    def legacy(self, ident):
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO experiment_observations(experiment_id,idempotency_key,observed_at,value,evidence,notes,recorded_at,measurement_mode) VALUES(?,?,?,?,?,?,?,?)",
                (
                    ident,
                    "legacy",
                    "2026-10-11T12:00:00Z",
                    1,
                    "Fictional legacy evidence",
                    "",
                    "2026-10-11T12:00:01Z",
                    "live",
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def test_fractional_latest_and_pagination_include_immutable_legacy_seconds(self):
        plan = self.prepare()
        with patch("memory.experiments.datetime.datetime", Clock):
            fractional = record(
                plan["id"],
                "fraction",
                "2026-10-11T14:00:00.000001+02:00",
                2,
                "Fictional later evidence",
            )
            legacy_id = self.legacy(plan["id"])
            self.assertEqual(
                get_experiment(plan["id"])["latest_observation"]["id"], fractional["id"]
            )
            self.assertEqual(
                list_observations(plan["id"], limit=1)[0]["id"], fractional["id"]
            )
            self.assertEqual(
                list_observations(plan["id"], limit=1, offset=1)[0]["id"], legacy_id
            )

    def test_equivalent_retry_preserves_legacy_timestamp_bytes(self):
        plan = self.prepare()
        ident = self.legacy(plan["id"])
        with patch("memory.experiments.datetime.datetime", Clock):
            retry = record(
                plan["id"],
                "legacy",
                "2026-10-11T14:00:00.000000+02:00",
                1,
                "Fictional legacy evidence",
            )
        self.assertEqual(retry["id"], ident)
        self.assertEqual(retry["observed_at"], "2026-10-11T12:00:00Z")

    def test_execution_order_keeps_microsecond_boundary_and_future_guard(self):
        plan = self.prepare("2026-10-11T12:00:00.100000+00:00")
        with patch("memory.experiments.datetime.datetime", Clock):
            with self.assertRaisesRegex(ValueError, "predates"):
                record(
                    plan["id"],
                    "before",
                    "2026-10-11T14:00:00.099999+02:00",
                    1,
                    "Fictional early measurement",
                )
            for key, time in (
                ("equal", "2026-10-11T12:00:00.100000Z"),
                ("after", "2026-10-11T12:00:00.100001Z"),
            ):
                record(plan["id"], key, time, 2, "Fictional measurement")
            with self.assertRaisesRegex(ValueError, "future"):
                record(
                    plan["id"],
                    "future",
                    "2026-10-11T12:01:02Z",
                    1,
                    "Fictional future measurement",
                )


if __name__ == "__main__":
    unittest.main()
