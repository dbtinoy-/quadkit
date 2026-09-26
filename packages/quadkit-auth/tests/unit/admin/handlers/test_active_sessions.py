"""Tests for the active_sessions admin widget handler."""

from __future__ import annotations

from quadkit.auth.admin.handlers.active_sessions import ActiveSessionsWidgetHandler
from quadkit.contracts.admin import StatContent, Tone, WidgetParams
from quadkit.result import Ok


class _FakeSessionRepo:
    """Implements SessionRepositoryProtocol + SessionCountProtocol."""

    def __init__(self, active: int = 0) -> None:
        self.active = active

    async def insert(self, payload: dict) -> None:  # noqa: ANN001
        return None

    async def find_active(self, session_id: str) -> dict | None:
        return None

    async def find_active_by_user(self, user_id: str, cutoff) -> list:  # noqa: ANN001
        return []

    async def revoke(self, session_id: str) -> None:
        return None

    async def revoke_all(self, user_id: str) -> None:
        return None

    async def update_activity(self, session_id: str, now) -> None:  # noqa: ANN001
        return None

    async def count_active(self, cutoff) -> int:  # noqa: ANN001
        return self.active


async def test_active_sessions_reports_real_count() -> None:
    handler = ActiveSessionsWidgetHandler(session_repository=_FakeSessionRepo(active=12))
    result = await handler.get_data(WidgetParams(time_window_minutes=60))
    assert isinstance(result, Ok)
    values = [s.value for s in result.unwrap().stats]
    assert "12" in values


async def test_active_sessions_degrades_without_capability() -> None:
    handler = ActiveSessionsWidgetHandler(session_repository=None)
    result = await handler.get_data(WidgetParams(time_window_minutes=60))
    assert isinstance(result, Ok)
    values = [s.value for s in result.unwrap().stats]
    assert "0" in values


async def test_active_sessions_handler_returns_stat_content() -> None:
    result = await ActiveSessionsWidgetHandler(
        session_repository=_FakeSessionRepo()
    ).get_data(WidgetParams())
    content = result.unwrap()
    assert isinstance(content, StatContent)


async def test_active_sessions_stats_mirror_template() -> None:
    result = await ActiveSessionsWidgetHandler(
        session_repository=_FakeSessionRepo()
    ).get_data(WidgetParams())
    content = result.unwrap()
    active = content.stats[0]
    assert active.label == "Currently Active"
    assert active.value == "0"
    assert active.tone is Tone.DEFAULT


async def test_active_sessions_no_peak_stat_when_zero() -> None:
    result = await ActiveSessionsWidgetHandler(
        session_repository=_FakeSessionRepo()
    ).get_data(WidgetParams())
    content = result.unwrap()
    assert len(content.stats) == 1


async def test_active_sessions_uses_static_tone_no_threshold_ladder() -> None:
    result = await ActiveSessionsWidgetHandler(
        session_repository=_FakeSessionRepo()
    ).get_data(WidgetParams())
    content = result.unwrap()
    assert all(stat.tone is Tone.DEFAULT for stat in content.stats)


__all__ = [
    "test_active_sessions_degrades_without_capability",
    "test_active_sessions_handler_returns_stat_content",
    "test_active_sessions_no_peak_stat_when_zero",
    "test_active_sessions_reports_real_count",
    "test_active_sessions_stats_mirror_template",
    "test_active_sessions_uses_static_tone_no_threshold_ladder",
]