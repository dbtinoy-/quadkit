"""Route registration captures origin metadata in debug mode."""

from quadkit.web import get
from quadkit.web.routing.controllers import Controller
from quadkit.web.routing.registry import RouteRegistry


def test_registry_stores_registration_metadata():
    registry = RouteRegistry()
    registry._debug = True

    class C(Controller):
        @get("/meta/{item_id}")
        async def get_item(self):
            return {"id": "1"}

    try:
        registry.register_controller(C)
        routes = registry.get_all_routes()

        assert "/meta/{item_id}" in routes
        route_info = routes["/meta/{item_id}"]["GET"]
        assert route_info["controller"] is C
        assert route_info["handler_name"] == "get_item"
        # Debug mode captures registration origin metadata.
        assert route_info["registered_file"] is not None
        assert route_info["registered_line"] is not None
    finally:
        registry._debug = False


def test_registry_keeps_deprecation_metadata():
    class C(Controller):
        @get("/old", deprecated=True)
        async def old(self):
            pass

        @get("/current")
        async def current(self):
            pass

    registry = RouteRegistry()
    registry.register_controller(C)
    assert registry.supports_route_deprecated_v1 is True
    assert registry.get_all_routes()["/old"]["GET"]["deprecated"] is True
    assert registry.get_all_routes()["/current"]["GET"]["deprecated"] is False
