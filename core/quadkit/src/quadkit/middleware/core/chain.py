"""Mutable middleware builder that produces an immutable MiddlewarePipeline.

MiddlewareChain is the *mutable* counterpart to the immutable
:class:`~quadkit.app.pipeline.MiddlewarePipeline`.  Use it when
you need to build a pipeline incrementally (e.g. across multiple provider
``boot`` calls) and only freeze it once construction is complete.

Example::

    from quadkit.middleware.core.chain import MiddlewareChain
    from quadkit.middleware.builtins import LoggingMiddleware, TimingMiddleware

    chain = MiddlewareChain()
    chain.add(TimingMiddleware())
    chain.add(LoggingMiddleware())

    pipeline = chain.build()          # immutable from here on
    result = await pipeline.execute(ctx, handler)
"""

from __future__ import annotations

from typing import Any

from quadkit.app.pipeline import MiddlewarePipeline


class MiddlewareChain:
    """Mutable builder for :class:`~quadkit.app.pipeline.MiddlewarePipeline`.

    Collect middleware via :meth:`add` (fluent interface supported), then call
    :meth:`build` to produce the frozen :class:`MiddlewarePipeline` that is
    safe to share.

    The chain itself is never executed — it is only a construction helper.
    After :meth:`build` is called the chain remains mutable; further :meth:`add`
    calls extend the next :meth:`build`.
    """

    def __init__(self, middleware: list[Any] | None = None) -> None:
        """Create a chain, optionally pre-populated with middleware.

        Args:
            middleware: Initial list of middleware to seed the chain with.
        """
        self._middleware: list[Any] = list(middleware) if middleware else []

    def add(self, middleware: Any) -> MiddlewareChain:
        """Append a middleware and return *self* for chaining.

        Args:
            middleware: An ``async (context, next_handler) -> result`` callable.

        Returns:
            ``self`` so calls can be chained fluently.
        """
        self._middleware.append(middleware)
        return self

    def build(self) -> MiddlewarePipeline:
        """Produce an immutable :class:`MiddlewarePipeline` from the current state.

        The returned pipeline is a snapshot — subsequent :meth:`add` calls do
        not affect already-built pipelines.

        Returns:
            A new :class:`MiddlewarePipeline` containing all added middleware.
        """
        return MiddlewarePipeline(list(self._middleware))

    def clear(self) -> None:
        """Remove all middleware from the chain without building."""
        self._middleware.clear()

    def __len__(self) -> int:
        """Return the number of middleware currently in the chain."""
        return len(self._middleware)

    def __repr__(self) -> str:
        return f"MiddlewareChain({len(self._middleware)} middleware)"


__all__ = [
    "MiddlewareChain",
]
