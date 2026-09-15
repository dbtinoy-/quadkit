"""Contract compliance test suites for Quadkit protocol implementations.

Each suite is a base test class.  Subclass it, implement the abstract
factory method, and pytest will run all contract checks automatically::

    class TestRedisCacheCompliance(CacheBackendCompliance):
        async def create_backend(self):
            return RedisCacheBackend("redis://localhost:6379/15")

Available suites:

- :class:`~quadkit.testing.compliance.AuditLoggerCompliance`
- :class:`~quadkit.testing.compliance.AuditStoreCompliance`
- :class:`~quadkit.testing.compliance.BlobStoreCompliance`
- :class:`~quadkit.testing.compliance.CacheBackendCompliance`
- :class:`~quadkit.testing.compliance.DatabaseProviderCompliance`
- :class:`~quadkit.testing.compliance.DistributedLockCompliance`
- :class:`~quadkit.testing.compliance.EventBusCompliance`
- :class:`~quadkit.testing.compliance.FlagProviderCompliance`
- :class:`~quadkit.testing.compliance.MiddlewareCompliance`
- :class:`~quadkit.testing.compliance.NotificationChannelCompliance`
- :class:`~quadkit.testing.compliance.QueueBackendCompliance`
- :class:`~quadkit.testing.compliance.RepositoryCompliance`
- :class:`~quadkit.testing.compliance.SearchEngineCompliance`
- :class:`~quadkit.testing.compliance.TaskQueueCompliance`
- :class:`~quadkit.testing.compliance.VectorStoreCompliance`
- :class:`~quadkit.testing.compliance.WebhookDeliveryStoreCompliance`
- :class:`~quadkit.testing.compliance.WebhookSubscriptionStoreCompliance`
"""

from __future__ import annotations

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
from quadkit.testing.compliance.secrets import (
    StoreConformanceSuite,
    parametrize_rotatable_store,
)
from quadkit.testing.compliance.task_queue import TaskQueueCompliance
from quadkit.testing.compliance.vector_store import VectorStoreCompliance
from quadkit.testing.compliance.webhook import (
    WebhookDeliveryStoreCompliance,
    WebhookSubscriptionStoreCompliance,
)

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
