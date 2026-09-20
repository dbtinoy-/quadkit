# Quadkit Testing Module

`quadkit.testing` provides the testing infrastructure for applications built on
the Quadkit Framework: test beds that boot a real application against
in-memory doubles, in-memory implementations of the framework's contracts,
conformance suites for your own implementations, and the assertion helpers
used across the ecosystem.

Every public name resolves on first attribute access, so importing the
package costs little more than `import quadkit`.

## Overview

- **Test beds** — `AppTestBed`, `WebTestBed`, `TaskTestBed`, `DatabaseTestBed`
  and `AITestBed` boot an application (or a provider set) with overrides and
  hand back a ready client.
- **Pytest fixtures** — the pytest plugin registers fixtures for the in-memory
  doubles, the web/task/database beds and sample data. They load automatically
  once the package is installed.
- **Fakes and in-memory doubles** — `FakeCache`, `FakeClock`, `FakeConfig`,
  `FakeLogger`, `FakeMetricsCollector`, `FakeStateStore`, `FakeUnitOfWork`,
  and the `InMemory*` bus/repository/cache/outbox/audit/lock implementations.
- **Conformance suites** — abstract test classes that check a cache backend,
  event bus, repository, queue, vector store and the rest against the
  contract they claim to implement.
- **Assertions and data** — `TestAssertions`, the `assert_result_*` helpers
  for `Result[T, E]`, `TestDataFactory` and snapshot assertions.

## Quick Start

`TestEnvironment` boots a real application against the fakes and manages the
lifecycle for a test:

```python
import pytest

from quadkit.testing import TestEnvironment


@pytest.mark.asyncio
async def test_my_feature():
    env = TestEnvironment("my-feature")
    env.use_provider(MemoryProvider())

    async with env:
        service = await env.container.resolve(MyService)

        assert await service.do_something() is not None
```

For tests that only need the in-memory doubles, the fixtures are shorter:

```python
@pytest.mark.asyncio
async def test_cache(fake_cache):
    await fake_cache.set("key", "value", ttl=30)

    assert await fake_cache.get("key") == "value"
```

## Fixtures

The pytest plugin registers these fixtures process-wide; ask for them by name.

| Group | Fixtures |
|---|---|
| Core | `test_bed`, `test_container`, `test_data`, `assertions`, `fake_cache`, `fake_clock`, `fake_command_bus`, `fake_config`, `fake_event_bus`, `fake_logger`, `fake_metrics`, `fake_query_bus`, `fake_state_store`, `fake_unit_of_work` |
| Web | `app_bed`, `web_test_bed`, `web_test_client`, `authenticated_web_client`, `mock_web_request`, `mock_web_response`, `sample_web_user_data`, `sample_web_post_data` |
| Database | `db_test_bed`, `db_transaction`, `clean_database`, `seeded_database`, `mock_connection`, `mock_connection_pool`, `database_provider`, `sample_user_data`, `sample_order_data`, `sample_product_data`, `test_database_client` |
| Tasks | `task_test_bed`, `task_test_client`, `sample_task_data` |

The database and task fixtures are registered when their integration is
installed; the AI fixtures resolve on demand through the same lazy lookup as
the package facade.

## Test Beds

A bed boots the application or provider set once and exposes a container and a
client:

```python
from quadkit.testing import AppTestBed


@pytest.mark.asyncio
async def test_user_endpoint():
    async with AppTestBed.from_factory("my_app.app:create_app") as bed:
        response = await bed.client.get("/api/v1/users")

        assert response.status_code == 200
```

`WebTestBed` takes a provider (or an application) directly and is used with
`await bed.setup()` / `await bed.teardown()`; its `bed.client` is a
`WebTestClient` whose response has `.status_code`, `.json` and
`.assert_status(...)`.

Available beds: `AppTestBed` (`from_factory` / `from_app`), `WebTestBed` +
`WebTestClient`, `TaskTestBed` + `TaskTestClient`, `DatabaseTestBed` +
`DatabaseTestClient`, `AITestBed` + `AITestClient`, plus `AdminTestClient`.

Inside a test class, `@testbed` and `@override` remove the boilerplate:

```python
from quadkit.testing import override, testbed
from quadkit.testing import AppTestBed


@testbed("my_app.app:create_app", overrides={EmailService: FakeEmailService()})
class TestUsers:
    @override(UserRepository, InMemoryUserRepository())
    async def test_list_users(self, bed: AppTestBed):
        response = await bed.client.get("/api/v1/users")

        assert response.status_code == 200
```

## In-Memory Doubles

The `InMemory*` classes implement framework contracts with no external
service, and the `Fake*` classes are the smaller, behaviour-focused doubles:

```python
from quadkit.testing import InMemoryEventBus, InMemoryRepository, InMemoryUnitOfWork

events = InMemoryEventBus()
users = InMemoryRepository()
uow = InMemoryUnitOfWork()
```

`MemoryProvider` registers the buses, the audit logger and the rest as
container singletons, and `TestingModule` packages them for module-based
applications:

```python
from quadkit.testing import MemoryProvider, TestingModule

app.add_provider(MemoryProvider())
```

`InMemoryDistributedLock` coordinates only the locks that share a store —
pass one `InMemoryLockStore` to the locks that must block each other (the
`TestEnvironment` does this for the lock it registers). A lock created with
no store gets a private one, so lock state never leaks between tests.

## Conformance Suites

Subclass a `*Compliance` class, implement the factory for your
implementation, and inherit the contract tests:

```python
from quadkit.testing import CacheBackendCompliance


class TestRedisCacheBackend(CacheBackendCompliance):
    async def create_backend(self):
        return RedisCacheBackend(url="redis://localhost:6379")
```

Available suites: `AuditLoggerCompliance`, `AuditStoreCompliance`,
`BlobStoreCompliance`, `CacheBackendCompliance`, `DatabaseProviderCompliance`,
`DistributedLockCompliance`, `EventBusCompliance`, `FlagProviderCompliance`,
`MiddlewareCompliance`, `NotificationChannelCompliance`,
`QueueBackendCompliance`, `RepositoryCompliance`, `SearchEngineCompliance`,
`TaskQueueCompliance`, `VectorStoreCompliance`,
`WebhookDeliveryStoreCompliance`, `WebhookSubscriptionStoreCompliance`.

## Assertions and Test Data

`TestAssertions` and the module-level result helpers assert on `Result[T, E]`
and on health checks:

```python
from quadkit.result import Ok
from quadkit.testing import assert_ok, assert_result_err_type


def test_service_result():
    result = service.get_user("123")

    assert_ok(result)
    user = result.unwrap()
    assert user["id"] == "123"


def test_expected_failure():
    result = service.get_user("missing")

    assert_result_err_type(result, NotFoundError)
```

The `assertions` fixture hands each test a fresh `TestAssertions`, and
`test_data` does the same for `TestDataFactory`:

```python
def test_user_payload(test_data):
    payload = test_data.create_user(username="a")

    assert payload["username"] == "a"
```

`SnapshotAsserter` compares a value against a stored snapshot and raises
`SnapshotMismatchError` when it drifts.

## Markers

The plugin registers the service markers and skips a marked test at
collection time when the service does not accept a TCP connection on its
default localhost port:

```python
@pytest.mark.requires_redis
async def test_cache_round_trip(): ...
```

Markers: `requires_redis`, `requires_postgres`, `requires_elasticsearch`,
`requires_rabbitmq`, `requires_meilisearch`, `requires_smtp`,
`requires_kafka`, `requires_minio`, `requires_mongodb`, `requires_qdrant`,
`requires_neo4j`, plus `integration`, `slow` and `performance`.
`ServiceProbe` exposes the same availability checks for fixtures that need to
decide at runtime.

## Contributing

When adding a double or a suite:

1. Implement the framework contract, not a bespoke interface, so the
   conformance suites apply.
2. Add the name to the package's lazy export map (`src/quadkit/testing/__init__.py`)
   and to `__all__`.
3. Register a fixture when a test would otherwise construct the double itself.
4. Cover the double with a test in `tests/unit`, and run an existing
   `*Compliance` suite against it.
