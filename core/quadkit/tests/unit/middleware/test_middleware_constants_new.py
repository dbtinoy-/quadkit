"""Tests for middleware constants."""

from __future__ import annotations

from quadkit.middleware.constants import (
    DEFAULT_CIRCUIT_FAILURE_THRESHOLD,
    DEFAULT_CIRCUIT_RECOVERY_TIMEOUT,
    DEFAULT_CORRELATION_HEADER,
    DEFAULT_RATE_LIMIT_MAX_REQUESTS,
    DEFAULT_RATE_LIMIT_WINDOW,
    DEFAULT_RETRY_COUNT,
    DEFAULT_RETRY_DELAY,
    DEFAULT_TIMEOUT,
    ENV_NESTED_DELIMITER,
    ENV_PREFIX,
    HOOK_CIRCUIT_BREAKER_CLOSED,
    HOOK_CIRCUIT_BREAKER_OPENED,
    HOOK_MIDDLEWARE_AFTER,
    HOOK_MIDDLEWARE_BEFORE,
    HOOK_MIDDLEWARE_ERROR,
    HOOK_RATE_LIMIT_EXCEEDED,
    HOOK_TIMEOUT,
)


class TestMiddlewareConstants:
    """Tests for middleware constants."""

    def test_env_prefix(self) -> None:
        assert ENV_PREFIX == "QK_MIDDLEWARE__"

    def test_env_nested_delimiter(self) -> None:
        assert ENV_NESTED_DELIMITER == "__"

    def test_default_correlation_header(self) -> None:
        assert DEFAULT_CORRELATION_HEADER == "X-Correlation-Id"

    def test_default_retry_count(self) -> None:
        assert DEFAULT_RETRY_COUNT == 3

    def test_default_retry_delay(self) -> None:
        assert DEFAULT_RETRY_DELAY == 0.1

    def test_default_timeout(self) -> None:
        assert DEFAULT_TIMEOUT == 30.0

    def test_default_circuit_failure_threshold(self) -> None:
        assert DEFAULT_CIRCUIT_FAILURE_THRESHOLD == 5

    def test_default_circuit_recovery_timeout(self) -> None:
        assert DEFAULT_CIRCUIT_RECOVERY_TIMEOUT == 30.0

    def test_default_rate_limit_max_requests(self) -> None:
        assert DEFAULT_RATE_LIMIT_MAX_REQUESTS == 100

    def test_default_rate_limit_window(self) -> None:
        assert DEFAULT_RATE_LIMIT_WINDOW == 60.0


class TestMiddlewareHooks:
    """Tests for middleware hook constants."""

    def test_hook_middleware_before(self) -> None:
        assert HOOK_MIDDLEWARE_BEFORE == "middleware.before"

    def test_hook_middleware_after(self) -> None:
        assert HOOK_MIDDLEWARE_AFTER == "middleware.after"

    def test_hook_middleware_error(self) -> None:
        assert HOOK_MIDDLEWARE_ERROR == "middleware.error"

    def test_hook_circuit_breaker_opened(self) -> None:
        assert HOOK_CIRCUIT_BREAKER_OPENED == "middleware.circuit_breaker.opened"

    def test_hook_circuit_breaker_closed(self) -> None:
        assert HOOK_CIRCUIT_BREAKER_CLOSED == "middleware.circuit_breaker.closed"

    def test_hook_rate_limit_exceeded(self) -> None:
        assert HOOK_RATE_LIMIT_EXCEEDED == "middleware.rate_limit.exceeded"

    def test_hook_timeout(self) -> None:
        assert HOOK_TIMEOUT == "middleware.timeout"
