"""Async disposable protocol for Quadkit Framework."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class AsyncDisposableProtocol(Protocol):
    """Protocol for async resource cleanup.

    Expected Behavior:
    - dispose: MUST be idempotent.
    - dispose: SHOULD NOT raise exceptions on error; log and continue cleanup.
    """

    async def dispose(self) -> None: ...


__all__ = ["AsyncDisposableProtocol"]
