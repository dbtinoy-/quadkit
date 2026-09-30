# quadkit-testing

![Quadkit](https://raw.githubusercontent.com/dbtinoy-/quadkit/main/banner.jpg)

[![PyPI](https://img.shields.io/pypi/v/quadkit-testing?color=%2322c55e&label=pypi)](https://pypi.org/project/quadkit-testing/)
[![Python](https://img.shields.io/pypi/pyversions/quadkit-testing?color=%2322c55e)](https://pypi.org/project/quadkit-testing/)
[![License](https://img.shields.io/pypi/l/quadkit-testing?color=%2322c55e)](https://github.com/dbtinoy-/quadkit/blob/main/LICENSE)

Test harnesses, fakes, and fixtures for Quadkit applications: boot the
real application in-process, substitute bindings instead of mocking
import sites, and assert on responses with helpers that say what
failed.

For anyone writing tests against Quadkit applications — and for tooling
that needs drop-in implementations of the framework's protocols.

## The quadkit family

| Package | Role |
| --- | --- |
| [`quadkit-contracts`](https://pypi.org/project/quadkit-contracts/) | zero-dependency protocols, types, exception hierarchy |
| [`quadkit`](https://pypi.org/project/quadkit/) | the framework core — DI container, modules, config, logging, `Result` |
| [`quadkit-web`](https://pypi.org/project/quadkit-web/) | ASGI layer — controllers, routing, middleware, OpenAPI docs |
| [`quadkit-cli`](https://pypi.org/project/quadkit-cli/) | project scaffolding and code generators |
| [`quadkit-testing`](https://pypi.org/project/quadkit-testing/) | in-process test beds, fakes, fixtures |

## Installation

```bash
uv add --dev quadkit-testing
```

Requires **Python >= 3.11**.

## Minimal working example

Test an HTTP route with the real application, in-process:

```python
import pytest

from quadkit.testing import WebTestBed

from my_app import create_app


@pytest.mark.asyncio
async def test_hello() -> None:
    async with WebTestBed(create_app()) as bed:
        response = bed.get("/hello", params={"name": "quadkit"})
        response.assert_status(200)
        assert response.json == {"message": "hello, quadkit"}
```

Or test services directly, with binding overrides:

```python
async def test_service() -> None:
    from quadkit.testing import AppTestBed

    async with AppTestBed.from_factory(
        create_app, overrides={Cache: FakeCache()}
    ) as bed:
        service = await bed.app.container.resolve(UserService)
```

A pytest plugin registers automatically via entry points — no
`conftest.py` wiring — and provides auto-registered fixtures including
`fake_cache`, `fake_event_bus`, `fake_logger`, `fake_clock`,
`fake_command_bus`, `fake_query_bus`, `fake_unit_of_work`,
`fake_metrics`, `fake_config`, `fake_state_store`, `test_bed`,
`test_container`, and `test_data`:

```python
import pytest

from quadkit.contracts.domain.events import DomainEvent


class UserCreated(DomainEvent):
    user_id: str
    email: str


@pytest.mark.asyncio
async def test_signup_publishes(fake_event_bus) -> None:
    await fake_event_bus.publish(UserCreated(user_id="1", email="a@b.c"))
    fake_event_bus.assert_published(UserCreated, user_id="1")


def test_trial_expiry_is_deterministic(fake_clock) -> None:
    t0 = fake_clock.now()
    fake_clock.advance(30 * 24 * 3600)
    assert (fake_clock.now() - t0).days == 30
```

## Optional extras

| Extra | Contents |
| --- | --- |
| `[web]` | `httpx` + Starlette — the `WebTestBed` client transport |
| `[db]` | `aiosqlite`, `asyncpg` — drivers for your async DB test suites |
| `[integration]` | service clients for integration suites (Redis, MongoDB, Kafka, Elasticsearch, Neo4j, Qdrant, PostgreSQL, SQLite) |
| `[dev]` | `ruff`, `mypy`, `black` |

## Public API entry points

### Test beds

```python
from quadkit.testing import AppTestBed, WebTestBed
```

- `AppTestBed.from_factory(factory, overrides=None)` /
  `AppTestBed.from_app(app)` — application-level beds.
- `WebTestBed(app_or_provider, raise_server_exceptions=True)` with
  `get/post/put/patch/delete`, `override(Contract, impl)` (before
  boot), and `TestResponse` — `status_code`, `headers`, `text`,
  `json` (property), `assert_status`, `assert_json`,
  `assert_json_path`, `assert_header`.
- `quadkit.testing.fixtures.container.ContainerTestFixture` — DI-level
  fixture with `mock()`, `override()`, `get()`, `get_optional()`.
- `quadkit.testing.fixtures.bed.TestEnvironment` — programmatic
  environment builder (`use_provider`, `override`, `fake`, `resolve`).
- `quadkit.testing.lib.factory.TestDataFactory` — deterministic
  `create_user()`, `create_task()`, `create_message()`,
  `create_request()`.

### Fakes (`quadkit.testing.fakes`)

All in-process, async-native, implementing the same contracts as the
real services:

| Class | Covers |
| --- | --- |
| `FakeCache` / `FakeStateStore` | cache and state storage |
| `FakeEventBus` | in-process events with `assert_published()`, `published_of_type()`, `assert_events_in_order()` and friends |
| `FakeCommandBus` / `FakeQueryBus` | command / query dispatch |
| `FakeUnitOfWork` | unit-of-work context |
| `FakeClock` (+ `Clock`, `SystemClock`) | deterministic time |
| `FakeConfig` | config overrides |
| `FakeLogger` (+ `LogEntry`) | structlog-compatible sink |
| `FakeMetricsCollector` / `FakeResourceUnitTracker` | metrics / resource tracking |
| `FakeRedisClient` | Redis-protocol client |
| `FakeAuditLogger` | audit records |
| `FakeTracer` / `FakeSpan` | tracing |

The published wheel carries the `ai`, `db` and `web` test clients and beds
plus the fakes and fixtures that need no private package. The `auth`,
`cache`, `events`, `search`, `storage`, `tasks`, `ui` test clients, the
AI/DB/task fixture modules, the secrets fake and `IntegrationEnvironment`
stay in this repository until their packages publish; asking the published
wheel for one raises `AttributeError` naming the module.

## Configuration

None required — the pytest plugin self-registers. Mark suites for
external services and gate them yourself (e.g.
`uv run pytest -m "not integration"`).

## Error handling

Test beds surface failures, they don't hide them: with
`raise_server_exceptions=True` (the default) unexpected exceptions
re-raise into your test with their original traceback; HTTP-expected
failures assert on the response instead.

## Testing

Ironically self-hosted: this package's public tests are among the
suite the release executes from the exported tree against the built
wheels.

## Security

Fakes are in-process and safe to wire into unit suites. Report
vulnerabilities privately per [SECURITY.md](https://github.com/dbtinoy-/quadkit/blob/main/SECURITY.md).

## Stability

Version `0.0.44` in the `0.x` series, released in lockstep with the
other four distributions; APIs may change between minor versions until
1.0 — pin an exact version (`quadkit-testing==0.0.44`) or a tight range
(`>=0.0.44,<0.1.0`). Full policy:
[stability and compatibility](https://dbtinoy-.github.io/quadkit/reference/stability/).

## Links

- **Documentation** — <https://dbtinoy-.github.io/quadkit/>
- **Getting started** — <https://dbtinoy-.github.io/quadkit/getting-started/installation/>
- **Changelog** — <https://github.com/dbtinoy-/quadkit/blob/main/CHANGELOG.md>
- **Issues** — <https://github.com/dbtinoy-/quadkit/issues>
- **Security** — report privately per [SECURITY.md](https://github.com/dbtinoy-/quadkit/blob/main/SECURITY.md)
- **Contributing** — [CONTRIBUTING.md](https://github.com/dbtinoy-/quadkit/blob/main/CONTRIBUTING.md)

Apache-2.0 — see [LICENSE](https://github.com/dbtinoy-/quadkit/blob/main/LICENSE). "Quadkit" and the
Quadkit logo are trademarks of the project — see
[TRADEMARK.md](https://github.com/dbtinoy-/quadkit/blob/main/TRADEMARK.md).
