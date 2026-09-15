"""Immutable, composable middleware pipeline.

The core ``MiddlewarePipeline`` has no external dependencies: it is
a pure Python chain of async callables. Extension packages (e.g.
``quadkit-middleware``) re-export this class and may augment it with
additional helpers, but the authoritative implementation lives here so
that the :class:`~quadkit.app.base.Application` root can be instantiated
without importing any extension package.

Example::

    from quadkit.app.pipeline import MiddlewarePipeline

    pipeline = (
        MiddlewarePipeline()
        .add(TimingMiddleware())
        .add(LoggingMiddleware())
    )

    result = await pipeline.execute(context, final_handler)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

_logger = get_logger(__name__)


class MiddlewarePipeline:
    """Immutable, composable middleware pipeline.

    Each middleware is an ``async (context, next_handler) -> result``
    callable.  The pipeline chains them so that each middleware's
    ``next_handler`` invokes the subsequent middleware.
    """

    __slots__ = ("_middleware",)

    def __init__(self, middleware: list[Any] | None = None) -> None:
        self._middleware: list[Any] = list(middleware) if middleware else []

    def add(self, middleware: Any) -> MiddlewarePipeline:
        """Return a new pipeline with *middleware* appended.

        Args:
            middleware: An ``async (context, next_handler) -> result`` callable.

        Returns:
            A new :class:`MiddlewarePipeline` with the middleware added.
        """
        return MiddlewarePipeline([*self._middleware, middleware])

    async def execute(
        self,
        context: Any,
        handler: Callable[..., Coroutine[Any, Any, Any]],
    ) -> Any:
        """Execute the pipeline, passing *context* through all middleware to *handler*.

        Args:
            context: The request/context object to process.
            handler: The final ``async (context) -> result`` handler at the
                end of the chain.

        Returns:
            The result from the handler (possibly transformed by middleware).

        Raises:
            Exception: Any unhandled exception from a middleware or the handler;
                logged at ERROR level before propagating.
        """
        chain: Callable[..., Coroutine[Any, Any, Any]] = handler

        for mw in reversed(self._middleware):
            _next = chain

            async def _wrap(
                ctx: Any,
                _mw: Any = mw,
                _nxt: Any = _next,
            ) -> Any:
                return await _mw(ctx, _nxt)

            chain = _wrap

        try:
            return await chain(context)
        except BaseException as exc:
            if isinstance(exc, (asyncio.CancelledError, KeyboardInterrupt, SystemExit)):
                raise
            _logger.error(
                "middleware_pipeline.unhandled_error",
                exc_type=type(exc).__name__,
                middleware_count=len(self._middleware),
            )
            raise

    def __len__(self) -> int:
        """Return the number of middleware registered in this pipeline."""
        return len(self._middleware)

    def __repr__(self) -> str:
        return f"MiddlewarePipeline({len(self._middleware)} middleware)"


__all__ = ["MiddlewarePipeline"]
