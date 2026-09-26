"""Tests for the token_refresh_rate admin widget handler."""

from __future__ import annotations

from quadkit.auth.admin.handlers.token_refresh_rate import (
    TokenRefreshRateWidgetHandler,
)
from quadkit.auth.services.activity_tracker import AuthActivityTracker
from quadkit.contracts.admin import StatContent, Tone, WidgetParams
from quadkit.result import Ok


async def test_token_refresh_rate_reports_real_rate() -> None:
    tracker = AuthActivityTracker()
    for _ in range(3):
        tracker.record_refresh()
    result = await TokenRefreshRateWidgetHandler(tracker=tracker).get_data(
        WidgetParams(time_window_minutes=60)
    )
    assert isinstance(result, Ok)
    values = [s.value for s in result.unwrap().stats]
    assert "3" in values
    assert "0.0" not in values


async def test_token_refresh_rate_handler_returns_stat_content() -> None:
    result = await TokenRefreshRateWidgetHandler(
        tracker=AuthActivityTracker()
    ).get_data(WidgetParams())
    content = result.unwrap()
    assert isinstance(content, StatContent)


async def test_token_refresh_rate_stats_mirror_template() -> None:
    result = await TokenRefreshRateWidgetHandler(
        tracker=AuthActivityTracker()
    ).get_data(WidgetParams())
    content = result.unwrap()
    rate = content.stats[0]
    assert rate.label == "Refresh Rate (per minute)"
    assert rate.value == "0.0"
    assert rate.tone is Tone.DEFAULT


async def test_token_refresh_rate_no_total_stat_when_zero() -> None:
    result = await TokenRefreshRateWidgetHandler(
        tracker=AuthActivityTracker()
    ).get_data(WidgetParams())
    content = result.unwrap()
    assert len(content.stats) == 1


async def test_token_refresh_rate_uses_static_tone_no_threshold_ladder() -> None:
    result = await TokenRefreshRateWidgetHandler(
        tracker=AuthActivityTracker()
    ).get_data(WidgetParams())
    content = result.unwrap()
    assert all(stat.tone is Tone.DEFAULT for stat in content.stats)


__all__ = [
    "test_token_refresh_rate_handler_returns_stat_content",
    "test_token_refresh_rate_no_total_stat_when_zero",
    "test_token_refresh_rate_reports_real_rate",
    "test_token_refresh_rate_stats_mirror_template",
    "test_token_refresh_rate_uses_static_tone_no_threshold_ladder",
]