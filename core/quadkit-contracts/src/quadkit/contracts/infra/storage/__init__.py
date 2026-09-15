"""Storage protocols."""

from __future__ import annotations

from quadkit.contracts.infra.storage.exceptions import (
    StorageError,
    StorageUnsupportedOperationError,
)
from quadkit.contracts.infra.storage.kv import StorageBackendProtocol, StorageType
from quadkit.contracts.infra.storage.models import FileInfo, Uploadable, UploadOptions
from quadkit.contracts.infra.storage.protocols import (
    BlobStoreProtocol,
    StorageDriverProtocol,
    StorageProviderProtocol,
)

__all__ = [
    "BlobStoreProtocol",
    "FileInfo",
    "StorageBackendProtocol",
    "StorageDriverProtocol",
    "StorageError",
    "StorageProviderProtocol",
    "StorageType",
    "StorageUnsupportedOperationError",
    "UploadOptions",
    "Uploadable",
]
