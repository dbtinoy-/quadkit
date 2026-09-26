"""Storage exceptions - consolidated to base framework exceptions."""

from __future__ import annotations

from quadkit.contracts.exceptions import DomainError
from quadkit.contracts.infra.storage.exceptions import (
    StorageError,
    StorageUnsupportedOperationError,
)


class StorageFileNotFoundError(DomainError):
    """Raised when file is not found."""

    _code: str = "QK_ERR_STORE_002"


class TransactionError(StorageError):
    """Raised when a transaction operation fails."""

    _code: str = "QK_ERR_STORE_004"


class QuotaExceededError(StorageError):
    """Raised when a storage quota or size limit is exceeded."""

    _code: str = "QK_ERR_STORE_005"


class InvalidPathError(StorageError):
    """Raised when a path is invalid or attempts directory traversal."""

    _code: str = "QK_ERR_STORE_006"


class StorageUnavailableError(StorageError):
    """Raised when the storage backend is not reachable or unavailable."""

    _code: str = "QK_ERR_STORE_007"


class ChecksumMismatchError(StorageError):
    """Raised when a file's checksum does not match the expected value."""

    _code: str = "QK_ERR_STORE_008"


__all__ = [
    "ChecksumMismatchError",
    "InvalidPathError",
    "QuotaExceededError",
    "StorageError",
    "StorageFileNotFoundError",
    "StorageUnavailableError",
    "StorageUnsupportedOperationError",
    "TransactionError",
]
