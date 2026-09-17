# Async model

Async is not an opt-in mode — the container, modules, controllers, and
providers are async end to end, and concurrency-safe by construction.

## Async all the way down

Controller actions are `async` coroutines:

```python
class OrdersController(Controller):
    @get("/orders/{order_id}")
    async def get_order(self, order_id: str) -> dict:
        return {"id": order_id}
```

Provider `boot()` is async (initialization may do I/O),
`Application.start()`/`stop()` are awaited, and factories registered
with the container may themselves be async callables.

## Serving: sync wrapper vs. async-native

Two entry points serve an application, and the rule is simple:

- `run_server(app, ...)` — **synchronous and blocking**. It runs the
  server directly in the calling thread and never inspects the
  surrounding context. Called from inside a running event loop it raises
  `RuntimeError` rather than silently blocking that loop.
- `await run_server_async(app, ...)` — the async-native entry point for
  code already inside an event loop (REPLs, notebooks, embedding into a
  larger async process). Uvicorn serves in the calling loop; Granian
  runs in an executor thread.

Scripts and `__main__` entry points use the sync wrapper — that is what
the [first app](../getting-started/first-app.md) does.

```python
import asyncio

from quadkit.web.server import run_server_async


async def main() -> None:
    app = create_app()
    await run_server_async(app, port=8000)


asyncio.run(main())
```

## Async in tests

The test harness is async in the same shape as the framework: tests are
async functions, the bed's context manager is async, and `pytest-asyncio`
ships with `quadkit-testing`. Mark tests with `@pytest.mark.asyncio`
unless your project sets asyncio auto-mode — see
[testing](../getting-started/testing.md).

---

Backtracking pointers:

- [Lifecycle](./lifecycle.md) — the start/stop sequence being awaited.
- [Modules](./modules.md) — what gets assembled before any of this runs.
