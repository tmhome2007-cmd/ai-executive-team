"""Verify real lifespan registration/cleanup without executing scheduled work."""

import asyncio
from contextlib import ExitStack
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from config import config


class StartupSchedulerTests(unittest.TestCase):
    def test_real_scheduler_dispatches_startup_and_delayed_jobs_and_stops(self):
        """Real scheduler/executor, stub work; accelerate only the delayed test job."""
        import datetime
        import main
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        with tempfile.TemporaryDirectory() as raw, ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    config, "DATABASE_PATH", str(Path(raw).resolve() / "test.db")
                )
            )
            for name in (
                "validate_config",
                "run_startup_checks",
                "backup_database",
                "start_telegram_listener",
                "stop_telegram_listener",
            ):
                stack.enter_context(patch.object(main, name))
            stack.enter_context(
                patch(
                    "memory.artifact_retention.prune_generated_artifacts",
                    return_value={},
                )
            )

            async def run():
                research_seen, followup_seen = asyncio.Event(), asyncio.Event()

                async def research():
                    research_seen.set()

                async def followup():
                    followup_seen.set()

                scheduler = AsyncIOScheduler()
                application = SimpleNamespace(state=SimpleNamespace())
                with (
                    patch.object(main, "AsyncIOScheduler", return_value=scheduler),
                    patch.object(main, "scheduled_research_job", side_effect=research),
                    patch.object(
                        main, "scheduled_autonomous_followup_job", side_effect=followup
                    ),
                ):
                    async with main.lifespan(application):
                        await asyncio.wait_for(research_seen.wait(), timeout=3)
                        self.assertFalse(followup_seen.is_set())
                        delayed = scheduler.get_job("autonomous_followup_interval_job")
                        now = datetime.datetime.now(delayed.next_run_time.tzinfo)
                        self.assertGreater(
                            (delayed.next_run_time - now).total_seconds(), 110
                        )
                        self.assertLessEqual(
                            (delayed.next_run_time - now).total_seconds(), 120
                        )
                        scheduler.modify_job(delayed.id, next_run_time=now)
                        await asyncio.wait_for(followup_seen.wait(), timeout=3)
                    # AsyncIOScheduler schedules shutdown on its event loop.
                    await asyncio.sleep(0)
                    self.assertFalse(scheduler.running)

            asyncio.run(run())

    def exercise(
        self, *, body_failure=False, shutdown_failure=False, startup_failure=False
    ):
        import main

        with tempfile.TemporaryDirectory() as raw, ExitStack() as stack:
            root = Path(raw).resolve()
            stack.enter_context(
                patch.object(config, "DATABASE_PATH", str(root / "history.db"))
            )
            stack.enter_context(patch.object(main, "validate_config", return_value=[]))
            stack.enter_context(patch.object(main, "run_startup_checks"))
            stack.enter_context(
                patch(
                    "memory.artifact_retention.prune_generated_artifacts",
                    return_value={},
                )
            )
            backup = stack.enter_context(
                patch.object(main, "backup_database", return_value="disposable-backup")
            )
            start_listener = stack.enter_context(
                patch.object(main, "start_telegram_listener")
            )
            if startup_failure:
                start_listener.side_effect = RuntimeError(
                    "synthetic listener startup failure"
                )
            stop_listener = stack.enter_context(
                patch.object(main, "stop_telegram_listener")
            )
            research = stack.enter_context(patch.object(main, "scheduled_research_job"))
            followup = stack.enter_context(
                patch.object(main, "scheduled_autonomous_followup_job")
            )
            scheduler = Mock()
            if shutdown_failure:
                scheduler.shutdown.side_effect = RuntimeError(
                    "synthetic shutdown failure"
                )
            stack.enter_context(
                patch.object(main, "AsyncIOScheduler", return_value=scheduler)
            )
            app = SimpleNamespace(state=SimpleNamespace())

            async def run():
                async with main.lifespan(app):
                    jobs = {
                        call.kwargs["id"]: call
                        for call in scheduler.add_job.call_args_list
                    }
                    self.assertEqual(len(jobs), 8)
                    self.assertIn(
                        "next_run_time", jobs["daily_research_interval_job"].kwargs
                    )
                    self.assertIn(
                        "next_run_time", jobs["autonomous_followup_interval_job"].kwargs
                    )
                    for name in (
                        "observation_collectors",
                        "executive_work_plans",
                        "daily_research_interval_job",
                        "autonomous_followup_interval_job",
                    ):
                        self.assertEqual(jobs[name].kwargs["max_instances"], 1)
                        self.assertTrue(jobs[name].kwargs["coalesce"])
                    research.assert_not_called()
                    followup.assert_not_called()
                    scheduler.start.assert_called_once()
                    self.assertIs(app.state.scheduler, scheduler)
                    if body_failure:
                        raise ValueError("synthetic lifespan body failure")

            if startup_failure:
                with self.assertRaisesRegex(RuntimeError, "listener startup failure"):
                    asyncio.run(run())
            elif body_failure:
                with self.assertRaisesRegex(ValueError, "lifespan body"):
                    asyncio.run(run())
            elif shutdown_failure:
                with self.assertRaisesRegex(RuntimeError, "shutdown failure"):
                    asyncio.run(run())
            else:
                asyncio.run(run())
            if startup_failure:
                backup.assert_not_called()
            else:
                backup.assert_called_once()
            scheduler.start.assert_called_once()
            start_listener.assert_called_once()
            scheduler.shutdown.assert_called_once()
            stop_listener.assert_called_once()

    def test_real_lifespan_registers_jobs_and_cleans_up_on_body_failure(self):
        self.exercise()
        self.exercise(body_failure=True)

    def test_listener_stops_even_if_scheduler_shutdown_fails(self):
        self.exercise(shutdown_failure=True)

    def test_scheduler_is_stopped_if_listener_startup_fails(self):
        self.exercise(startup_failure=True)
