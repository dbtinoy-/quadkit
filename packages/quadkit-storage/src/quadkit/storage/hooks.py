"""Root hook payload surface for quadkit-storage.

Defines canonical payload dataclasses for object/blob storage hook points.
Actual hook registration and invocation use the framework's string-keyed
``HookRegistryProtocol`` action/filter APIs.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "ObjectDeletedHook",
    "ObjectStoredHook",
]


@dataclass(frozen=True, kw_only=True)
class ObjectStoredHook:
    """Payload fired when a blob object is successfully stored.

    Attributes:
        bucket: Name of the bucket or container the object was stored in.
        key: Storage key (path) of the stored object.
    """

    bucket: str
    key: str


@dataclass(frozen=True, kw_only=True)
class ObjectDeletedHook:
    """Payload fired when a blob object is deleted.

    Attributes:
        bucket: Name of the bucket or container the object was deleted from.
        key: Storage key (path) of the deleted object.
    """

    bucket: str
    key: str
