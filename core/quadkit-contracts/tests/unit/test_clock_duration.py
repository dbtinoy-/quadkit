"""Clock contracts: Duration parsing/formatting/arithmetic, ClockProtocol."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from quadkit.contracts.core.clock import ClockProtocol, Duration


class TestDurationConstructors:
    def test_units(self) -> None:
        assert Duration.seconds(1).total_seconds == 1.0
        assert Duration.minutes(2).total_seconds == 120.0
        assert Duration.hours(1).total_seconds == 3600.0
        assert Duration.days(1).total_seconds == 86400.0
        assert Duration.zero().total_seconds == 0.0
        assert Duration.seconds(90).seconds_value == 90.0

    def test_parse_single_units(self) -> None:
        assert Duration.parse("30s") == Duration.seconds(30)
        assert Duration.parse("2m") == Duration.minutes(2)
        assert Duration.parse("1h") == Duration.hours(1)
        assert Duration.parse("1d") == Duration.days(1)
        assert Duration.parse(" 45S ") == Duration.seconds(45)  # case/whitespace

    def test_parse_chained(self) -> None:
        assert Duration.parse("1h30m") == Duration.seconds(5400)
        assert Duration.parse("1d2h3m4s") == Duration.seconds(
            86400 + 7200 + 180 + 4
        )
        assert Duration.parse("0.5s") == Duration.seconds(0.5)

    def test_parse_invalid(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            Duration.parse("   ")
        with pytest.raises(ValueError, match="Invalid duration"):
            Duration.parse("abc")
        with pytest.raises(ValueError, match="Invalid duration"):
            Duration.parse("1x")
        # partial match (trailing junk) must be rejected
        with pytest.raises(ValueError, match="Invalid duration"):
            Duration.parse("1h junk")


class TestDurationArithmetic:
    def test_add_sub_mul(self) -> None:
        a, b = Duration.minutes(1), Duration.seconds(30)
        assert a + b == Duration.seconds(90)
        assert a - b == Duration.seconds(30)
        assert Duration.seconds(10) * 3 == Duration.seconds(30)
        assert 2 * Duration.seconds(10) == Duration.seconds(20)

    def test_comparison_ordering(self) -> None:
        assert Duration.zero() < Duration.seconds(1)
        assert Duration.seconds(1) >= Duration.seconds(1)
        assert Duration.seconds(2) > Duration.seconds(1)
        assert Duration.seconds(1) <= Duration.seconds(1)
        assert Duration.zero() == Duration.seconds(0)

    def test_not_comparable_to_other_types(self) -> None:
        with pytest.raises(TypeError):
            assert Duration.seconds(1) < 1  # type: ignore[operator]
        # equality with non-Duration falls back to identity -> False, no raise
        assert Duration.seconds(1) != 1  # type: ignore[operator]

    def test_bool_and_hash(self) -> None:
        assert not bool(Duration.zero())
        assert bool(Duration.seconds(1))
        assert hash(Duration.seconds(1)) == hash(Duration.seconds(1.0))
        assert {Duration.seconds(1), Duration.minutes(1)} == {
            Duration.seconds(1),
            Duration.minutes(1),
        }

    def test_to_timedelta(self) -> None:
        assert Duration.minutes(1).to_timedelta() == timedelta(minutes=1)


class TestDurationFormatting:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (Duration.zero(), "0s"),
            (Duration.seconds(45), "45s"),
            (Duration.seconds(90), "1m30s"),
            (Duration.minutes(61), "1h1m"),
            (Duration.days(1) + Duration.hours(2), "1d2h"),
            (Duration.seconds(0.5), "0.5s"),
            (Duration.seconds(-90), "-1m30s"),
        ],
    )
    def test_str(self, value: Duration, expected: str) -> None:
        assert str(value) == expected


class TestClockProtocol:
    def test_runtime_checkable(self) -> None:
        class GoodClock:
            def now(self) -> datetime:
                return datetime.now(UTC)

            def monotonic(self) -> float:
                return 0.0

            def timestamp(self) -> float:
                return 0.0

            def time(self) -> float:
                return 0.0

        class BadClock:
            def now(self) -> datetime:
                return datetime.now(UTC)

        assert isinstance(GoodClock(), ClockProtocol)
        assert not isinstance(BadClock(), ClockProtocol)
        assert not isinstance(42, ClockProtocol)
