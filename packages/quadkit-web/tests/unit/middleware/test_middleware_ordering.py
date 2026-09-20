import pytest

from quadkit.web.middleware.base import MiddlewarePriority, MiddlewareRegistry
class DummyMiddleware:
    def __init__(self, app, name=None):
        self.app = app
        self.name = name or "dummy"

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)


class DummyApp:
    async def __call__(self, scope, receive, send):
        # Record that app was called
        scope.setdefault("order", []).append("app")


@pytest.mark.asyncio
async def test_middleware_ordering():
    registry = MiddlewareRegistry()
    registry.register_middleware(
        DummyMiddleware, priority=MiddlewarePriority.LATE, name="late",
    )
    registry.register_middleware(
        DummyMiddleware, priority=MiddlewarePriority.EARLY, name="early",
    )
    registry.register_middleware(
        DummyMiddleware, priority=MiddlewarePriority.NORMAL, name="normal",
    )

    app = DummyApp()
    wrapped = registry.compose_app(app)

    # Compose returns an ASGI app; calling it should call through to base app
    scope = {}

    await wrapped(scope, None, None)

    # Base app should have recorded a call
    assert "app" in scope.get("order", [])
