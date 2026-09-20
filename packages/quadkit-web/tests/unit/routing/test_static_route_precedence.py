"""Static routes must register before param routes (no shadowing).

Starlette matches first-registered-first, and ``collect_routes`` order is
alphabetical by handler name — so ``/channels/{channel_id}`` (get_channel)
would otherwise shadow ``/channels/models`` (list_channel_models).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.web.routing.manager import WebRouterManager


class _ShadowController:
    prefix = "/channels"

    @classmethod
    def collect_routes(cls) -> list[dict[str, str]]:
        # Deliberately param-first: alphabetical handler order would
        # register get_channel before list_channel_models.
        return [
            {
                "path": "/channels/{channel_id}",
                "method": "GET",
                "handler_name": "get_channel",
            },
            {
                "path": "/channels/models",
                "method": "GET",
                "handler_name": "list_channel_models",
            },
        ]


@pytest.mark.asyncio
async def test_static_routes_register_before_param_routes() -> None:
    mock_provider = MagicMock()
    mock_provider.route_registry = None
    mock_provider.controller_registry = None
    manager = WebRouterManager(provider=mock_provider)
    manager.add_route = AsyncMock()  # type: ignore[method-assign]

    await manager.register_controller_routes(_ShadowController, MagicMock())

    paths = [call.kwargs["path"] for call in manager.add_route.await_args_list]
    assert paths == ["/channels/models", "/channels/{channel_id}"]
