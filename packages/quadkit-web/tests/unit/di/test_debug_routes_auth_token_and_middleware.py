import pytest
from starlette.testclient import TestClient


class AdminAuthMiddleware:
    def __init__(self, token):
        self.token = token


from quadkit.app.base import Application
from quadkit.web.config import WebConfig, RateLimitConfig
from quadkit.web.di.provider import WebProvider
from quadkit.web.routing.controllers import Controller
from quadkit.web import get


class TokenController(Controller):
    @get("/x")
    def x(self):
        return {"ok": True}


@pytest.mark.asyncio
async def test_debug_routes_token_header_required():
    app = Application(name="test-app")
    web = WebProvider(
        controllers=[TokenController],
        web_config=WebConfig(
            rate_limit=RateLimitConfig(enabled=False),
            debug_routes=True,
            debug_routes_token="s3cr3t",
        ),
    )

    await web.register(app.container)
    await web.boot(app.container)

    with TestClient(web.starlette) as client:
        r = client.get("/debug/routes")
        assert r.status_code == 403

        r2 = client.get("/debug/routes", headers={"X-Debug-Token": "s3cr3t"})
        assert r2.status_code == 200

    await web.shutdown()


@pytest.mark.asyncio
async def test_debug_routes_require_middleware_present_allows_access():
    """When debug_routes_require_middleware names a registered middleware, access is granted."""
    app = Application(name="test-app")
    web = WebProvider(
        controllers=[TokenController],
        web_config=WebConfig(
            debug_routes=True,
            debug_routes_token="dummy-token",  # satisfies WebProvider validation
            debug_routes_require_middleware="AdminAuthMiddleware",
            rate_limit=RateLimitConfig(enabled=False),
        ),
        middleware=[AdminAuthMiddleware("s3cr3t")],
    )

    await web.register(app.container)
    await web.boot(app.container)

    with TestClient(web.starlette) as client:
        # Middleware IS registered → access is granted
        r = client.get("/debug/routes")
        assert r.status_code == 200

    await web.shutdown()


@pytest.mark.asyncio
async def test_debug_routes_require_middleware_absent_returns_404():
    """When debug_routes_require_middleware names an unregistered middleware, 404 is returned."""
    app = Application(name="test-app")
    web = WebProvider(
        controllers=[TokenController],
        web_config=WebConfig(
            debug_routes=True,
            debug_routes_token="dummy-token",  # satisfies WebProvider validation
            debug_routes_require_middleware="MissingMiddleware",
            rate_limit=RateLimitConfig(enabled=False),
        ),
    )

    await web.register(app.container)
    await web.boot(app.container)

    with TestClient(web.starlette) as client:
        r = client.get("/debug/routes")
        assert r.status_code == 404

    await web.shutdown()
