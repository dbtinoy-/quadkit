"""Public protocol surface for ``quadkit.storage``."""

from __future__ import annotations

from quadkit.contracts.infra.storage import BlobStoreProtocol, StorageBackendProtocol
from quadkit.storage.backends.protocols import StreamingBodyProtocol

__all__ = [
    "BlobStoreProtocol",
    "StorageBackendProtocol",
    "StreamingBodyProtocol",
]
