"""Forbidden responses must resolve their factory from the current request."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.responses import Response

from quadkit.auth.config import AuthMiddlewareConfig
from quadkit.auth.models.user import User
from quadkit.auth.web.middleware.auth import AuthMiddleware


@pytest.mark.parametrize("policy", ["roles_required", "permissions_required"])
async def test_forbidden_response_receives_current_request(monkeypatch, policy):
    provider = SimpleNamespace(
        cache_service=None,
        has_any_role=lambda *_: False,
        has_any_permission=lambda *_: False,
    )
    middleware = AuthMiddleware(
        provider, AuthMiddlewareConfig(**{policy: ["required"]})
    )
    middleware.authenticate_request = AsyncMock(
        return_value=User(user_id="fixture", email="local@example.invalid")
    )
    middleware.response_handler.forbidden_response = AsyncMock(
        return_value=Response(status_code=403)
    )
    middleware.set_app(AsyncMock())
    monkeypatch.setattr(
        "quadkit.di.resolution.context.get_async_resolver", lambda _: None
    )
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/private",
        "headers": [],
        "query_string": b"",
        "scheme": "http",
        "server": ("test", 80),
    }
    send = AsyncMock()
    await middleware(scope, AsyncMock(), send)
    kwargs = middleware.response_handler.forbidden_response.await_args.kwargs
    assert kwargs["request"].scope is scope
    assert send.await_args_list[0].args[0]["status"] == 403
    middleware.app.assert_not_awaited()
