"""Tests for the tasks_summary admin widget handler."""

from __future__ import annotations

import pytest

from quadkit.contracts.admin import StatContent, Tone, WidgetParams
from quadkit.result import Ok
from quadkit.tasks.admin.handlers.tasks_summary import TasksSummaryWidgetHandler


class _FakeQueue:
    """Implements TaskQueueProtocol.get_task_count."""

    def __init__(self, count: int = 0) -> None:
        self.count = count

    async def get_task_count(self) -> int:
        return self.count


class _FakePool:
    """Implements WorkerPool.get_pool_stats."""

    def __init__(self, stats: dict | None = None) -> None:
        self.stats = stats or {}

    def get_pool_stats(self) -> dict:
        return self.stats


@pytest.mark.asyncio
async def test_tasks_summary_reports_real_queue_and_pool_stats() -> None:
    handler = TasksSummaryWidgetHandler(
        queue_provider=_FakeQueue(count=25),
        pool_provider=_FakePool(
            stats={
                "active_workers": 3,
                "total_jobs_succeeded": 40,
                "total_jobs_failed": 2,
            }
        ),
    )
    result = await handler.get_data(WidgetParams(time_window_minutes=60))
    assert isinstance(result, Ok)
    values = [s.value for s in result.unwrap().stats]
    assert "25" in values
    assert "3" in values
    assert "40" in values
    assert "2" in values


@pytest.mark.asyncio
async def test_tasks_summary_handler_returns_single_stat_content() -> None:
    result = await TasksSummaryWidgetHandler().get_data(WidgetParams())
    content = result.unwrap()
    assert isinstance(content, StatContent)
    assert len(content.stats) == 4


@pytest.mark.asyncio
async def test_tasks_summary_copies_template_cells_exactly() -> None:
    result = await TasksSummaryWidgetHandler().get_data(WidgetParams())
    content = result.unwrap()
    pending, running, completed, failed = content.stats
    assert pending.label == "Pending"
    assert pending.value == "0"
    assert running.label == "Running"
    assert running.value == "0"
    assert completed.label == "Completed"
    assert completed.value == "0"
    assert failed.label == "Failed"
    assert failed.value == "0"


@pytest.mark.asyncio
async def test_tasks_summary_mirrors_per_cell_tone_classes() -> None:
    result = await TasksSummaryWidgetHandler().get_data(WidgetParams())
    content = result.unwrap()
    pending, running, completed, failed = content.stats
    assert pending.tone is Tone.DEFAULT
    assert running.tone is Tone.INFO
    assert completed.tone is Tone.SUCCESS
    assert failed.tone is Tone.DANGER


__all__ = [
    "test_tasks_summary_handler_returns_single_stat_content",
    "test_tasks_summary_copies_template_cells_exactly",
    "test_tasks_summary_mirrors_per_cell_tone_classes",
]