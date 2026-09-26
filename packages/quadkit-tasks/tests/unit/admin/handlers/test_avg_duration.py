"""Tests for the avg_duration admin widget handler."""

from __future__ import annotations

import pytest

from quadkit.contracts.admin import StatContent, Tone, WidgetParams
from quadkit.result import Ok
from quadkit.tasks.admin.handlers.avg_duration import AvgDurationWidgetHandler


class _FakePool:
    """Implements WorkerPool.get_pool_stats."""

    def get_pool_stats(self) -> dict:
        return {"average_processing_time": 0.0125}  # seconds


@pytest.mark.asyncio
async def test_avg_duration_reports_real_pool_stats() -> None:
    handler = AvgDurationWidgetHandler(pool_provider=_FakePool())
    result = await handler.get_data(WidgetParams(time_window_minutes=60))
    assert isinstance(result, Ok)
    values = [s.value for s in result.unwrap().stats]
    assert any("12.5" in v for v in values)  # 0.0125s -> 12.5ms


@pytest.mark.asyncio
async def test_avg_duration_handler_returns_single_stat_content() -> None:
    result = await AvgDurationWidgetHandler().get_data(WidgetParams())
    content = result.unwrap()
    assert isinstance(content, StatContent)
    assert len(content.stats) == 2


@pytest.mark.asyncio
async def test_avg_duration_copies_template_rows_exactly() -> None:
    result = await AvgDurationWidgetHandler().get_data(WidgetParams())
    content = result.unwrap()
    avg, p95 = content.stats
    assert avg.label == "Avg"
    assert avg.value == "0.0ms"
    assert p95.label == "P95"
    assert p95.value == "0.0ms"


@pytest.mark.asyncio
async def test_avg_duration_mirrors_per_row_tone_classes() -> None:
    result = await AvgDurationWidgetHandler().get_data(WidgetParams())
    content = result.unwrap()
    avg, p95 = content.stats
    assert avg.tone is Tone.DEFAULT
    assert p95.tone is Tone.WARNING


__all__ = [
    "test_avg_duration_handler_returns_single_stat_content",
    "test_avg_duration_copies_template_rows_exactly",
    "test_avg_duration_mirrors_per_row_tone_classes",
]