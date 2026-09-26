"""Idempotency store contract."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.core.result import Result
    from quadkit.contracts.domain.idempotency import IdempotencyRecord
    from quadkit.contracts.exceptions.idempotency import IdempotencyError


@runtime_checkable
class IdempotencyStoreProtocol(Protocol):
    """Protocol for storing and checking idempotency keys."""

    async def get(self, key: str) -> Any | None:
        """Retrieve a stored result by idempotency key.

        Args:
            key: The idempotency key.

        Returns:
            The stored result, or ``None`` when the key is not present or
            expired.  Store failures raise.

        Note:
            Implementations return the unwrapped value directly — this is the
            shape implemented by every concrete store
            (:class:`~the optional provider module`,
            :class:`~the optional provider module`,
            :class:`~the optional provider module`,
            and the multimedia in-memory store) and consumed by
            :class:`~the optional provider module`.
            The previous revision declared a ``Result`` wrapper here that no
            implementation ever returned.
        """
        ...

    async def get_record(
        self,
        key: str,
    ) -> Result[IdempotencyRecord | None, IdempotencyError]:
        """Retrieve the full idempotency record, including metadata."""
        ...

    async def set(
        self,
        key: str,
        value: Any,
        ttl: float | None = None,
    ) -> None:
        """Store a result with an optional time-to-live.

        Args:
            key: The idempotency key.
            value: The result to store.
            ttl: Time-to-live in seconds, or ``None`` for no expiry.
        """
        ...

    async def delete(self, key: str) -> None:
        """Remove an idempotency record by key."""
        ...

    async def acquire(self, key: str, ttl: int) -> bool:
        """Atomically claim an idempotency key if it is not already held.

        Args:
            key: The idempotency key to acquire.
            ttl: Time-to-live in seconds for the claimed key.

        Returns:
            ``True`` if this caller should proceed.
            ``False`` if the key is already claimed.
            Store failures raise.
        """
        ...


@runtime_checkable
class IdempotencyMiddlewareProtocol(Protocol):
    """Protocol for HTTP idempotency deduplication middleware."""

    async def process(
        self,
        headers: dict[str, str],
        handler: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Run the handler with idempotency deduplication."""
        ...

    @property
    def ttl(self) -> float:
        """Default TTL (seconds) for cached idempotency results."""
        ...


__all__ = [
    "IdempotencyMiddlewareProtocol",
    "IdempotencyStoreProtocol",
]
