"""Adapters bridging plain callables to the exception-filter pipeline.

Application-level exception handler mappings — ``{ErrorType: handler}`` —
reach the router as callable objects, while route execution dispatches through
:class:`ExceptionFilterProtocol` instances.  The adapter here presents each
mapping entry as a filter so a single dispatch order governs both built-in
filters and application mappings.

The callable signature follows the Starlette convention: the handler receives
``(request, exc)`` and returns a response.  Both synchronous and asynchronous
callables are supported.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from inspect import isawaitable
from typing import Any

__all__ = ["CallbackExceptionFilter"]


class CallbackExceptionFilter:
    """Present a callable exception handler as an exception filter.

    Attributes:
        exception_type: The exception type registered for this handler.  The
            filter pipeline indexes filters by this attribute for O(1)
            exact-type dispatch and walks the raised exception's MRO to cover
            subclasses, so registering a base class catches its subclass
            hierarchy as well.
    """

    def __init__(
        self,
        exception_type: type[Exception],
        handler: Callable[[Any, Exception], Any | Coroutine[Any, Any, Any]],
    ) -> None:
        """Initialize the adapter.

        Args:
            exception_type: Exception type this handler is registered for.
            handler: Callable receiving ``(request, exc)`` and returning an
                HTTP response; may be synchronous or asynchronous.
        """
        self.exception_type = exception_type
        self._handler = handler

    def can_handle(self, exc: Exception) -> bool:
        """Check whether ``exc`` falls under the registered type."""
        return isinstance(exc, self.exception_type)

    async def handle(self, exc: Exception, request: Any) -> Any:
        """Invoke the wrapped handler, awaiting it when asynchronous."""
        result = self._handler(request, exc)
        if isawaitable(result):
            result = await result
        return result
