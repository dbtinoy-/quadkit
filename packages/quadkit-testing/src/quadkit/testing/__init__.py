"""Quadkit testing utilities."""

from __future__ import annotations

# Re-export from clients (optional deps guarded)
try:
    from quadkit.testing.clients.ai.bed import AITestBed
    from quadkit.testing.clients.ai.client import AITestClient
except ImportError:
    pass
try:
    from quadkit.testing.clients.db.bed import DatabaseTestBed
    from quadkit.testing.clients.db.client import DatabaseTestClient
except ImportError:
    pass
try:
    from quadkit.testing.clients.tasks.bed import TaskTestBed
    from quadkit.testing.clients.tasks.client import TaskTestClient
except ImportError:
    pass
try:
    from quadkit.testing.clients.web.bed import WebTestBed
    from quadkit.testing.clients.web.client import WebTestClient
except ImportError:
    pass

# Re-export from clock
from quadkit.testing.clock import FixedClock

# Re-export from compliance
from quadkit.testing.compliance import (
    AuditLoggerCompliance,
    AuditStoreCompliance,
    BlobStoreCompliance,
    CacheBackendCompliance,
    DatabaseProviderCompliance,
    DistributedLockCompliance,
    EventBusCompliance,
    FlagProviderCompliance,
    MiddlewareCompliance,
    NotificationChannelCompliance,
    QueueBackendCompliance,
    RepositoryCompliance,
    SearchEngineCompliance,
    TaskQueueCompliance,
    VectorStoreCompliance,
    WebhookDeliveryStoreCompliance,
    WebhookSubscriptionStoreCompliance,
)

# Re-export version
from quadkit.testing.constants import __version__

# Re-export from fakes
from quadkit.testing.fakes import (
    Clock,
    FakeAuditLogger,
    FakeCache,
    FakeClock,
    FakeCommandBus,
    FakeConfig,
    FakeEventBus,
    FakeLogger,
    FakeMetricsCollector,
    FakeQueryBus,
    FakeSpan,
    FakeStateStore,
    FakeTracer,
    FakeUnitOfWork,
    LogEntry,
    SystemClock,
)

# Re-export from testkit
from quadkit.testing.fixtures.bed import TestEnvironment

# Re-export from fixtures
from quadkit.testing.fixtures.container import ContainerTestFixture
from quadkit.testing.fixtures.containers import ContainerFactory
from quadkit.testing.generators_contract import (
    assert_contributor_generators_render,
)

# Re-export from harness
from quadkit.testing.harness.container import QuadkitContainerHarness

# Re-export from harness decorators
from quadkit.testing.harness.decorators import override, testbed
from quadkit.testing.harness.environment import IntegrationEnvironment
from quadkit.testing.harness.testbed import AppTestBed

# Re-export from integration (markers and probes)
from quadkit.testing.integration import (
    ServiceProbe,
    requires_postgres,
    requires_rabbitmq,
    requires_redis,
)

# Re-export from lib
from quadkit.testing.lib.admin_helpers import (
    AdminResponse,
    AdminTestClient,
    make_resource_record,
)
from quadkit.testing.lib.assertions import (
    TestAssertions,
    assert_all_ok,
    assert_err,
    assert_healthy,
    assert_ok,
    assert_result_err,
    assert_result_err_contains,
    assert_result_err_type,
    assert_result_ok,
    assert_result_ok_value,
)
from quadkit.testing.lib.async_helper import AsyncTestHelper
from quadkit.testing.lib.factory import TestDataFactory

# Re-export from lib (snapshots)
from quadkit.testing.lib.snapshots import SnapshotAsserter, SnapshotMismatchError

# Re-export from memory
from quadkit.testing.memory import (
    FileInfo,
    InMemoryAuditLogger,
    InMemoryBlobStore,
    InMemoryCacheBackend,
    InMemoryCommandBus,
    InMemoryDistributedLock,
    InMemoryEventBus,
    InMemoryOutbox,
    InMemoryQueryBus,
    InMemoryRepository,
    InMemoryUnitOfWork,
    MemoryProvider,
    OutboxRelay,
)

# Re-export from module
from quadkit.testing.module import TestingModule

__all__ = [
    "AITestBed",
    "AITestClient",
    "AdminResponse",
    "AdminTestClient",
    "AppTestBed",
    "AsyncTestHelper",
    "AuditLoggerCompliance",
    "AuditStoreCompliance",
    "BlobStoreCompliance",
    "CacheBackendCompliance",
    "Clock",
    "ContainerFactory",
    "ContainerTestFixture",
    "DatabaseProviderCompliance",
    "DatabaseTestBed",
    "DatabaseTestClient",
    "DistributedLockCompliance",
    "EventBusCompliance",
    "FakeAuditLogger",
    "FakeCache",
    "FakeClock",
    "FakeCommandBus",
    "FakeConfig",
    "FakeEventBus",
    "FakeLogger",
    "FakeMetricsCollector",
    "FakeQueryBus",
    "FakeSpan",
    "FakeStateStore",
    "FakeTracer",
    "FakeUnitOfWork",
    "FileInfo",
    "FixedClock",
    "FlagProviderCompliance",
    "InMemoryAuditLogger",
    "InMemoryBlobStore",
    "InMemoryCacheBackend",
    "InMemoryCommandBus",
    "InMemoryDistributedLock",
    "InMemoryEventBus",
    "InMemoryOutbox",
    "InMemoryQueryBus",
    "InMemoryRepository",
    "InMemoryUnitOfWork",
    "IntegrationEnvironment",
    "LogEntry",
    "MemoryProvider",
    "MiddlewareCompliance",
    "NotificationChannelCompliance",
    "OutboxRelay",
    "QuadkitContainerHarness",
    "QueueBackendCompliance",
    "RepositoryCompliance",
    "SearchEngineCompliance",
    "ServiceProbe",
    "SnapshotAsserter",
    "SnapshotMismatchError",
    "TaskQueueCompliance",
    "TaskTestBed",
    "TaskTestClient",
    "TestAssertions",
    "TestDataFactory",
    "TestEnvironment",
    "TestingModule",
    "VectorStoreCompliance",
    "WebTestBed",
    "WebTestClient",
    "WebhookDeliveryStoreCompliance",
    "WebhookSubscriptionStoreCompliance",
    "__version__",
    "assert_all_ok",
    "assert_contributor_generators_render",
    "assert_err",
    "assert_healthy",
    "assert_ok",
    "assert_result_err",
    "assert_result_err_contains",
    "assert_result_err_type",
    "assert_result_ok",
    "assert_result_ok_value",
    "make_resource_record",
    "override",
    "requires_postgres",
    "requires_rabbitmq",
    "requires_redis",
    "testbed",
]
