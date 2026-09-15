from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from quadkit.testing.clock import FixedClock
from quadkit.contracts.core.clock import ClockProtocol, Duration
from quadkit.primitives import clock


class TestDuration:
    def test_parse_seconds(self) -> None:
        duration = Duration.parse("30s")
        assert duration.total_seconds == 30.0
        assert str(duration) == "30s"

    def test_parse_chained_units(self) -> None:
        duration = Duration.parse("1h30m")
        assert duration.total_seconds == 5400.0
        assert str(duration) == "1h30m"

    def test_arithmetic(self) -> None:
        duration = Duration.minutes(5) + Duration.seconds(30)
        assert duration == Duration.seconds(330)
        assert (duration - Duration.minutes(1)).total_seconds == 270.0

    def test_bool_and_timedelta(self) -> None:
        duration = Duration.zero()
        assert bool(duration) is False
        assert duration.to_timedelta() == timedelta(0)


class TestClockPrimitive:
    def test_now_is_utc(self) -> None:
        now = clock.now()
        assert now.tzinfo is UTC

    def test_timestamp_and_monotonic_return_floats(self) -> None:
        assert isinstance(clock.timestamp(), float)
        assert isinstance(clock.monotonic(), float)

    def test_current_returns_clock(self) -> None:
        current = clock.current()
        assert hasattr(current, 'now')
        assert hasattr(current, 'monotonic')
        assert hasattr(current, 'timestamp')


class TestFixedClock:
    def test_defaults_to_utc_start(self) -> None:
        clock = FixedClock()
        assert clock.now().tzinfo is UTC

    def test_accepts_aware_datetime(self) -> None:
        start = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
        fixed = FixedClock(start)
        assert fixed.now() == start

    def test_rejects_naive_datetime_on_set(self) -> None:
        fixed = FixedClock()
        naive = datetime(2025, 1, 1)
        with pytest.raises(ValueError, match="timezone-aware"):
            fixed.set(naive)

    def test_advance_supports_duration(self) -> None:
        fixed = FixedClock()
        fixed.advance(Duration.minutes(5))
        assert fixed.now().minute == 5

    def test_advance_supports_timedelta(self) -> None:
        fixed = FixedClock()
        fixed.advance(timedelta(hours=1))
        assert fixed.now().hour == 1

    def test_timestamp_tracks_clock(self) -> None:
        fixed = FixedClock()
        ts1 = fixed.timestamp()
        fixed.advance(1.0)
        ts2 = fixed.timestamp()
        assert ts2 > ts1


class TestClockUse:
    def test_use_overrides_temporarily(self) -> None:
        fixed = FixedClock(datetime(2026, 1, 1, tzinfo=UTC))
        with clock.use(fixed):
            assert clock.now().year == 2026

    def test_use_restores_after_block(self) -> None:
        before = clock.now()
        with clock.use(FixedClock(datetime(2030, 1, 1, tzinfo=UTC))):
            pass
        after = clock.now()
        assert before.year == after.year