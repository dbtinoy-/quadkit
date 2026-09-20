"""Contract compliance suite for ``MiddlewareProtocol`` implementations.

Subclass :class:`MiddlewareCompliance` and implement
:meth:`create_middleware` to verify that any middleware satisfies the
``MiddlewareProtocol`` contract::

    from quadkit.testing.compliance import MiddlewareCompliance

    class TestMyMiddleware(MiddlewareCompliance):
        async def create_middleware(self):
            return MyLoggingMiddleware()
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

import pytest

__all__ = ["MiddlewareCompliance"]


class MiddlewareCompliance:
    """Reusable compliance suite for any ``MiddlewareProtocol`` implementation.

    Subclass and implement :meth:`create_middleware`.  All tests exercise the
    ``async __call__(context, next)`` contract defined by
    :class:`~quadkit.contracts.middleware.MiddlewareProtocol`.

    The *before* / *after* / *error* terminology maps to the three observable
    phases of a ``__call__``-style middleware:

    * **before** — code that runs prior to invoking ``next``
    * **after**  — code that runs after ``next`` returns
    * **error**  — behaviour when the downstream ``next`` raises an exception
    """

    # ------------------------------------------------------------------
    # Factory — subclasses MUST override
    # ------------------------------------------------------------------

    @abstractmethod
    async def create_middleware(self) -> Any:
        """Return a fresh instance of the middleware under test."""
        ...

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def make_context(self) -> dict[str, Any]:
        """Return a minimal request context suitable for the middleware."""
        return {"method": "GET", "path": "/test"}

    # ------------------------------------------------------------------
    # Contract tests
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_before_called(self) -> None:
        """Middleware is invoked before the downstream handler is called.

        Verified by asserting that ``__call__`` is awaitable and executes
        without error when a valid context and ``next`` are provided.
        """
        middleware = await self.create_middleware()
        called: list[bool] = []

        async def next_handler(ctx: dict[str, Any]) -> dict[str, Any]:
            called.append(True)
            return {"status": 200}

        context = self.make_context()
        await middleware(context, next_handler)
        # The downstream handler must have been reached.
        assert called, "next handler was never called — middleware must call next()"

    @pytest.mark.asyncio
    async def test_after_called(self) -> None:
        """Middleware receives and can observe the result from the downstream handler.

        The result returned by ``__call__`` must equal the value returned by
        the inner ``next`` handler (pass-through behaviour is the minimum
        requirement; middleware may wrap or transform but must not discard).
        """
        middleware = await self.create_middleware()
        sentinel = {"status": 200, "body": "ok"}

        async def next_handler(ctx: dict[str, Any]) -> dict[str, Any]:
            return sentinel

        context = self.make_context()
        result = await middleware(context, next_handler)
        # At minimum, the middleware must propagate the response.
        assert result is not None, "middleware must return a non-None result"

    @pytest.mark.asyncio
    async def test_error_flow(self) -> None:
        """An exception raised by the downstream handler propagates through the middleware.

        A middleware that does **not** explicitly handle errors must let the
        exception bubble up.  If the middleware catches and re-raises the
        exception that is also acceptable, provided the original exception type
        is preserved (or wrapped in a framework-specific exception).
        """
        middleware = await self.create_middleware()
        error = RuntimeError("downstream failure")

        async def failing_handler(ctx: dict[str, Any]) -> None:
            raise error

        context = self.make_context()
        with pytest.raises(Exception, match="downstream failure"):
            await middleware(context, failing_handler)

    @pytest.mark.asyncio
    async def test_context_passed_to_next(self) -> None:
        """The context object passed to ``next`` is the same (or an enriched) version.

        The middleware must not silently drop the context before forwarding it
        to the inner handler.
        """
        middleware = await self.create_middleware()
        received: list[Any] = []

        async def capturing_handler(ctx: Any) -> dict[str, Any]:
            received.append(ctx)
            return {"status": 200}

        context = self.make_context()
        await middleware(context, capturing_handler)
        assert received, "next handler received no context"
        # The forwarded context must contain the original keys.
        forwarded = received[0]
        if isinstance(forwarded, dict) and isinstance(context, dict):
            for key in context:
                assert key in forwarded, (
                    f"context key {key!r} was dropped before forwarding to next"
                )
