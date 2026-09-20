# Lifecycle

Quadkit applications move through explicit, ordered states — nothing
starts by accident and shutdown is symmetrical with startup.

```text
CREATED → STARTING → RUNNING → STOPPED
```

- **CREATED** — `Application()` (plus `add_modules` / `add_providers`)
  only *assembles*. No provider registers, nothing binds, no sockets
  open. Assembly is cheap and safe at import time.
- **STARTING → RUNNING** — `await app.start()` runs the boot sequence.
- **STOPPED** — `await app.stop()` unwinds providers in reverse and
  leaves a supported end state.

## What `start()` does, in order

1. Validates configuration against the active environment (for
   example, rejecting `debug=True` in a production profile).
2. Emits the `ApplicationStarting` lifecycle event.
3. Registers all providers with the container (`register()` phase).
4. Boots all providers in dependency order, in parallel where possible
   (`boot()` phase — see
   [dependency injection](./dependency-injection.md)).
5. Resolves the event bus and emits `ApplicationStarted`.

If any phase fails, providers already booted are shut down and the app
lands in `STOPPED` — no half-started processes.

## Lazy boot

You rarely call `start()` yourself:

- `run_server(app, port=8000)` boots the application when the server
  starts and stops it on shutdown.
- The ASGI entry point (`Application.__call__`) lazily starts the app
  on first request if it is still `CREATED` — useful when an external
  ASGI server loads the application object.
- `WebTestBed(app)` boots and tears down the app around each test.

## Provider lifecycle

Your own providers plug into the same sequence — no lifecycle method
runs before its time:

| Phase | Method | Runs when |
| --- | --- | --- |
| Declare | `register(container)` | all providers, before any boot |
| Initialize | `boot(container)` | after registration; I/O allowed |
| Report | `health_check(timeout)` | aggregated into health results |
| Release | shutdown | on `app.stop()`, reverse order |

`health_check()` results aggregate into the app's health reports and
the web layer's `/health` probe.

Next: [async model](./async-model.md).
