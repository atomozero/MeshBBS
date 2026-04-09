"""
Background scheduler for MeshCore BBS.

Handles periodic tasks like:
- Retention policy cleanup
- Statistics updates
- Health checks

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Callable, Awaitable, List
from dataclasses import dataclass, field

logger = logging.getLogger("meshbbs.scheduler")


@dataclass
class ScheduledTask:
    """Represents a scheduled task."""

    name: str
    callback: Callable[[], Awaitable[None]]
    interval_seconds: int
    last_run: Optional[datetime] = None
    enabled: bool = True
    run_on_start: bool = False

    @property
    def next_run(self) -> Optional[datetime]:
        """Calculate next run time."""
        if self.last_run is None:
            return datetime.utcnow() if self.run_on_start else None
        return self.last_run + timedelta(seconds=self.interval_seconds)

    @property
    def is_due(self) -> bool:
        """Check if task is due to run."""
        if not self.enabled:
            return False
        if self.last_run is None:
            return self.run_on_start
        return datetime.utcnow() >= self.next_run


class Scheduler:
    """
    Async scheduler for background tasks.

    Runs tasks at specified intervals without blocking the main loop.
    """

    def __init__(self):
        self.tasks: List[ScheduledTask] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._check_interval = 60  # Check every 60 seconds

    def add_task(
        self,
        name: str,
        callback: Callable[[], Awaitable[None]],
        interval_seconds: int,
        run_on_start: bool = False,
    ) -> ScheduledTask:
        """
        Add a task to the scheduler.

        Args:
            name: Task name for logging
            callback: Async function to call
            interval_seconds: Seconds between runs
            run_on_start: Whether to run immediately on scheduler start

        Returns:
            The created ScheduledTask
        """
        task = ScheduledTask(
            name=name,
            callback=callback,
            interval_seconds=interval_seconds,
            run_on_start=run_on_start,
        )
        self.tasks.append(task)
        logger.info(f"Scheduled task '{name}' every {interval_seconds}s")
        return task

    def remove_task(self, name: str) -> bool:
        """Remove a task by name."""
        for task in self.tasks:
            if task.name == name:
                self.tasks.remove(task)
                logger.info(f"Removed task '{name}'")
                return True
        return False

    async def start(self) -> None:
        """Start the scheduler loop."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler stopped")

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                await self._check_tasks()
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Scheduler error: {e}")
                await asyncio.sleep(self._check_interval)

    async def _check_tasks(self) -> None:
        """Check and run due tasks."""
        for task in self.tasks:
            if task.is_due:
                await self._run_task(task)

    async def _run_task(self, task: ScheduledTask) -> None:
        """Run a single task."""
        logger.debug(f"Running task '{task.name}'")
        try:
            await task.callback()
            task.last_run = datetime.utcnow()
            logger.info(f"Task '{task.name}' completed successfully")
        except Exception as e:
            logger.exception(f"Task '{task.name}' failed: {e}")
            # Still update last_run to avoid rapid retries
            task.last_run = datetime.utcnow()

    async def run_task_now(self, name: str) -> bool:
        """
        Run a task immediately by name.

        Args:
            name: Task name

        Returns:
            True if task was found and run
        """
        for task in self.tasks:
            if task.name == name:
                await self._run_task(task)
                return True
        return False

    def get_status(self) -> dict:
        """Get scheduler status."""
        return {
            "running": self._running,
            "tasks": [
                {
                    "name": t.name,
                    "enabled": t.enabled,
                    "interval_seconds": t.interval_seconds,
                    "last_run": t.last_run.isoformat() if t.last_run else None,
                    "next_run": t.next_run.isoformat() if t.next_run else None,
                }
                for t in self.tasks
            ],
        }


class RetentionScheduler:
    """
    Specialized scheduler for retention cleanup tasks.

    Runs daily cleanup of old PMs and activity logs.
    """

    # Run cleanup once per day (in seconds)
    DEFAULT_INTERVAL = 24 * 60 * 60  # 24 hours

    def __init__(
        self,
        session_factory,
        pm_retention_days: int = 30,
        log_retention_days: int = 90,
        interval_seconds: int = None,
    ):
        """
        Initialize retention scheduler.

        Args:
            session_factory: SQLAlchemy session factory
            pm_retention_days: Days to keep PMs (0 = forever)
            log_retention_days: Days to keep logs (0 = forever)
            interval_seconds: Override cleanup interval
        """
        self.session_factory = session_factory
        self.pm_retention_days = pm_retention_days
        self.log_retention_days = log_retention_days
        self.interval = interval_seconds or self.DEFAULT_INTERVAL

        self.scheduler = Scheduler()
        self._setup_tasks()

    def _setup_tasks(self) -> None:
        """Setup retention cleanup task."""
        self.scheduler.add_task(
            name="retention_cleanup",
            callback=self._run_cleanup,
            interval_seconds=self.interval,
            run_on_start=False,  # Don't run immediately on start
        )

    async def _run_cleanup(self) -> None:
        """Execute retention cleanup."""
        from bbs.privacy import RetentionManager

        session = self.session_factory()
        try:
            manager = RetentionManager(session)
            pms_deleted, logs_deleted = manager.run_cleanup(
                pm_retention_days=self.pm_retention_days,
                log_retention_days=self.log_retention_days,
            )

            if pms_deleted > 0 or logs_deleted > 0:
                logger.info(
                    f"Retention cleanup: {pms_deleted} PMs, {logs_deleted} logs deleted"
                )
        finally:
            session.close()

    async def start(self) -> None:
        """Start the retention scheduler."""
        await self.scheduler.start()

    async def stop(self) -> None:
        """Stop the retention scheduler."""
        await self.scheduler.stop()

    async def run_now(self) -> None:
        """Run cleanup immediately."""
        await self.scheduler.run_task_now("retention_cleanup")

    def get_status(self) -> dict:
        """Get scheduler status with retention info."""
        status = self.scheduler.get_status()
        status["pm_retention_days"] = self.pm_retention_days
        status["log_retention_days"] = self.log_retention_days
        return status
