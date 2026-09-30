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


class _FakeRoute:
    """Minimal stand-in for a Starlette route: all the reorder pass reads."""

    def __init__(self, path: str) -> None:
        self.path = path

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{self.path}>"


class _FakeApp:
    def __init__(self, paths: list[str]) -> None:
        self.router = MagicMock()
        self.router.routes = [_FakeRoute(p) for p in paths]


def test_static_routes_win_across_controllers_too() -> None:
    """The collision a generated project actually has.

    The per-controller sort above only orders routes *within* one controller.
    A generated module splits them: the CRUD controller emits
    ``/catalogs/{item_id}`` and the search controller emits
    ``/catalogs/search``, so whichever controller registered first won — and
    the CRUD one does. The search endpoint appeared in the OpenAPI document
    and answered ``404 Catalog not found: search``, having read the literal
    word as an id.

    One stable pass over the finished table fixes every such pair at once.
    """
    app = _FakeApp(
        [
            "/catalogs",
            "/catalogs/{item_id}",  # registered first by the CRUD controller
            "/catalogs/search",  # a different controller, so it lost
            "/medias/{item_id}",
            "/medias/recent",
        ]
    )

    WebRouterManager._reorder_static_before_params(app)

    order = [r.path for r in app.router.routes]
    assert order.index("/catalogs/search") < order.index("/catalogs/{item_id}")
    assert order.index("/medias/recent") < order.index("/medias/{item_id}")
    # Stable: the static paths keep the order they were registered in, so a
    # reorder cannot quietly reshuffle unrelated routes.
    assert order[:3] == ["/catalogs", "/catalogs/search", "/medias/recent"]


def test_reorder_is_a_no_op_without_a_router() -> None:
    # Some hosts pass an app object with no router (tests, ASGI shims). The
    # pass must not be the thing that breaks them.
    WebRouterManager._reorder_static_before_params(object())
