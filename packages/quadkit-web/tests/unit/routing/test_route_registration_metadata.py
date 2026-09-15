from quadkit.web.routing.controllers import Controller
from quadkit.web import get
from quadkit.web.routing.registry import route_registry


def test_registry_stores_registration_metadata():
    class C(Controller):
        @get("/meta-test")
        def handler(self):
            return {}

    route_registry._debug = True
    try:
        route_registry.register_controller(C)
        routes = route_registry.get_all_routes()
        assert "/meta-test" in routes
        info = routes["/meta-test"]["GET"]
        assert "registered_file" in info and info["registered_file"] is not None
        assert "registered_stack" in info and isinstance(info["registered_stack"], list)
    finally:
        route_registry._debug = False
