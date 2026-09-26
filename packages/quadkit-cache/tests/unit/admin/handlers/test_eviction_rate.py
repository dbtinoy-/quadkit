"""Tests for the eviction_rate admin widget handler."""

from __future__ import annotations

from quadkit.cache.admin.handlers.eviction_rate import EvictionRateWidgetHandler
from quadkit.contracts.admin import StatContent, Tone, WidgetParams


class _FakeCache:
    """Implements CacheStatsProtocol.get_stats."""

    def __init__(self, evictions: int = 0) -> None:
        self.evictions = evictions

    def get_stats(self) -> dict[str, int] | None:
        return {"evictions": self.evictions}


async def test_eviction_rate_handler_returns_stat_content() -> None:
    result = await EvictionRateWidgetHandler(cache=_FakeCache(30)).get_data(
        WidgetParams()
    )
    content = result.unwrap()
    assert isinstance(content, StatContent)
    assert len(content.stats) == 2


async def test_eviction_rate_stats_mirror_real_stats() -> None:
    result = await EvictionRateWidgetHandler(cache=_FakeCache(1800)).get_data(
        WidgetParams(time_window_minutes=60)
    )
    content = result.unwrap()
    rate, total = content.stats
    assert rate.value == "0.5/s"
    assert rate.tone is Tone.DEFAULT
    assert total.value == "1800"
    assert total.tone is Tone.DEFAULT


async def test_eviction_rate_degrades_without_capability() -> None:
    result = await EvictionRateWidgetHandler(cache=object()).get_data(
        WidgetParams(time_window_minutes=60)
    )
    content = result.unwrap()
    assert content.stats[0].value == "Unavailable"


__all__ = [
    "test_eviction_rate_degrades_without_capability",
    "test_eviction_rate_handler_returns_stat_content",
    "test_eviction_rate_stats_mirror_real_stats",
]