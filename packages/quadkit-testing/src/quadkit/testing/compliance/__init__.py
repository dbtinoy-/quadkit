"""Contract compliance test suites for Quadkit protocol implementations.

Each suite is a base test class. Subclass it, implement the abstract factory
method, and pytest runs the contract checks::

    class TestRedisCacheCompliance(CacheBackendCompliance):
        async def create_backend(self):
            return RedisCacheBackend("redis://localhost:6379/15")

Every suite named in `__all__` is importable; the secret-store suite ships only
with the optional `the optional provider` extra, so accessing it without that extra
raises `AttributeError` instead of failing at import time.
"""

from __future__ import annotations

from typing import Any, Final

from quadkit.testing._lazy_exports import resolve_export
from quadkit.testing.compliance.audit import (
    AuditLoggerCompliance,
    AuditStoreCompliance,
)
from quadkit.testing.compliance.blob_store import BlobStoreCompliance
from quadkit.testing.compliance.cache import CacheBackendCompliance
from quadkit.testing.compliance.database import DatabaseProviderCompliance
from quadkit.testing.compliance.distributed_lock import DistributedLockCompliance
from quadkit.testing.compliance.event_bus import EventBusCompliance
from quadkit.testing.compliance.flags import FlagProviderCompliance
from quadkit.testing.compliance.middleware import MiddlewareCompliance
from quadkit.testing.compliance.notification import NotificationChannelCompliance
from quadkit.testing.compliance.queue_backend import QueueBackendCompliance
from quadkit.testing.compliance.repository import RepositoryCompliance
from quadkit.testing.compliance.search import SearchEngineCompliance
from quadkit.testing.compliance.task_queue import TaskQueueCompliance
from quadkit.testing.compliance.vector_store import VectorStoreCompliance
from quadkit.testing.compliance.webhook import (
    WebhookDeliveryStoreCompliance,
    WebhookSubscriptionStoreCompliance,
)

_LAZY_IMPORTS: Final[dict[str, tuple[str, str]]] = {
    "StoreConformanceSuite": (
        "quadkit.testing.compliance.secrets",
        "StoreConformanceSuite",
    ),
    "parametrize_rotatable_store": (
        "quadkit.testing.compliance.secrets",
        "parametrize_rotatable_store",
    ),
}

# Secret-store compliance depends on a private production extension and is
# omitted from the public projection.
_OPTIONAL_MODULES: Final[frozenset[str]] = frozenset(
    {"quadkit.testing.compliance.secrets"}
)


def __getattr__(name: str) -> Any:
    """Import and return a public attribute on first access."""
    return resolve_export(
        name,
        _LAZY_IMPORTS,
        package=__name__,
        optional=_OPTIONAL_MODULES,
    )


def __dir__() -> list[str]:
    """Return the importable public names."""
    return sorted(__all__)


__all__ = [
    "AuditLoggerCompliance",
    "AuditStoreCompliance",
    "BlobStoreCompliance",
    "CacheBackendCompliance",
    "DatabaseProviderCompliance",
    "DistributedLockCompliance",
    "EventBusCompliance",
    "FlagProviderCompliance",
    "MiddlewareCompliance",
    "NotificationChannelCompliance",
    "QueueBackendCompliance",
    "RepositoryCompliance",
    "SearchEngineCompliance",
    "StoreConformanceSuite",
    "TaskQueueCompliance",
    "VectorStoreCompliance",
    "WebhookDeliveryStoreCompliance",
    "WebhookSubscriptionStoreCompliance",
    "parametrize_rotatable_store",
]
