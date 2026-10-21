"""Quadkit Storage — Unified Storage Abstractions.

This package exposes **two distinct storage paradigms**.  Choose based on
your access patterns:

Blob / Object storage  (this package's primary API)
----------------------------------------------------
Designed for arbitrary binary objects (files, images, documents).
Operations: upload, download, delete, generate signed URLs, list objects.

Key classes:

* :class:`BlobStoreProtocol` — protocol for storage backend implementations.
* :class:`LocalDriver` — local filesystem driver (dev / CI).
* :class:`MemoryDriver` — ephemeral in-process driver (unit tests).
* :class:`S3Driver` — AWS S3 driver (requires ``boto3``).
* :class:`GCSDriver` — Google Cloud Storage driver (requires ``google-cloud-storage``).
* :class:`AzureDriver` — Azure Blob Storage driver (requires ``azure-storage-blob``).

Use blob storage when you need presigned download URLs, content-type
metadata, streaming uploads, or cloud-hosted durable file storage.

Key-Value (KV) storage  (:mod:`quadkit.storage.kv`)
------------------------------------------------------
Designed for small, string-keyed records (session data, feature flags,
ephemeral state) with optional TTL.  KV backends store values as JSON
and do **not** support binary blobs or presigned URLs.

Key classes (in :mod:`quadkit.storage.kv`):

* :class:`~quadkit.storage.kv.InMemoryKVStorage` — ephemeral dict-backed
  store (unit tests, single-node apps).
* :class:`~quadkit.storage.kv.LocalStorage` — JSON-file-backed persistent
  store (dev environments, low-volume single-node deployments).

Use KV storage when you need simple get / set / delete / TTL semantics
without the overhead of a full object storage system.

Exports (blob storage)
-----------------------
* :class:`StorageProvider` — DI provider for framework integration.
* :class:`StorageConfig` — root configuration model.
* :class:`BlobStoreProtocol` — protocol for storage backend implementations.
* :class:`FileInfo` — file metadata returned from storage operations.
* :class:`Uploadable` — type for file-like objects that can be uploaded.
* :class:`UploadOptions` — options for upload operations.
* :class:`LocalDriver`, :class:`MemoryDriver`, :class:`S3Driver`,
  :class:`GCSDriver`, :class:`AzureDriver` — concrete backend drivers.
"""

from __future__ import annotations

import importlib.metadata

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from typing import TYPE_CHECKING, Any

from quadkit.storage.constants import __version__ as __version__

if TYPE_CHECKING:
    from quadkit.contracts.infra.storage import (
        BlobStoreProtocol,
        FileInfo,
        Uploadable,
        UploadOptions,
    )
    from quadkit.storage.backends.azure import AzureDriver
    from quadkit.storage.backends.gcs import GCSDriver
    from quadkit.storage.backends.local import LocalDriver
    from quadkit.storage.backends.memory import MemoryDriver
    from quadkit.storage.backends.s3 import S3Driver
    from quadkit.storage.config import NamedStorageConfig, StorageConfig
    from quadkit.storage.di.provider import StorageProvider

_LAZY_IMPORTS = {
    # Module
    "StorageModule": "quadkit.storage.module",
    "BlobStoreProtocol": "quadkit.contracts.infra.storage",
    "FileInfo": "quadkit.contracts.infra.storage",
    "NamedStorageConfig": "quadkit.storage.config",
    "StorageConfig": "quadkit.storage.config",
    "StorageProvider": "quadkit.storage.di.provider",
    "UploadOptions": "quadkit.contracts.infra.storage",
    "Uploadable": "quadkit.contracts.infra.storage",
    "LocalDriver": "quadkit.storage.backends.local",
    "MemoryDriver": "quadkit.storage.backends.memory",
    "S3Driver": "quadkit.storage.backends.s3",
    "GCSDriver": "quadkit.storage.backends.gcs",
    "AzureDriver": "quadkit.storage.backends.azure",
    # Events
    "FileDeletedEvent": "quadkit.storage.events",
    "FileDownloadedEvent": "quadkit.storage.events",
    "FileUploadedEvent": "quadkit.storage.events",
    # Hooks
    "ObjectDeletedHook": "quadkit.storage.hooks",
    "ObjectStoredHook": "quadkit.storage.hooks",
}


def __getattr__(name: str) -> Any:
    if name == "__version__":
        return __version__
    if name in _LAZY_IMPORTS:
        import importlib

        module_path = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__} has no attribute {name}")


def __dir__() -> list[str]:
    return [*_LAZY_IMPORTS, "__version__"]


# Written out rather than derived from ``_LAZY_IMPORTS``. A computed
# ``__all__`` is invisible to a type checker: under ``no_implicit_reexport``
# every consumer of ``from quadkit.storage import LocalDriver`` is told the
# attribute is not exported, and the only workarounds available to them are
# a per-module error suppression or an import of the private backend path —
# both of which couple application code to this package's internals.
# ``test_public_api.py`` asserts this list stays equal to the lazy map, so
# the two cannot drift.
__all__ = [
    "AzureDriver",
    "BlobStoreProtocol",
    "FileDeletedEvent",
    "FileDownloadedEvent",
    "FileInfo",
    "FileUploadedEvent",
    "GCSDriver",
    "LocalDriver",
    "MemoryDriver",
    "NamedStorageConfig",
    "ObjectDeletedHook",
    "ObjectStoredHook",
    "S3Driver",
    "StorageConfig",
    "StorageModule",
    "StorageProvider",
    "UploadOptions",
    "Uploadable",
    "__version__",
]
