# Events Timeline / Replay Lab

A focused, offline integration contract for **`quadkit-events` + `WebModule`**.

The lab is a small event journal for one deterministic stream. The browser can:

- publish `open`, `approve`, and intentionally failing `fail` events;
- inspect the in-memory event-store history and global sequence numbers;
- observe an event subscriber and a retrying handler failure;
- replay stored history through Quadkit's optional `EventReplayProtocol`; and
- check the lab's readiness, dispatch diagnostics, and offline backend details.

There is no broker, database, worker, or external API. `EventsModule.configure()`
provides the package-owned in-memory event store and event bus; `WebModule`
provides the HTTP and static browser surface. The demo provider only wires these
public package contracts into a scenario.

## Run

From the repository root:

```bash
cd examples/event-timeline
PYTHONPATH=src ../../.venv/bin/python -m timeline_lab
```

Or run the focused contract tests:

```bash
../../.venv/bin/pytest examples/event-timeline/tests -q
```

The standalone port is `8102`. The demo is also listed in Demo Hub as
`/examples/event-timeline/`.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/events` | Return the current event-store history and delivery observations |
| GET | `/api/events/health` | Return offline readiness details and component health |
| POST | `/api/events/publish` | Append and publish one of the lab's three event actions (`open`, `approve`, `fail`) |
| POST | `/api/events/replay` | Replay the stored event history without appending new events |

## What to look for

1. Publish several events and note that stream versions and global sequence
   numbers are assigned by the event store.
2. Publish **Simulate handler failure**. The publication result remains an
   enqueue result, while the failure panel reports the handler's retry attempts.
   The projection subscriber still receives the event because the bus continues
   after a failed handler.
3. Press **Replay history**. This uses the store's public
   `EventReplayProtocol` capability and reports the number of events replayed
   without appending duplicates.
4. After a failure probe, the readiness panel becomes degraded and exposes the
   bus's retained asynchronous dispatch error count; successful publication
   remains an enqueue result by design.

## Quadkit Concepts

| Concept | How it's used |
|---------|---------------|
| Event Sourcing | `EventStoreProtocol` append/read maintains an immutable event history for the `checkout-demo` stream |
| Domain Events | `TimelineEvent` extends the framework `Event` base class as a frozen dataclass with action, note, and stream metadata |
| Event Bus | `EventBusProtocol.publish()` routes events to subscribers; enqueue semantics with optional `flush()` for deterministic delivery |
| Event Subscribers | `event_bus.subscribe(TimelineEvent, ...)` registers two handlers: `record_delivery` for projections and `failure_probe` for retry visibility |
| Event Replay | `EventReplayProtocol.replay_events()` replays stored history through subscribers without appending duplicates |
| Event Diagnostics | `EventBusDiagnosticsProtocol.dispatch_errors` exposes bus-level async dispatch error counts for health reporting |
| Result Pattern | `Result[T, E]` from `quadkit.result` wraps publish outcomes — `Ok` for enqueued, `Err` for rejected |
| Provider Pattern | `TimelineLabProvider` extends `Provider` with `register()`, `boot()`, `shutdown()`, and `health_check()` lifecycle hooks |
| Dependency Injection | Container `register()` binds types; `boot()` resolves `EventBusProtocol` and `EventStoreProtocol` and wires subscribers |
| Health Checks | `HealthCheckResult` with `HealthStatus` reports provider wiring state; component-level health via optional `health_check()` protocol |
