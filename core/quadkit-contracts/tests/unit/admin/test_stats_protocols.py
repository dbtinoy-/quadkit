"""Capability protocols must exist, be runtime-checkable, and be exported."""

from __future__ import annotations

from quadkit.contracts.admin import (
    CacheStatsProtocol,
    DlqStatsProtocol,
    HealthOverviewProtocol,
    MetricsReadbackProtocol,
    NamedHealthCheckProtocol,
    QueueStatsProtocol,
    SessionCountProtocol,
)


class _FakeCache:
    def get_stats(self) -> dict[str, int | float | str] | None:
        return {"hits": 1, "misses": 2, "evictions": 0, "entries": 3}


class _FakeSessions:
    def __init__(self) -> None:
        self.total = 0

    async def count_active(self, cutoff) -> int:  # noqa: ANN001
        return self.total


def test_contracts_export_capability_protocols() -> None:
    for cls in (
        SessionCountProtocol,
        CacheStatsProtocol,
        QueueStatsProtocol,
        DlqStatsProtocol,
        MetricsReadbackProtocol,
        HealthOverviewProtocol,
        NamedHealthCheckProtocol,
    ):
        assert isinstance(cls, type)
        assert getattr(cls, "_is_runtime_protocol", False)


def test_cache_stats_isinstance_structural() -> None:
    assert isinstance(_FakeCache(), CacheStatsProtocol)


async def test_session_count_isinstance_structural() -> None:
    fake = _FakeSessions()
    assert isinstance(fake, SessionCountProtocol)
    assert await fake.count_active(None) == 0  # type: ignore[arg-type]
