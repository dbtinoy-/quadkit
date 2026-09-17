"""Domain errors for the storage subsystem.

Storage exceptions shared across packages. Per the framework's
single-definition rule, exceptions referenced by more than one package
live in contracts; ``the optional provider`` re-exports them from here.
"""

from __future__ import annotations

from quadkit.contracts.exceptions import QuadkitError


class StorageError(QuadkitError):
    """Base exception for storage errors."""

    _code: str = "QK_ERR_STORE_001"


class StorageUnsupportedOperationError(StorageError):
    """Raised when the requested operation is not supported by the storage driver."""

    _code: str = "QK_ERR_STORE_003"


__all__ = ["StorageError", "StorageUnsupportedOperationError"]
