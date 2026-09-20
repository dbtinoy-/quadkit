"""Unit tests for AbstractSSEHandler max_connections cap (M47)."""

from __future__ import annotations

import pytest

from quadkit.web.exceptions import TooManyConnectionsError
from quadkit.web.sse.handler import AbstractSSEHandler


# ---------------------------------------------------------------------------
# Concrete handler stub
# ---------------------------------------------------------------------------


class _NoopRequest:
    """Minimal request stub."""


class _BasicSSEHandler(AbstractSSEHandler):
    """Concrete AbstractSSEHandler with a trivial stream."""

    async def stream(self, request):  # type: ignore[override]
        yield {"event": "ping", "data": "ok"}


class _LimitedSSEHandler(_BasicSSEHandler):
    """AbstractSSEHandler with a max_connections cap of 2."""

    max_connections = 2


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSSEHandlerMaxConnections:
    """AbstractSSEHandler enforces the max_connections class variable."""

    def setup_method(self) -> None:
        # Reset per-test to avoid cross-test contamination
        _LimitedSSEHandler._active_connections = 0

    # -- no limit configured (0 = unlimited) --

    @pytest.mark.asyncio
    async def test_unlimited_handler_does_not_raise(self) -> None:
        handler = _BasicSSEHandler()
        request = _NoopRequest()

        # Should return an EventSourceResponse without raising
        response = await handler.handle(request)  # type: ignore[arg-type]
        assert response is not None

    # -- limit=2 --

    @pytest.mark.asyncio
    async def test_first_connection_is_accepted(self) -> None:
        handler = _LimitedSSEHandler()
        await handler.handle(_NoopRequest())  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_connection_at_limit_raises_too_many_connections(self) -> None:
        _LimitedSSEHandler._active_connections = 2

        handler = _LimitedSSEHandler()
        with pytest.raises(TooManyConnectionsError):
            await handler.handle(_NoopRequest())  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_active_connections_incremented_on_handle(self) -> None:
        assert _LimitedSSEHandler._active_connections == 0
        handler = _LimitedSSEHandler()
        await handler.handle(_NoopRequest())  # type: ignore[arg-type]
        # The counter is incremented before streaming and decremented when the
        # generator is exhausted; after handle() returns the response object
        # the counter is still 1 (stream not yet consumed).
        assert _LimitedSSEHandler._active_connections == 1

    @pytest.mark.asyncio
    async def test_active_connections_decremented_after_stream_consumed(self) -> None:
        handler = _LimitedSSEHandler()
        response = await handler.handle(_NoopRequest())  # type: ignore[arg-type]
        assert _LimitedSSEHandler._active_connections == 1

        # Exhaust the generator
        async for _ in response.body_iterator:  # type: ignore[attr-defined]
            pass

        assert _LimitedSSEHandler._active_connections == 0

    # -- TooManyConnectionsError --

    def test_too_many_connections_error_has_503_status(self) -> None:
        error = TooManyConnectionsError()
        assert error.status_code == 503

    def test_too_many_connections_error_code(self) -> None:
        error = TooManyConnectionsError()
        assert error.code == "TOO_MANY_CONNECTIONS"

    def test_too_many_connections_error_custom_detail(self) -> None:
        error = TooManyConnectionsError(detail="custom message")
        assert "custom message" in str(error.detail)
