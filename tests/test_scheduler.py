"""
Tests for the scheduler module.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from bbs.scheduler import Scheduler, ScheduledTask, RetentionScheduler


class TestScheduledTask:
    """Tests for ScheduledTask dataclass."""

    def test_next_run_none_without_last_run_and_no_run_on_start(self):
        """Test next_run is None when never run and run_on_start is False."""
        task = ScheduledTask(
            name="test",
            callback=AsyncMock(),
            interval_seconds=60,
            run_on_start=False,
        )
        assert task.next_run is None

    def test_next_run_immediate_with_run_on_start(self):
        """Test next_run is immediate when run_on_start is True."""
        task = ScheduledTask(
            name="test",
            callback=AsyncMock(),
            interval_seconds=60,
            run_on_start=True,
        )
        # Should be approximately now
        assert task.next_run is not None
        assert (datetime.utcnow() - task.next_run).total_seconds() < 1

    def test_next_run_after_last_run(self):
        """Test next_run is calculated from last_run."""
        last_run = datetime.utcnow() - timedelta(seconds=30)
        task = ScheduledTask(
            name="test",
            callback=AsyncMock(),
            interval_seconds=60,
            last_run=last_run,
        )
        expected = last_run + timedelta(seconds=60)
        assert abs((task.next_run - expected).total_seconds()) < 1

    def test_is_due_disabled(self):
        """Test is_due is False when task is disabled."""
        task = ScheduledTask(
            name="test",
            callback=AsyncMock(),
            interval_seconds=60,
            enabled=False,
        )
        assert not task.is_due

    def test_is_due_never_run_no_run_on_start(self):
        """Test is_due is False when never run and no run_on_start."""
        task = ScheduledTask(
            name="test",
            callback=AsyncMock(),
            interval_seconds=60,
            run_on_start=False,
        )
        assert not task.is_due

    def test_is_due_never_run_with_run_on_start(self):
        """Test is_due is True when never run but run_on_start is True."""
        task = ScheduledTask(
            name="test",
            callback=AsyncMock(),
            interval_seconds=60,
            run_on_start=True,
        )
        assert task.is_due

    def test_is_due_after_interval(self):
        """Test is_due is True when interval has passed."""
        task = ScheduledTask(
            name="test",
            callback=AsyncMock(),
            interval_seconds=60,
            last_run=datetime.utcnow() - timedelta(seconds=120),
        )
        assert task.is_due

    def test_is_due_before_interval(self):
        """Test is_due is False when interval hasn't passed."""
        task = ScheduledTask(
            name="test",
            callback=AsyncMock(),
            interval_seconds=60,
            last_run=datetime.utcnow() - timedelta(seconds=30),
        )
        assert not task.is_due


class TestScheduler:
    """Tests for the Scheduler class."""

    def test_add_task(self):
        """Test adding a task to the scheduler."""
        scheduler = Scheduler()
        callback = AsyncMock()

        task = scheduler.add_task(
            name="test_task",
            callback=callback,
            interval_seconds=300,
            run_on_start=True,
        )

        assert task.name == "test_task"
        assert task.interval_seconds == 300
        assert task.run_on_start is True
        assert len(scheduler.tasks) == 1

    def test_remove_task(self):
        """Test removing a task from the scheduler."""
        scheduler = Scheduler()
        scheduler.add_task("test", AsyncMock(), 60)

        assert scheduler.remove_task("test") is True
        assert len(scheduler.tasks) == 0

    def test_remove_nonexistent_task(self):
        """Test removing a task that doesn't exist."""
        scheduler = Scheduler()
        assert scheduler.remove_task("nonexistent") is False

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping the scheduler."""
        scheduler = Scheduler()
        scheduler._check_interval = 0.1  # Fast for testing

        await scheduler.start()
        assert scheduler._running is True

        await asyncio.sleep(0.05)

        await scheduler.stop()
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_run_task_now(self):
        """Test running a task immediately."""
        scheduler = Scheduler()
        callback = AsyncMock()
        scheduler.add_task("test", callback, 3600)

        result = await scheduler.run_task_now("test")

        assert result is True
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_task_now_nonexistent(self):
        """Test running a nonexistent task."""
        scheduler = Scheduler()
        result = await scheduler.run_task_now("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_task_callback_executed(self):
        """Test that task callback is executed when due."""
        scheduler = Scheduler()
        callback = AsyncMock()

        scheduler.add_task(
            name="test",
            callback=callback,
            interval_seconds=60,
            run_on_start=True,
        )

        await scheduler._check_tasks()

        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_task_last_run_updated(self):
        """Test that last_run is updated after task execution."""
        scheduler = Scheduler()
        callback = AsyncMock()

        task = scheduler.add_task(
            name="test",
            callback=callback,
            interval_seconds=60,
            run_on_start=True,
        )

        assert task.last_run is None

        await scheduler._run_task(task)

        assert task.last_run is not None

    @pytest.mark.asyncio
    async def test_task_failure_still_updates_last_run(self):
        """Test that last_run is updated even on task failure."""
        scheduler = Scheduler()
        callback = AsyncMock(side_effect=Exception("Test error"))

        task = scheduler.add_task(
            name="test",
            callback=callback,
            interval_seconds=60,
            run_on_start=True,
        )

        await scheduler._run_task(task)

        # Should still update last_run to prevent rapid retries
        assert task.last_run is not None

    def test_get_status(self):
        """Test getting scheduler status."""
        scheduler = Scheduler()
        scheduler.add_task("task1", AsyncMock(), 60)
        scheduler.add_task("task2", AsyncMock(), 120)

        status = scheduler.get_status()

        assert status["running"] is False
        assert len(status["tasks"]) == 2
        assert status["tasks"][0]["name"] == "task1"
        assert status["tasks"][1]["name"] == "task2"


class TestRetentionScheduler:
    """Tests for the RetentionScheduler class."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        mock_factory = MagicMock()
        retention = RetentionScheduler(
            session_factory=mock_factory,
        )

        assert retention.pm_retention_days == 30
        assert retention.log_retention_days == 90
        assert retention.interval == 24 * 60 * 60

    def test_init_with_custom_values(self):
        """Test initialization with custom values."""
        mock_factory = MagicMock()
        retention = RetentionScheduler(
            session_factory=mock_factory,
            pm_retention_days=7,
            log_retention_days=14,
            interval_seconds=3600,
        )

        assert retention.pm_retention_days == 7
        assert retention.log_retention_days == 14
        assert retention.interval == 3600

    def test_task_registered(self):
        """Test that retention cleanup task is registered."""
        mock_factory = MagicMock()
        retention = RetentionScheduler(session_factory=mock_factory)

        assert len(retention.scheduler.tasks) == 1
        assert retention.scheduler.tasks[0].name == "retention_cleanup"

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping the retention scheduler."""
        mock_factory = MagicMock()
        retention = RetentionScheduler(session_factory=mock_factory)
        retention.scheduler._check_interval = 0.1

        await retention.start()
        await asyncio.sleep(0.05)
        await retention.stop()

        # Should complete without error

    def test_get_status(self):
        """Test getting retention scheduler status."""
        mock_factory = MagicMock()
        retention = RetentionScheduler(
            session_factory=mock_factory,
            pm_retention_days=15,
            log_retention_days=30,
        )

        status = retention.get_status()

        assert status["pm_retention_days"] == 15
        assert status["log_retention_days"] == 30
        assert "tasks" in status
