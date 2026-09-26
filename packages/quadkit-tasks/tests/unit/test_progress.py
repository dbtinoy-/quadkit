"""Tests for task progress tracking."""

import pytest
import time

from quadkit.tasks.progress.core import (
    ProgressTracker,
    ProgressInfo,
    ProgressStore,
)


class TestProgressInfo:
    """Tests for ProgressInfo."""

    def test_create_progress_info(self):
        """Test creating progress info."""
        info = ProgressInfo(
            job_id="job-1",
            current=50,
            total=100,
            percentage=50.0,
            message="Processing...",
        )

        assert info.job_id == "job-1"
        assert info.current == 50
        assert info.total == 100
        assert info.percentage == 50.0
        assert info.message == "Processing..."

    def test_is_complete_when_complete(self):
        """Test is_complete returns True when done."""
        info = ProgressInfo(job_id="job-1", current=100, total=100)
        assert info.is_complete is True

    def test_is_complete_when_incomplete(self):
        """Test is_complete returns False when not done."""
        info = ProgressInfo(job_id="job-1", current=50, total=100)
        assert info.is_complete is False

    def test_is_complete_when_zero_total(self):
        """Test is_complete returns False when total is zero."""
        info = ProgressInfo(job_id="job-1", current=0, total=0)
        assert info.is_complete is False

    def test_is_complete_handles_current_exceeding_total(self):
        """Test is_complete when current exceeds total."""
        info = ProgressInfo(job_id="job-1", current=150, total=100)
        assert info.is_complete is True

    def test_elapsed_seconds_not_started(self):
        """Test elapsed_seconds returns 0 when not started."""
        info = ProgressInfo(job_id="job-1", started_at=0)
        assert info.elapsed_seconds == 0

    def test_elapsed_seconds_started(self):
        """Test elapsed_seconds calculates correctly."""
        start = time.monotonic() - 10
        info = ProgressInfo(job_id="job-1", started_at=start)
        assert info.elapsed_seconds >= 10


class MockProgressStore(ProgressStore):
    """In-memory store for testing."""

    def __init__(self):
        self._store: dict[str, ProgressInfo] = {}

    async def save(self, info: ProgressInfo) -> None:
        self._store[info.job_id] = info

    async def get(self, job_id: str) -> ProgressInfo | None:
        return self._store.get(job_id)

    async def delete(self, job_id: str) -> None:
        self._store.pop(job_id, None)

    async def list_active(self) -> list[ProgressInfo]:
        return [info for info in self._store.values() if not info.is_complete]


class TestProgressTracker:
    """Tests for ProgressTracker."""

    @pytest.mark.asyncio
    async def test_create_tracker(self):
        """Test creating a progress tracker."""
        store = MockProgressStore()
        tracker = ProgressTracker(job_id="job-1", store=store)

        assert tracker._info.job_id == "job-1"

    @pytest.mark.asyncio
    async def test_update_progress(self):
        """Test updating progress."""
        store = MockProgressStore()
        tracker = ProgressTracker(job_id="job-1", store=store)

        await tracker.update(50, 100, "Halfway there")

        info = tracker.info
        assert info.current == 50
        assert info.total == 100
        assert info.percentage == 50.0

    @pytest.mark.asyncio
    async def test_update_persists_to_store(self):
        """Test that updates are persisted to store."""
        store = MockProgressStore()
        tracker = ProgressTracker(job_id="job-1", store=store)

        await tracker.update(25, 100)

        saved = await store.get("job-1")
        assert saved is not None
        assert saved.current == 25

    @pytest.mark.asyncio
    async def test_update_with_message(self):
        """Test updating progress with message."""
        store = MockProgressStore()
        tracker = ProgressTracker(job_id="job-1", store=store)

        await tracker.update(25, 100, "Processing records")

        info = tracker.info
        assert info.message == "Processing records"

    @pytest.mark.asyncio
    async def test_complete_progress(self):
        """Test marking progress as complete."""
        store = MockProgressStore()
        tracker = ProgressTracker(job_id="job-1", store=store)

        await tracker.update(100, 100)
        await tracker.complete()

        assert tracker.info.is_complete is True

    @pytest.mark.asyncio
    async def test_estimated_remaining(self):
        """Test estimated remaining time calculation."""
        store = MockProgressStore()
        tracker = ProgressTracker(job_id="job-1", store=store)

        start = time.monotonic() - 10
        tracker._info.started_at = start
        await tracker.update(50, 100)

        estimated = tracker._info.estimated_remaining_seconds
        assert estimated is not None

    @pytest.mark.asyncio
    async def test_get_progress_info(self):
        """Test getting progress info."""
        store = MockProgressStore()
        tracker = ProgressTracker(job_id="job-1", store=store)

        await tracker.update(30, 100, "Working")

        info = tracker.info
        assert info.current == 30
        assert info.total == 100

    @pytest.mark.asyncio
    async def test_with_metadata(self):
        """Test progress with metadata."""
        store = MockProgressStore()
        tracker = ProgressTracker(job_id="job-1", store=store)

        await tracker.update(10, 100, batch=1)

        info = tracker.info
        assert info.metadata.get("batch") == 1
