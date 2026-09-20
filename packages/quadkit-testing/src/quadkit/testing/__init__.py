"""Quadkit testing utilities.

Every public name is resolved on first attribute access, so importing this
package costs little more than ``import quadkit``: the test beds, the in-memory
fakes and the conformance suites load when a test actually asks for them.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from quadkit.testing._lazy_exports import module_shipped
from quadkit.testing.constants import __version__

if TYPE_CHECKING:
    from quadkit.testing.clients.ai.bed import AITestBed
    from quadkit.testing.clients.ai.client import AITestClient
    from quadkit.testing.clients.db.bed import DatabaseTestBed
    from quadkit.testing.clients.db.client import DatabaseTestClient
    from quadkit.testing.clients.tasks.bed import TaskTestBed
    from quadkit.testing.clients.tasks.client import TaskTestClient
    from quadkit.testing.clients.web.bed import WebTestBed
    from quadkit.testing.clients.web.client import WebTestClient
    from quadkit.testing.clock import FixedClock
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
    from quadkit.testing.fixtures.bed import TestEnvironment
    from quadkit.testing.fixtures.container import ContainerTestFixture
    from quadkit.testing.fixtures.containers import ContainerFactory
    from quadkit.testing.generators_contract import assert_contributor_generators_render
    from quadkit.testing.harness.container import QuadkitContainerHarness
    from quadkit.testing.harness.decorators import (
        override,
        testbed,
    )
    from quadkit.testing.harness.environment import IntegrationEnvironment
    from quadkit.testing.harness.testbed import AppTestBed
    from quadkit.testing.integration import (
        ServiceProbe,
        requires_postgres,
        requires_rabbitmq,
        requires_redis,
    )
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
    from quadkit.testing.lib.snapshots import (
        SnapshotAsserter,
        SnapshotMismatchError,
    )
    from quadkit.testing.memory import (
        FileInfo,
        InMemoryAuditLogger,
        InMemoryBlobStore,
        InMemoryCacheBackend,
        InMemoryCommandBus,
        InMemoryDistributedLock,
        InMemoryEventBus,
        InMemoryLockStore,
        InMemoryOutbox,
        InMemoryQueryBus,
        InMemoryRepository,
        InMemoryUnitOfWork,
        MemoryProvider,
        OutboxRelay,
    )
    from quadkit.testing.module import TestingModule

_LAZY_IMPORTS: Final[dict[str, str]] = {
    "AITestBed": "quadkit.testing.clients.ai.bed",
    "AITestClient": "quadkit.testing.clients.ai.client",
    "AdminResponse": "quadkit.testing.lib.admin_helpers",
    "AdminTestClient": "quadkit.testing.lib.admin_helpers",
    "AppTestBed": "quadkit.testing.harness.testbed",
    "AsyncTestHelper": "quadkit.testing.lib.async_helper",
    "AuditLoggerCompliance": "quadkit.testing.compliance",
    "AuditStoreCompliance": "quadkit.testing.compliance",
    "BlobStoreCompliance": "quadkit.testing.compliance",
    "CacheBackendCompliance": "quadkit.testing.compliance",
    "Clock": "quadkit.testing.fakes",
    "ContainerFactory": "quadkit.testing.fixtures.containers",
    "ContainerTestFixture": "quadkit.testing.fixtures.container",
    "DatabaseProviderCompliance": "quadkit.testing.compliance",
    "DatabaseTestBed": "quadkit.testing.clients.db.bed",
    "DatabaseTestClient": "quadkit.testing.clients.db.client",
    "DistributedLockCompliance": "quadkit.testing.compliance",
    "EventBusCompliance": "quadkit.testing.compliance",
    "FakeAuditLogger": "quadkit.testing.fakes",
    "FakeCache": "quadkit.testing.fakes",
    "FakeClock": "quadkit.testing.fakes",
    "FakeCommandBus": "quadkit.testing.fakes",
    "FakeConfig": "quadkit.testing.fakes",
    "FakeEventBus": "quadkit.testing.fakes",
    "FakeLogger": "quadkit.testing.fakes",
    "FakeMetricsCollector": "quadkit.testing.fakes",
    "FakeQueryBus": "quadkit.testing.fakes",
    "FakeSpan": "quadkit.testing.fakes",
    "FakeStateStore": "quadkit.testing.fakes",
    "FakeTracer": "quadkit.testing.fakes",
    "FakeUnitOfWork": "quadkit.testing.fakes",
    "FileInfo": "quadkit.testing.memory",
    "FixedClock": "quadkit.testing.clock",
    "FlagProviderCompliance": "quadkit.testing.compliance",
    "InMemoryAuditLogger": "quadkit.testing.memory",
    "InMemoryBlobStore": "quadkit.testing.memory",
    "InMemoryCacheBackend": "quadkit.testing.memory",
    "InMemoryCommandBus": "quadkit.testing.memory",
    "InMemoryDistributedLock": "quadkit.testing.memory",
    "InMemoryLockStore": "quadkit.testing.memory",
    "InMemoryEventBus": "quadkit.testing.memory",
    "InMemoryOutbox": "quadkit.testing.memory",
    "InMemoryQueryBus": "quadkit.testing.memory",
    "InMemoryRepository": "quadkit.testing.memory",
    "InMemoryUnitOfWork": "quadkit.testing.memory",
    "IntegrationEnvironment": "quadkit.testing.harness.environment",
    "LogEntry": "quadkit.testing.fakes",
    "MemoryProvider": "quadkit.testing.memory",
    "MiddlewareCompliance": "quadkit.testing.compliance",
    "NotificationChannelCompliance": "quadkit.testing.compliance",
    "OutboxRelay": "quadkit.testing.memory",
    "QuadkitContainerHarness": "quadkit.testing.harness.container",
    "QueueBackendCompliance": "quadkit.testing.compliance",
    "RepositoryCompliance": "quadkit.testing.compliance",
    "SearchEngineCompliance": "quadkit.testing.compliance",
    "ServiceProbe": "quadkit.testing.integration",
    "SnapshotAsserter": "quadkit.testing.lib.snapshots",
    "SnapshotMismatchError": "quadkit.testing.lib.snapshots",
    "SystemClock": "quadkit.testing.fakes",
    "TaskQueueCompliance": "quadkit.testing.compliance",
    "TaskTestBed": "quadkit.testing.clients.tasks.bed",
    "TaskTestClient": "quadkit.testing.clients.tasks.client",
    "TestAssertions": "quadkit.testing.lib.assertions",
    "TestDataFactory": "quadkit.testing.lib.factory",
    "TestEnvironment": "quadkit.testing.fixtures.bed",
    "TestingModule": "quadkit.testing.module",
    "VectorStoreCompliance": "quadkit.testing.compliance",
    "WebTestBed": "quadkit.testing.clients.web.bed",
    "WebTestClient": "quadkit.testing.clients.web.client",
    "WebhookDeliveryStoreCompliance": "quadkit.testing.compliance",
    "WebhookSubscriptionStoreCompliance": "quadkit.testing.compliance",
    "assert_all_ok": "quadkit.testing.lib.assertions",
    "assert_contributor_generators_render": "quadkit.testing.generators_contract",
    "assert_err": "quadkit.testing.lib.assertions",
    "assert_healthy": "quadkit.testing.lib.assertions",
    "assert_ok": "quadkit.testing.lib.assertions",
    "assert_result_err": "quadkit.testing.lib.assertions",
    "assert_result_err_contains": "quadkit.testing.lib.assertions",
    "assert_result_err_type": "quadkit.testing.lib.assertions",
    "assert_result_ok": "quadkit.testing.lib.assertions",
    "assert_result_ok_value": "quadkit.testing.lib.assertions",
    "make_resource_record": "quadkit.testing.lib.admin_helpers",
    "override": "quadkit.testing.harness.decorators",
    "requires_postgres": "quadkit.testing.integration",
    "requires_rabbitmq": "quadkit.testing.integration",
    "requires_redis": "quadkit.testing.integration",
    "testbed": "quadkit.testing.harness.decorators",
}

_OPTIONAL_MODULES: Final[frozenset[str]] = frozenset(
    {
        "quadkit.testing.clients.ai.bed",
        "quadkit.testing.clients.ai.client",
        "quadkit.testing.clients.db.bed",
        "quadkit.testing.clients.db.client",
        "quadkit.testing.clients.tasks.bed",
        "quadkit.testing.clients.tasks.client",
        "quadkit.testing.clients.web.bed",
        "quadkit.testing.clients.web.client",
        "quadkit.testing.harness.environment",
    }
)


def __getattr__(name: str) -> Any:
    """Import and return a public attribute on first access."""
    module_path = _LAZY_IMPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    if module_path in _OPTIONAL_MODULES and not module_shipped(module_path):
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}: "
            f"{module_path} is not part of this installation"
        )
    module = importlib.import_module(module_path)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return the importable public names."""
    return sorted(__all__)


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
    "InMemoryLockStore",
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
    "SystemClock",
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
# Names whose module is absent from this installation stay unadvertised,
# so star-imports keep working in the public projection.
__all__ = [
    name
    for name in __all__
    if _LAZY_IMPORTS.get(name) not in _OPTIONAL_MODULES
    or module_shipped(_LAZY_IMPORTS[name])
]
