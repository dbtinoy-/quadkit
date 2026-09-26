"""Tests for the hit_miss_ratio admin widget handler."""

from __future__ import annotations

from quadkit.cache.admin.handlers.hit_miss_ratio import HitMissRatioWidgetHandler
from quadkit.contracts.admin import StatContent, Tone, WidgetParams


class _FakeCache:
    """Implements CacheStatsProtocol.get_stats."""

    def __init__(self, hits: int = 0, misses: int = 0) -> None:
        self.hits = hits
        self.misses = misses

    def get_stats(self) -> dict[str, int] | None:
        return {"hits": self.hits, "misses": self.misses}


async def test_hit_miss_ratio_handler_returns_stat_content() -> None:
    result = await HitMissRatioWidgetHandler(cache=_FakeCache(100, 20)).get_data(
        WidgetParams(time_window_minutes=60)
    )
    content = result.unwrap()
    assert isinstance(content, StatContent)
    assert len(content.stats) == 3


async def test_hit_miss_ratio_rate_mirrors_real_stats() -> None:
    result = await HitMissRatioWidgetHandler(cache=_FakeCache(100, 20)).get_data(
        WidgetParams(time_window_minutes=60)
    )
    content = result.unwrap()
    rate = content.stats[0]
    assert rate.value == "83.3%"
    assert rate.tone is Tone.WARNING
    assert "60m" in rate.label


async def test_hit_miss_ratio_high_rate_is_success_tone() -> None:
    result = await HitMissRatioWidgetHandler(cache=_FakeCache(95, 5)).get_data(
        WidgetParams(time_window_minutes=60)
    )
    content = result.unwrap()
    assert content.stats[0].tone is Tone.SUCCESS


async def test_hit_miss_ratio_counts_are_carried() -> None:
    result = await HitMissRatioWidgetHandler(cache=_FakeCache(100, 20)).get_data(
        WidgetParams(time_window_minutes=60)
    )
    content = result.unwrap()
    hits, misses = content.stats[1], content.stats[2]
    assert hits.value == "100"
    assert misses.value == "20"
    assert hits.tone is Tone.DEFAULT
    assert misses.tone is Tone.DEFAULT


async def test_hit_miss_ratio_degrades_without_capability() -> None:
    result = await HitMissRatioWidgetHandler(cache=object()).get_data(
        WidgetParams(time_window_minutes=60)
    )
    content = result.unwrap()
    assert content.stats[0].value == "Unavailable"


__all__ = [
    "test_hit_miss_ratio_counts_are_carried",
    "test_hit_miss_ratio_degrades_without_capability",
    "test_hit_miss_ratio_handler_returns_stat_content",
    "test_hit_miss_ratio_high_rate_is_success_tone",
    "test_hit_miss_ratio_rate_mirrors_real_stats",
]