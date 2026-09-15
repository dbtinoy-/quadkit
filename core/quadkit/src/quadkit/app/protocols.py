"""Protocols for the app subsystem.

Defines :class:`AppLifecycleProtocol` for application start/stop hooks.
"""

from __future__ import annotations

from typing import Protocol


class AppLifecycleProtocol(Protocol):
    """Protocol for objects that manage an application lifecycle."""

    async def start(self) -> None:
        """Start the application and all registered providers."""
        ...

    async def stop(self) -> None:
        """Stop the application and release all resources."""
        ...


__all__ = ["AppLifecycleProtocol"]
