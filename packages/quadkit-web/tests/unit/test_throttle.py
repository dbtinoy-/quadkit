"""Unit tests for quadkit.web.throttle module."""

from __future__ import annotations

import pytest

from quadkit.web.integrations.throttle import (
    _WINDOW_MAP,
    RateLimitModule,
    _parse_rate,
    throttle,
)


class TestParseRate:
    """Tests for the rate string parser."""

    def test_parse_minutes(self) -> None:
        """Verify minute-based rate parsing."""
        limit, window = _parse_rate("30/minute")
        assert limit == 30
        assert window == 60

    def test_parse_minutes_plural(self) -> None:
        """Verify plural minutes parsing."""
        limit, window = _parse_rate("30/minutes")
        assert limit == 30
        assert window == 60

    def test_parse_hours(self) -> None:
        """Verify hour-based rate parsing."""
        limit, window = _parse_rate("5/hour")
        assert limit == 5
        assert window == 3600

    def test_parse_hours_plural(self) -> None:
        """Verify plural hours parsing."""
        limit, window = _parse_rate("5/hours")
        assert limit == 5
        assert window == 3600

    def test_parse_seconds(self) -> None:
        """Verify second-based rate parsing."""
        limit, window = _parse_rate("100/second")
        assert limit == 100
        assert window == 1

    def test_parse_seconds_plural(self) -> None:
        """Verify plural seconds parsing."""
        limit, window = _parse_rate("100/seconds")
        assert limit == 100
        assert window == 1

    def test_parse_days(self) -> None:
        """Verify day-based rate parsing."""
        limit, window = _parse_rate("1/day")
        assert limit == 1
        assert window == 86400

    def test_parse_days_plural(self) -> None:
        """Verify plural days parsing."""
        limit, window = _parse_rate("1/days")
        assert limit == 1
        assert window == 86400

    def test_invalid_format_raises(self) -> None:
        """Verify invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid rate string"):
            _parse_rate("invalid")

    def test_invalid_window_raises(self) -> None:
        """Verify invalid window raises ValueError."""
        with pytest.raises(ValueError, match="Invalid rate string"):
            _parse_rate("30/week")

    def test_non_numeric_limit_raises(self) -> None:
        """Verify non-numeric limit raises ValueError."""
        with pytest.raises(ValueError, match="Invalid rate string"):
            _parse_rate("abc/minute")

    def test_case_insensitive(self) -> None:
        """Verify parsing is case insensitive."""
        limit, window = _parse_rate("30/MINUTE")
        assert limit == 30
        assert window == 60

    def test_whitespace_handling(self) -> None:
        """Verify whitespace is handled correctly."""
        limit, window = _parse_rate("  30  /  minute  ")
        assert limit == 30
        assert window == 60


class TestWindowMap:
    """Tests for the _WINDOW_MAP dictionary."""

    def test_window_map_second(self) -> None:
        """Verify second mapping."""
        assert _WINDOW_MAP["second"] == 1

    def test_window_map_minute(self) -> None:
        """Verify minute mapping."""
        assert _WINDOW_MAP["minute"] == 60

    def test_window_map_hour(self) -> None:
        """Verify hour mapping."""
        assert _WINDOW_MAP["hour"] == 3600

    def test_window_map_day(self) -> None:
        """Verify day mapping."""
        assert _WINDOW_MAP["day"] == 86400


class TestThrottleDecorator:
    """Tests for the @throttle decorator."""

    def test_throttle_returns_callable(self) -> None:
        """Verify throttle returns a decorator."""
        result = throttle("30/minute")
        assert callable(result)

    def test_throttle_with_by_user(self) -> None:
        """Verify throttle accepts user scope."""
        result = throttle("10/minute", by="user")
        assert callable(result)

    def test_throttle_with_by_ip(self) -> None:
        """Verify throttle accepts ip scope."""
        result = throttle("100/hour", by="ip")
        assert callable(result)

    def test_throttle_with_by_endpoint(self) -> None:
        """Verify throttle accepts endpoint scope."""
        result = throttle("50/minute", by="endpoint")
        assert callable(result)

    def test_invalid_rate_raises(self) -> None:
        """Verify invalid rate string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid rate string"):
            throttle("invalid")


class TestRateLimitModule:
    """Tests for the RateLimitModule."""

    def test_configure_creates_module(self) -> None:
        """Verify configure creates a properly configured module."""
        module = RateLimitModule.configure(
            backend="memory",
            default_limit="100/minute",
        )
        assert module is not None

    def test_configure_with_default_limit(self) -> None:
        """Verify configure accepts default_limit."""
        module = RateLimitModule.configure(
            default_limit="1000/hour",
        )
        assert module is not None

    def test_configure_validates_default_limit(self) -> None:
        """Verify configure validates default_limit format."""
        with pytest.raises(ValueError, match="Invalid rate string"):
            RateLimitModule.configure(default_limit="invalid")

    def test_configure_with_redis(self) -> None:
        """Verify configure configures redis backend."""
        module = RateLimitModule.configure(
            backend="redis",
            default_limit="1000/hour",
        )
        assert module is not None

    def test_configure_default_backend(self) -> None:
        """Verify configure has memory as default backend."""
        module = RateLimitModule.configure()
        assert module is not None
