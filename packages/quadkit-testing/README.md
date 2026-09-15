# quadkit-testing

Centralized testing infrastructure for Quadkit Framework — Fixtures, factories, and utilities.

---

## Overview

`quadkit-testing` provides in-process fakes for common framework protocols (`FakeCache`, `FakeEventBus`, `FakeCommandBus`, `FakeClock`, …), a pytest plugin with auto-registered fixtures, deterministic data-factory helpers, and a `ContainerTestFixture` for DI integration tests.

---

> Full documentation: [docs.quadkit.dev](https://docs.quadkit.dev)
## Install

```bash
uv add --dev quadkit-testing

# With extras for specific backends
uv add --dev "quadkit-testing[db]"      # aiosqlite, asyncpg
uv add --dev "quadkit-testing[web]"     # httpx, starlette
```

## Quick Start

```python
import pytest
from quadkit.testing.fixtures import fake_cache
from quadkit.testing.fakes import FakeCache


class TestUserService:
    @pytest.fixture
    def cache(self) -> FakeCache:
        return FakeCache()

    @pytest.fixture
    def service(self, cache: FakeCache) -> UserService:
        return UserService(cache=cache)

    @pytest.mark.asyncio
    async def test_returns_cached_user(
        self, service: UserService, cache: FakeCache
    ) -> None:
        await cache.set("user:123", {"id": "123", "name": "Alice"})
        result = await service.find_cached("123")
        assert result.is_ok()
        assert result.unwrap().name == "Alice"
```

## Testing

```python
from quadkit.testing.fakes import FakeEventBus


@pytest.mark.asyncio
async def test_places_order_emits_event(self, fake_event_bus: FakeEventBus) -> None:
    service = OrderService(bus=fake_event_bus)
    await service.place(order)

    fake_event_bus.assert_published(OrderPlaced, order_id=order.id)
    assert len(fake_event_bus.published_of_type(OrderPlaced)) == 1
```

## Available Fakes

All fakes live in `quadkit.testing.fakes` and implement the async contracts of the real services.

| Class | Implements | Location |
|-------|-----------|----------|
| `FakeCache` | cache API (`async get/set/delete/clear`) | `quadkit.testing.fakes.cache` |
| `FakeEventBus` | in-process event bus; `published()`, `published_of_type()`, `assert_published()` | `quadkit.testing.fakes.events` |
| `FakeCommandBus` | command dispatch | `quadkit.testing.fakes.buses` |
| `FakeQueryBus` | query dispatch | `quadkit.testing.fakes.buses` |
| `FakeUnitOfWork` | unit-of-work context | `quadkit.testing.fakes.lifecycle` |
| `FakeClock` | deterministic clock | `quadkit.testing.fakes.clock` |
| `FakeConfig` | config overrides | `quadkit.testing.fakes.config` |
| `FakeLogger` | structlog-compatible logger | `quadkit.testing.fakes.logging` |
| `FakeMetricsCollector` | metrics recording | `quadkit.testing.fakes.monitoring` |
| `FakeStateStore` | state storage | `quadkit.testing.fakes.cache` |
| `FakeAuditLogger` | audit logging | `quadkit.testing.fakes.audit` |
| `FakeRotatableSecretStore` | secret storage with rotation | `quadkit.testing.fakes.secrets` |
| `FakeTracer` / `FakeSpan` | tracing | `quadkit.testing.fakes.tracing` |

## Key Features

- **Zero infrastructure** — all fakes run in-process; no Docker or external services needed
- **Assertion helpers** — `assert_published()`, `assert_not_published()`, `assert_published_once()`, `assert_events_in_order()`
- **Async-first** — all fakes implement the same `async` APIs as real backends
- **pytest plugin** — auto-registered fixtures and auto-skip for external-service markers (Redis, PostgreSQL, Elasticsearch, RabbitMQ, Meilisearch)
- **DB fixtures** — `database_provider`, `clean_database`, `db_transaction`, `mock_connection`, `sample_user_data` (with `[db]` extra)
- **Data factory** — `test_data.create_user()`, `create_task()`, `create_message()` via `quadkit.testing.lib`
- **Container fixture** — `ContainerTestFixture` with `mock()`/`get()` for DI integration tests
- **Reproducible** — deterministic IDs and timestamps for snapshot testing

## pytest Plugin

The plugin is loaded automatically via entry points — no manual wiring needed:

```bash
uv run pytest -m "not integration"   # unit tests only (fast)
uv run pytest -m integration         # integration tests
```

Tests marked with external-service markers (`redis`, `postgres`, `elasticsearch`, `rabbitmq`, `meilisearch`) are skipped automatically when the service is unreachable.

## Key Source Files

| File | What it contains |
|------|----------------|
| `src/quadkit/testing/plugins/pytest/` | pytest plugin entry point, markers, auto-skip hooks |
| `src/quadkit/testing/fixtures/core.py` | Auto-registered core fixtures (`fake_cache`, `fake_event_bus`, …) |
| `src/quadkit/testing/fixtures/container.py` | `ContainerTestFixture` |
| `src/quadkit/testing/fixtures/bed.py` | `TestEnvironment` builder (`use_provider`, `override`, `fake`) |
| `src/quadkit/testing/fixtures/db.py` | DB fixtures (`database_provider`, `clean_database`, …) |
| `src/quadkit/testing/fakes/events.py` | `FakeEventBus` |
| `src/quadkit/testing/fakes/buses.py` | `FakeCommandBus`, `FakeQueryBus` |
| `src/quadkit/testing/lib/factory.py` | `TestDataFactory` (`create_user`, `create_task`, …) |
