"""Redis ownership tests for the debug-routes integration.

Constructor-injection of ``debug_routes_redis_client`` and
``debug_routes_redis_client_owns`` was removed in favour of pure
container-resolution.  WebProvider never directly owns the Redis client;
ownership and lifecycle belong to whichever provider registered Redis in
the container.  The single remaining test verifies that WebProvider
does NOT call ``close()`` on a container-provided Redis client during
its own ``shutdown()`` — that responsibility stays with the container.
"""

import asyncio

from starlette.testclient import TestClient

from quadkit.app.base import Application
from quadkit.web.config import WebProviderConfig
from quadkit.web.di.provider import WebProvider
from quadkit.web.routing.controllers import Controller
from quadkit.web import get


class FakeRedis:
    def __init__(self):
        self.closed = False

    async def incr(self, key: str) -> int:
        return 1

    async def expire(self, key: str, seconds: int) -> None:
        return None

    async def close(self):
        self.closed = True


class RateController(Controller):
    @get("/x")
    def x(self):
        return {"ok": True}


def test_web_provider_does_not_close_container_redis_on_shutdown():
    """WebProvider must not close a Redis client it did not create."""
    app = Application(name="test-app")
    fake = FakeRedis()
    app.container.singleton("redis", fake)

    web = WebProvider(
        controllers=[RateController],
        provider_config=WebProviderConfig(
            debug_routes=True,
            debug_routes_rate_limit=1,
            debug_routes_rate_window_seconds=1,
        ),
    )

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(web.register(app.container))
        loop.run_until_complete(web.boot(app.container))

        client = TestClient(web.starlette)
        r1 = client.get("/debug/routes")
        assert r1.status_code == 200

    finally:
        loop.run_until_complete(web.shutdown())
        loop.close()

    # WebProvider must not call close() — the container owns the client.
    assert fake.closed is False
