"""Feature tour: lifecycle hooks without middleware.

Bind a `HookRegistry` once and every HTTP request emits canonical, typed
hook payloads (`WebRequestReceivedHook`/`WebResponsePreparedHook`) through
the app's hook flow — no hand-wired ASGI middleware in application code.
Handlers run in `HookPriority` order; a failing handler is logged and never
breaks the request or its sibling handlers.
"""

import pytest

from quadkit import Application
from quadkit.contracts.core import HookRegistryProtocol
from quadkit.hooks import HookPriority, HookRegistry
from quadkit.testing import WebTestBed
from quadkit.web import Controller, WebModule, get
from quadkit.web.hooks import WebRequestReceivedHook, WebResponsePreparedHook


class HealthController(Controller):
    @get("/healthz")
    async def healthz(self) -> dict:
        return {"status": "up"}

    @get("/metrics")
    async def metrics(self) -> dict:
        return {"requests": 1}


received: list[str] = []
prepared: list[tuple[str, int]] = []
order: list[str] = []


def create_app() -> Application:
    received.clear()
    prepared.clear()
    order.clear()

    registry = HookRegistry(name="tour")

    def on_received(payload: WebRequestReceivedHook) -> None:
        received.append(f"{payload.method} {payload.path}")
        order.append("second(NORMAL)")

    def on_received_early(payload: WebRequestReceivedHook) -> None:
        order.append("first(EARLY)")

    def on_prepared(payload: WebResponsePreparedHook) -> None:
        prepared.append((payload.path, payload.status_code))

    registry.register_action("request.received", on_received)
    registry.register_action(
        "request.received", on_received_early, priority=HookPriority.EARLY
    )
    registry.register_action("response.prepared", on_prepared)

    app = Application()
    app.container.singleton(HookRegistryProtocol, factory=lambda: registry)
    app.add_module(WebModule.configure(controllers=[HealthController]))
    return app


@pytest.mark.asyncio
async def test_web_hooks_fire_in_priority_order() -> None:
    async with WebTestBed(create_app()) as bed:
        assert bed.get("/healthz").status_code == 200
        assert bed.get("/metrics").status_code == 200

    assert received == ["GET /healthz", "GET /metrics"]
    assert prepared == [("/healthz", 200), ("/metrics", 200)]
    # EARLY fires before NORMAL on every request.
    assert order == [
        "first(EARLY)",
        "second(NORMAL)",
        "first(EARLY)",
        "second(NORMAL)",
    ]
