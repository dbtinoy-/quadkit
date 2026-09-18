from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TransactionalProtocol(Protocol):
    """Protocol for transactional operations."""

    async def begin_transaction(self) -> Any: ...

    async def commit_transaction(self, transaction: Any) -> None: ...

    async def rollback_transaction(self, transaction: Any) -> None: ...


__all__ = ["TransactionalProtocol"]
