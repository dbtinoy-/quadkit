"""Context management for Quadkit Framework.

Provides :class:`ContextKey`, :class:`ContextVarRegistry`,
:class:`Context`, :class:`RequestContext`, and factory functions
for composition-root wiring.  Built on ``contextvars`` — nothing
is created or registered at import time.
"""

from __future__ import annotations

from contextlib import contextmanager
import contextvars
import time
from typing import TYPE_CHECKING, Any, Self, TypeVar

from quadkit.contracts.core.trace_context import (
    new_span_id,
    new_trace_id,
    span_id_var,
    trace_flags_var,
    trace_id_var,
)
from quadkit.primitives.context_keys import (
    CAUSATION_ID as CAUSATION_ID,
)
from quadkit.primitives.context_keys import (
    CORRELATION_ID as CORRELATION_ID,
)
from quadkit.primitives.context_keys import (
    DEFAULT_KEYS as DEFAULT_KEYS,
)
from quadkit.primitives.context_keys import (
    REQUEST_ID as REQUEST_ID,
)
from quadkit.primitives.context_keys import (
    REQUEST_METHOD as REQUEST_METHOD,
)
from quadkit.primitives.context_keys import (
    REQUEST_PATH as REQUEST_PATH,
)
from quadkit.primitives.context_keys import (
    REQUEST_START_TIME as REQUEST_START_TIME,
)
from quadkit.primitives.context_keys import (
    SPAN_ID as SPAN_ID,
)
from quadkit.primitives.context_keys import (
    TENANT_ID as TENANT_ID,
)
from quadkit.primitives.context_keys import (
    TRACE_FLAGS as TRACE_FLAGS,
)
from quadkit.primitives.context_keys import (
    TRACE_ID as TRACE_ID,
)
from quadkit.primitives.context_keys import (
    USER_ID as USER_ID,
)
from quadkit.primitives.context_keys import (
    ContextKey as ContextKey,
)
from quadkit.primitives.context_registry import (
    ContextVarRegistry as ContextVarRegistry,
)

if TYPE_CHECKING:
    from collections.abc import Generator
    import types

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Context  (user-facing typed wrapper — receives its registry via __init__)
# ---------------------------------------------------------------------------


class Context:
    """User-facing typed wrapper around an injected ``ContextVarRegistry``."""

    def __init__(self, registry: ContextVarRegistry) -> None:
        self._registry = registry

    @property
    def registry(self) -> ContextVarRegistry:
        """The underlying registry (for advanced use / wiring)."""
        return self._registry

    # -- typed operations --------------------------------------------------

    def get(self, key: ContextKey[T], default: T | None = None) -> T | None:
        """Get the current value for a typed key."""
        return self._registry.get_typed(key, default)

    def set(self, key: ContextKey[T], value: T) -> contextvars.Token[T | None]:
        """Set a typed value, returning a reset token."""
        return self._registry.set_typed(key, value)

    def reset(
        self,
        key: ContextKey[T],
        token: contextvars.Token[T | None],
    ) -> None:
        """Reset a typed value using a token from ``set``."""
        self._registry.reset_typed(key, token)

    # -- dynamic (string-keyed) operations ---------------------------------

    def register_key(self, key: ContextKey[Any]) -> None:
        """Register a new context key at runtime."""
        self._registry.register_key(key)

    def get_dynamic(self, key: str, default: Any = None) -> Any:
        """Get a value by string key."""
        return self._registry.get_value(key, default)

    def set_dynamic(self, key: str, value: Any) -> contextvars.Token[Any]:
        """Set a value by string key."""
        return self._registry.set_value(key, value)

    def reset_dynamic(self, key: str, token: contextvars.Token[Any]) -> None:
        """Reset a value by string key."""
        self._registry.reset_value(key, token)

    # -- introspection -----------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Snapshot of all non-``None`` context values."""
        return self._registry.snapshot()

    def has(self, key: str) -> bool:
        """Check whether a context key is registered."""
        return self._registry.has(key)


# ---------------------------------------------------------------------------
# RequestContext  (scoped context manager — fully injected)
# ---------------------------------------------------------------------------


class RequestContext:
    """Context manager that sets request-scoped variables and restores them on exit."""

    request_id: str | None
    method: str | None
    path: str | None
    correlation_id: str | None
    causation_id: str | None
    user_id: str | None
    tenant_id: str | None
    start_time: float | None
    trace_id: str | None
    span_id: str | None
    trace_flags: str

    def __init__(
        self,
        registry: ContextVarRegistry,
        *,
        request_id: str | None = None,
        method: str | None = None,
        path: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        user_id: str | None = None,
        tenant_id: str | None = None,
        start_time: float | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
        trace_flags: str | None = None,
    ) -> None:
        self._registry = registry
        self.request_id = request_id
        self.method = method
        self.path = path
        self.correlation_id = correlation_id
        self.causation_id = causation_id
        self.user_id = user_id if user_id is not None else registry.get_typed(USER_ID)
        self.tenant_id = (
            tenant_id if tenant_id is not None else registry.get_typed(TENANT_ID)
        )
        self.start_time = (
            start_time
            if start_time is not None
            else time.time()
            if request_id
            else registry.get_typed(REQUEST_START_TIME)
        )
        self._tokens: list[tuple[ContextKey[Any], contextvars.Token[Any]]] = []

        self.trace_id = (
            trace_id if trace_id is not None else registry.get_typed(TRACE_ID)
        )
        if span_id is not None:
            self.span_id = span_id
        elif request_id is None:
            self.span_id = registry.get_typed(SPAN_ID)
        else:
            self.span_id = None
        self.trace_flags = (
            trace_flags
            if trace_flags is not None
            else registry.get_typed(TRACE_FLAGS) or "01"
        )

    def __enter__(self) -> Self:
        if not self.trace_id:
            self.trace_id = new_trace_id()
        if not self.span_id and self.request_id:
            self.span_id = new_span_id()

        entries: list[tuple[ContextKey[Any], Any]] = []
        if self.request_id is not None:
            entries.append((REQUEST_ID, self.request_id))
        if self.start_time is not None:
            entries.append((REQUEST_START_TIME, self.start_time))
        if self.method is not None:
            entries.append((REQUEST_METHOD, self.method))
        if self.path is not None:
            entries.append((REQUEST_PATH, self.path))
        if self.trace_id:
            entries.append((TRACE_ID, self.trace_id))
        if self.span_id:
            entries.append((SPAN_ID, self.span_id))
        if self.trace_flags:
            entries.append((TRACE_FLAGS, self.trace_flags))
        if self.correlation_id is not None:
            entries.append((CORRELATION_ID, self.correlation_id))
        if self.causation_id is not None:
            entries.append((CAUSATION_ID, self.causation_id))
        if self.user_id is not None:
            entries.append((USER_ID, self.user_id))
        if self.tenant_id is not None:
            entries.append((TENANT_ID, self.tenant_id))

        for key, val in entries:
            token = self._registry.set_typed(key, val)
            self._tokens.append((key, token))

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        for key, token in reversed(self._tokens):
            self._registry.reset_typed(key, token)
        self._tokens.clear()


# ---------------------------------------------------------------------------
# Factory functions  (call these in your composition root)
# ---------------------------------------------------------------------------


def create_context_registry(
    keys: tuple[ContextKey[Any], ...] = DEFAULT_KEYS,
    *,
    external_vars: dict[str, contextvars.ContextVar[Any]] | None = None,
) -> ContextVarRegistry:
    """Create and populate a ``ContextVarRegistry``.

    Args:
        keys: Context keys to register (defaults to ``DEFAULT_KEYS``).
        external_vars: Externally-owned ``ContextVar`` instances keyed by
            name.  Matching keys in *keys* are skipped.
    """
    external_names = set(external_vars) if external_vars else set()

    registry = ContextVarRegistry()

    for key in keys:
        if key.name not in external_names:
            registry.register_key(key)

    if external_vars:
        for name, var in external_vars.items():
            registry.register(name, var)

    return registry


def create_default_context() -> Context:
    """Create a ``Context`` wired with default keys and trace vars."""
    registry = create_context_registry(
        external_vars={
            "trace_id": trace_id_var,
            "span_id": span_id_var,
            "trace_flags": trace_flags_var,
        },
    )
    return Context(registry)


# ---------------------------------------------------------------------------
# Standalone helper functions
# ---------------------------------------------------------------------------


@contextmanager
def request_scope(
    registry: ContextVarRegistry,
    *,
    request_id: str | None = None,
    method: str | None = None,
    path: str | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    user_id: str | None = None,
    tenant_id: str | None = None,
) -> Generator[RequestContext, None, None]:
    """Functional context manager for request-scoped context::

    with request_scope(registry, request_id="abc") as req_ctx:
        ...
    """
    ctx = RequestContext(
        registry,
        request_id=request_id,
        method=method,
        path=path,
        correlation_id=correlation_id,
        causation_id=causation_id,
        user_id=user_id,
        tenant_id=tenant_id,
    )
    with ctx:
        yield ctx


def get_request_context(registry: ContextVarRegistry) -> RequestContext | None:
    """Return a snapshot of the active request context, or ``None`` if none is active.

    Reads the current context-variable values for the standard request fields.
    Returns ``None`` when no request scope is active (i.e., ``request_id`` is not set).

    Args:
        registry: The ``ContextVarRegistry`` managing request-scoped vars.

    Returns:
        A ``RequestContext`` snapshot, or ``None`` when outside a request scope.
    """
    request_id = registry.get_typed(REQUEST_ID)
    if request_id is None:
        return None
    return RequestContext(
        registry,
        request_id=request_id,
        method=registry.get_typed(REQUEST_METHOD),
        path=registry.get_typed(REQUEST_PATH),
        correlation_id=registry.get_typed(CORRELATION_ID),
        causation_id=registry.get_typed(CAUSATION_ID),
        user_id=registry.get_typed(USER_ID),
        tenant_id=registry.get_typed(TENANT_ID),
        start_time=registry.get_typed(REQUEST_START_TIME),
        trace_id=registry.get_typed(TRACE_ID),
        span_id=registry.get_typed(SPAN_ID),
        trace_flags=registry.get_typed(TRACE_FLAGS),
    )


def propagate_context() -> contextvars.Context:
    """Capture the current ``contextvars`` state for propagation.

    Call this on the originating task/coroutine, then pass the returned
    ``Context`` to :func:`with_context` on the receiving task to ensure
    trace IDs, request IDs, and other context vars are forwarded.

    Returns:
        A snapshot of all current ``ContextVar`` values.
    """
    return contextvars.copy_context()


@contextmanager
def with_context(
    context: contextvars.Context,
) -> Generator[None, None, None]:
    """Run the enclosed block with all vars from *context* set.

    Typically used with :func:`propagate_context` to forward context to a
    background task or thread::

        ctx = propagate_context()
        async def worker() -> None:
            with with_context(ctx):
                # trace IDs and request vars are available here
                ...

    Args:
        context: A context snapshot from :func:`propagate_context`.
    """
    tokens: list[tuple[contextvars.ContextVar[Any], contextvars.Token[Any]]] = []
    try:
        for var in context:
            token = var.set(context[var])
            tokens.append((var, token))
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    # Keys (pure data)
    "CAUSATION_ID",
    "CORRELATION_ID",
    "DEFAULT_KEYS",
    "REQUEST_ID",
    "REQUEST_METHOD",
    "REQUEST_PATH",
    "REQUEST_START_TIME",
    "SPAN_ID",
    "TENANT_ID",
    "TRACE_FLAGS",
    "TRACE_ID",
    "USER_ID",
    # Classes
    "Context",
    "ContextKey",
    "ContextVarRegistry",
    "RequestContext",
    # Factories (composition root)
    "create_context_registry",
    "create_default_context",
    # Helpers
    "get_request_context",
    "propagate_context",
    "request_scope",
    "with_context",
]
