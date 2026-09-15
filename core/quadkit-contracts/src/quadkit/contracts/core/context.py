"""Context protocols for Quadkit Framework.

Provides protocol definitions for request-scoped context management.

For implementations, see ``quadkit.core.context``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, Self, runtime_checkable

if TYPE_CHECKING:
    import types


@runtime_checkable
class ContextProtocol(Protocol):
    """Protocol for string-keyed context variable access."""

    @classmethod
    def register_key(cls, key: str) -> None:
        """Explicitly register a new context key to prevent memory leaks."""
        ...

    @classmethod
    def set(cls, key: str, value: Any) -> Any:
        """Set a context value for a registered key."""
        ...

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Get a context value."""
        ...

    @classmethod
    def reset(cls, key: str, token: Any) -> None:
        """Reset a context value using a token from ``set()``."""
        ...

    @classmethod
    def get_all(cls) -> dict[str, Any]:
        """Snapshot of all non-None context values."""
        ...


@runtime_checkable
class RequestContextProtocol(Protocol):
    """Protocol for request-scoped context managers.

    Handles proper cleanup via tokens, even if nested.
    """

    request_id: str | None
    method: str | None
    path: str | None
    start_time: float | None
    trace_id: str | None
    span_id: str | None
    trace_flags: str | None
    correlation_id: str | None
    causation_id: str | None
    user_id: str | None
    tenant_id: str | None

    def __init__(
        self,
        request_id: str | None = None,
        method: str | None = None,
        path: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> None:
        """Initialize request context."""
        ...

    def __enter__(self) -> Self:
        """Enter the context scope."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Exit the context scope and cleanup."""
        ...


__all__ = [
    "ContextProtocol",
    "RequestContextProtocol",
]
