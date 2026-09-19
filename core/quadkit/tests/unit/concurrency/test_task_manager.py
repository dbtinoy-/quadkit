"""Tests for TaskManager with critical vs background task distinction."""

import asyncio
import contextlib

import pytest

from quadkit.concurrency.executors.task_manager import TaskManager


class TestTaskManager:
    """Test TaskManager functionality."""

    def setup_method(self):
        """Create a fresh TaskManager for each test."""
        self.tm = TaskManager()

    @pytest.mark.asyncio
    async def test_create_critical_task(self):
        """Test creating a critical task."""

        async def dummy_coro():
            await asyncio.sleep(0.1)
            return "critical_done"

        task = self.tm.create_critical_task(dummy_coro(), name="test_critical")

        assert task in self.tm._critical
        assert task not in self.tm._background

        # Wait for task to complete
        result = await task
        assert result == "critical_done"

        # Task should be removed from set after completion
        assert task not in self.tm._critical

    @pytest.mark.asyncio
    async def test_create_background_task(self):
        """Test creating a background task."""

        async def dummy_coro():
            await asyncio.sleep(0.1)
            return "background_done"

        task = self.tm.create_background_task(dummy_coro(), name="test_background")

        assert task in self.tm._background
        assert task not in self.tm._critical

        # Wait for task to complete
        result = await task
        assert result == "background_done"

        # Task should be removed from set after completion
        assert task not in self.tm._background

    @pytest.mark.asyncio
    async def test_shutdown_gracefully_critical_tasks_complete(self):
        """Test that critical tasks are allowed to complete during shutdown."""
        completed = []

        async def critical_task():
            await asyncio.sleep(0.1)
            completed.append("critical")

        async def background_task():
            await asyncio.sleep(0.1)
            completed.append("background")

        # Create tasks
        self.tm.create_critical_task(critical_task(), name="critical")
        self.tm.create_background_task(background_task(), name="background")

        # Shutdown with timeout longer than task duration
        await self.tm.shutdown_gracefully(
            critical_timeout=1.0,
            background_timeout=1.0,
        )

        # Both tasks should complete
        assert "critical" in completed
        assert "background" in completed

    @pytest.mark.asyncio
    async def test_shutdown_gracefully_critical_timeout(self):
        """Test that critical tasks are waited for with longer timeout."""
        completed = []

        async def slow_critical_task():
            await asyncio.sleep(0.5)  # Takes 0.5s
            completed.append("critical")

        async def fast_background_task():
            await asyncio.sleep(0.1)
            completed.append("background")

        # Create tasks
        self.tm.create_critical_task(slow_critical_task(), name="slow_critical")
        self.tm.create_background_task(
            fast_background_task(),
            name="fast_background",
        )

        # Shutdown with critical timeout shorter than task (0.2s < 0.5s)
        await self.tm.shutdown_gracefully(
            critical_timeout=0.2,
            background_timeout=1.0,
        )

        # Background task should complete, critical should timeout
        assert "background" in completed
        assert "critical" not in completed  # Critical task timed out

    @pytest.mark.asyncio
    async def test_shutdown_gracefully_background_cancelled(self):
        """Test that background tasks are cancelled after critical tasks."""
        completed = []
        cancelled = []

        async def critical_task():
            await asyncio.sleep(0.1)
            completed.append("critical")

        async def background_task():
            try:
                await asyncio.sleep(1.0)  # Long task
                completed.append("background")
            except asyncio.CancelledError:
                cancelled.append("background")
                raise

        # Create tasks
        self.tm.create_critical_task(critical_task(), name="critical")
        self.tm.create_background_task(background_task(), name="background")

        # Shutdown with very short background timeout
        await self.tm.shutdown_gracefully(
            critical_timeout=1.0,
            background_timeout=0.1,
        )

        # Critical should complete, background should be cancelled
        assert "critical" in completed
        assert "background" in cancelled

    @pytest.mark.asyncio
    async def test_get_task_counts(self):
        """Test getting task counts."""

        async def dummy():
            await asyncio.sleep(0.1)

        # Initially empty
        counts = self.tm.get_task_counts()
        assert counts == {"critical": 0, "background": 0}

        # Add tasks
        self.tm.create_critical_task(dummy(), name="c1")
        self.tm.create_critical_task(dummy(), name="c2")
        self.tm.create_background_task(dummy(), name="b1")

        counts = self.tm.get_task_counts()
        assert counts == {"critical": 2, "background": 1}

        # Wait for tasks to complete
        await asyncio.sleep(0.2)

        # Should be empty again
        counts = self.tm.get_task_counts()
        assert counts == {"critical": 0, "background": 0}

    @pytest.mark.asyncio
    async def test_get_task_by_name(self):
        """Test retrieving a task by name."""

        async def dummy():
            await asyncio.sleep(0.5)

        task = self.tm.create_critical_task(dummy(), name="find_me")

        # Should find the task
        found = self.tm.get_task("find_me")
        assert found is task

        # Should not find non-existent
        assert self.tm.get_task("nonexistent") is None

        # Cleanup
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_has_active_tasks(self):
        """Test has_active_tasks property."""
        assert not self.tm.has_active_tasks

        async def dummy():
            await asyncio.sleep(0.1)

        self.tm.create_critical_task(dummy(), name="active")
        assert self.tm.has_active_tasks

        await asyncio.sleep(0.2)
        assert not self.tm.has_active_tasks
