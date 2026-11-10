# quadkit-events

Event Sourcing and CQRS engine for Quadkit Framework — domain events, aggregates, and projections.

---

## Overview

CQRS, Event Sourcing, and messaging for Quadkit — command bus, event bus, event
store, sagas, and projections. Provides a full CQRS stack: a typed command bus, an in-process pub/sub event bus, an append-only event store
(PostgreSQL, SQLite, MongoDB, in-memory), saga orchestration, projections, and
outbox processing.

Use `EventsModule.configure()` to register the event system and dispatch commands
or subscribe to events via decorators.


> Full documentation: [oridecon.dev/quadkit](https://oridecon.dev/quadkit)
## Install

```bash
uv add quadkit-events
# Optional extras
uv add "quadkit-events[postgres,sqlite,mongo]"
```

## Quick Start

```python
from quadkit import Application
from quadkit.di.module import Module, module
from quadkit.events import EventsModule, EventsConfig


@module(imports=[EventsModule.configure()])
class AppModule(Module):
    pass


async def main():
    async with Application.boot(modules=[AppModule]) as app:
        # your event sourcing code
        ...


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
```

## Configuration

> **Zero-config usage:** Call `EventsModule.configure()` with no arguments to use defaults (in-memory event store and bus).

### Option 1 — YAML file

```yaml
# application.yaml
events:
  event_store_backend: postgres
  postgres:
    dsn: "${DATABASE_URL}"
```

### Option 2 — Profiles + Environment Variables *(recommended)*

```bash
export QK_EVENTS__EVENT_STORE_BACKEND=postgres
export QK_EVENTS__POSTGRES__DSN="postgresql://user:pass@host/db"
```

### Option 3 — Python

```python
from quadkit.events import EventsConfig, EventsModule, PostgresEventStoreConfig
from quadkit.events.types import EventStoreBackend

config = EventsConfig(
    event_store_backend=EventStoreBackend.POSTGRES,
    postgres=PostgresEventStoreConfig(dsn="${DATABASE_URL}"),
)
EventsModule.configure(config)
```

### Config reference

| Field | Default | Env var | Description |
|-------|---------|---------|-------------|
| `event_store_backend` | `memory` | `QK_EVENTS__EVENT_STORE_BACKEND` | Store backend: `postgres`, `sqlite`, `mongodb`, `memory` |
| `event_bus.max_concurrent_handlers` | `10` | `QK_EVENTS__EVENT_BUS__MAX_CONCURRENT_HANDLERS` | Max concurrent handler tasks |
| `event_bus.enable_dead_letter` | `True` | `QK_EVENTS__EVENT_BUS__ENABLE_DEAD_LETTER` | Send failed events to dead-letter queue |

## Module Factory Methods

| Method | Description |
|--------|-------------|
| `EventsModule.configure(...)` | Configure with explicit EventsConfig |
| `EventsModule.stub()` | In-memory event store for testing |

## WebSocket Event Streaming

`EventWebSocketEndpoint` streams every event published to a
`StreamDispatcher` to connected WebSocket clients in real time.

> **Security:** the endpoint does **not** authenticate connections by
> default. With no `authorize` callback, any client that can reach the
> endpoint receives a live, unauthenticated stream of **all** dispatched
> events — potentially business-sensitive or PII-bearing. Always pass an
> `authorize` callback in production:

```python
from quadkit.events.streaming import EventWebSocketEndpoint, StreamDispatcher


def authorize(scope: dict) -> bool:
    headers = dict(scope.get("headers") or [])
    return headers.get(b"authorization") == b"Bearer secret"


dispatcher = StreamDispatcher()
ws_app = EventWebSocketEndpoint(dispatcher, authorize=authorize)
```

The callback receives the ASGI connection `scope` (headers, query
string, client) and may be synchronous or asynchronous; returning a
falsy value rejects the connection with a `4401` close before the
handshake is accepted.

## Key Features

- **CommandBus** — Typed async command dispatch with middleware
- **EventBus** — In-process pub/sub with dead-letter handling
- **EventStore** — Append-only store (PostgreSQL, SQLite, MongoDB, in-memory)
- **Saga** — Long-running process orchestration with compensating transactions
- **Projection** — Read-model rebuilding from event streams
- **Outbox** — Reliable event delivery via transactional outbox pattern
- **Schema migration** — Versioned event schema evolution

## Use-case generator source references

`quadkit gen use_case` accepts a narrow data-reference vocabulary in its behavior
specification. In aggregate writes, event payloads and job payloads,
`input.<name>` must name an ASCII Python identifier explicitly declared in
`fields_str`. Calls, attribute chains, keywords, unknown inputs and implicit
command metadata are rejected before rendering, including during dry runs or
forced overwrites. A rejected source leaves existing output files unchanged.

For example, `fields_str="title:str"` permits `input.title`, not
`input.title.upper()` or `input.id`. Use `principal` and `clock` for injected
invocation context rather than treating that context as an authored input.
A `principal` source requires `principal_required=true` in every source-bearing
lane (writes, event payloads and job payloads). Merely declaring an input named
`principal_sub` is not authenticated context. Invalid combinations fail before
rendering, including dry runs and forced overwrites. The trusted adapter still
has to authenticate and inject the principal; enabling the flag does not perform
authentication. `clock` continues to add its invocation-time message field.
Aggregate references retain their existing mapping-key semantics.

This validates input references; it does not turn behavior specifications into
an untrusted-code sandbox. Imports and other application wiring remain
application-authored. Standalone event appends/job enqueues remain non-atomic
with the aggregate update, and an event store is not automatically an outbox.

## Testing

```python
async with Application.boot(modules=[EventsModule.stub()]) as app:
    # your test code
    ...
```

## Key Source Files

| File | What it contains |
|------|-----------------|
| `src/quadkit/events/module.py` | EventsModule definition |
| `src/quadkit/events/config.py` | EventsConfig and all config sub-models |
| `src/quadkit/events/di/provider.py` | EventsProvider wiring |
| `src/quadkit/events/buses/` | CommandBus, EventBus, QueryBus implementations |
| `src/quadkit/events/stores/` | Event store implementations (memory, postgres, etc.) |

## Standalone related snapshot assignments

The use-case generator can copy allowlisted related-row fields into its own
aggregate. This is a **standalone generator prerequisite**, not enabled
Playground graph/HTTP authoring or automatic relationship discovery. Example
`spec` for `fields_str="category_id:uuid"`:

```python
{
    "validate_inputs": True,
    "typed_outcomes": True,
    "related_reads": [
        {"name": "category", "key": "input.category_id", "fields": ["title"]},
    ],
    "writes": [
        {"field": "category_title", "source": "related.category.title"},
    ],
}
```

Construct the generated handler with `related_category_repository` explicitly.
Its read-only protocol provides async `get(str_key)` returning a Result with a
dictionary row or an exception. The app owns its DI binding, authorization/tenant
scope and field/type/visibility policy. Never inject an unrestricted repository
into an untrusted adapter merely because a caller can supply a row id.

Lookup keys are required declared string/UUID inputs. Aliases/field names are
unique public ASCII snake_case, with closed metadata keys. Empty string keys,
missing rows, read errors and missing allowlisted fields fail before mutation.
All reads run after the operation's existing principal/policy/transition/custom
work refusals and before any aggregate mutation/write. With typed outcomes, read
failures distinguish `related_not_found`, `related_repository_error` and
`invalid_related`. Related references are supported only in writes, not effect
payloads, scalar outputs or other lookup keys.

These are **independent snapshots**. No cross-entity transaction, row lock, retry,
related-row write, join, background synchronization or related authorization is
generated. A related row may change after the read; aggregate CAS does not guard
its version. Values are copied as-is; callers must validate compatibility with
the aggregate's schema. Existing standalone event/job effects remain non-atomic.

### Opt-in scalar target validation for related writes

A standalone spec can add `related_write_checks` to validate copied values before
any aggregate mutation, transition, counter application or persistence:

```python
"related_write_checks": [
    {
        "field": "category_title",
        "type": "str",
        "nullable": False,
        "min_length": 1,
        "max_length": 80,
        "enum": ["News", "Updates"],
    },
]
```

Check `UseCaseGenerator.supports_related_write_checks_v1 is True` before relying
on this metadata; version strings alone do not establish the capability. Basic
input validation must be enabled. When this key is supplied, every related write
must have exactly one target record. Unknown fields/options, unsupported types,
nonboolean nullability, invalid bounds and incomplete coverage fail generation,
including dry runs or forced overwrites. Omit `enum` for unrestricted text.

Supported target types are exact `str`, `int`, `float`, `bool` (no coercion and no
bool-as-int). Nullability is explicit. Text is checked for UTF-8/NUL storage
compatibility, inclusive `min_length`/`max_length` and optional string `enum`.
Numeric types accept inclusive finite `minimum`/`maximum`; floats must be finite.
Failures return `success=False`, with `invalid_related_value` when typed outcomes
are enabled. Error messages do not include copied values.

This checks the **authored target contract**, not a discovered database schema.
Patterns, formats, references, uniqueness and arbitrary/composite target types
are not supported options here; database constraints and row policy remain the
application's responsibility. Unbounded integers are not a portable SQL range
claim. Specs without this optional key retain their prior unchecked behavior.
Normal Playground graph generation is still gated; it does not yet derive these
records from entity constraints. This is not authorization or cross-row atomicity.
