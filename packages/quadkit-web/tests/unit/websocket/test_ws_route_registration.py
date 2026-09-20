"""Test for adding WebSocket routes after provider startup"""

import pytest
from starlette.routing import WebSocketRoute, Route
from starlette.websockets import WebSocket
from starlette.applications import Starlette
from starlette.responses import JSONResponse

from quadkit.app import Application
from quadkit.web.di.provider import WebProvider


async def ws_handler(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({"message": "hello"})
    await websocket.close()


@pytest.mark.asyncio
async def test_add_websocket_route_after_startup():
    """Test adding a WebSocket route after WebProvider startup"""
    from quadkit.testing.fixtures.bed import TestEnvironment
    from quadkit.identity.di.provider import IdentityProvider
    from quadkit.observability.di.sub_providers.observability import ObservabilityProvider

    app = Application()
    provider = WebProvider()
    env = TestEnvironment(app)
    env.use_provider(IdentityProvider())
    env.use_provider(ObservabilityProvider())
    env.use_provider(provider)

    async with env.context():
        web_provider = env.get_provider("web")
        assert web_provider is not None
        assert web_provider.starlette is not None

        # Add a WebSocket route
        ws_route = WebSocketRoute("/ws", ws_handler)
        web_provider.starlette.routes.append(ws_route)

        # Verify route was added
        route_paths = [r.path for r in web_provider.starlette.routes]
        assert "/ws" in route_paths

        print(f"Routes: {route_paths}")


@pytest.mark.asyncio
async def test_get_starlette_routes():
    """Test accessing starlette routes after startup"""
    from quadkit.di import Container

    provider = WebProvider()
    container = Container()

    await provider.register(container)
    await provider.boot(container)
    
    print(f"Starlette: {provider.starlette}")
    print(f"Starlette routes: {provider.starlette.routes if provider.starlette else 'None'}")
    
    # Add a route
    ws_route = WebSocketRoute("/ws", ws_handler)
    provider.starlette.routes.append(ws_route)
    
    print(f"After adding: {[r.path for r in provider.starlette.routes]}")
