"""Unit tests for routing domain"""
import pytest

from quadkit.web.routing.controllers import Controller
from quadkit.web import (
    delete,
    get,
    head,
    options,
    patch,
    post,
    put,
    trace,
)
from quadkit.web.routing.registry import RouteRegistry
from quadkit.web.routing.router import Router
from quadkit.web.types import HTTPMethod


class TestController:
    """Test base controller functionality"""

    def test_controller_creation(self):
        """Test basic controller instantiation"""
        controller = Controller()
        assert controller is not None

    def test_controller_with_prefix(self):
        """Test controller with route prefix"""

        class TestController(Controller):
            prefix = "/api"

        controller = TestController()
        assert controller.prefix == "/api"


class TestHTTPDecorators:
    """Test HTTP method decorators"""

    def test_get_decorator(self):
        """Test GET decorator"""

        @get("/users")
        def get_users():
            return {"users": []}

        assert hasattr(get_users, "_route_config")
        assert get_users._route_config["method"] == HTTPMethod.GET
        assert get_users._route_config["path"] == "/users"

    def test_post_decorator(self):
        """Test POST decorator"""

        @post("/users")
        def create_user():
            return {"user": "created"}

        assert hasattr(create_user, "_route_config")
        assert create_user._route_config["method"] == HTTPMethod.POST

    def test_put_decorator(self):
        """Test PUT decorator"""

        @put("/users/{user_id}")
        def update_user(user_id: int):
            return {"user_id": user_id, "updated": True}

        assert hasattr(update_user, "_route_config")
        assert update_user._route_config["method"] == HTTPMethod.PUT

    def test_delete_decorator(self):
        """Test DELETE decorator"""

        @delete("/users/{user_id}")
        def delete_user(user_id: int):
            return {"user_id": user_id, "deleted": True}

        assert hasattr(delete_user, "_route_config")
        assert delete_user._route_config["method"] == HTTPMethod.DELETE

    def test_patch_decorator(self):
        """Test PATCH decorator"""

        @patch("/users/{user_id}")
        def patch_user(user_id: int):
            return {"user_id": user_id, "patched": True}

        assert hasattr(patch_user, "_route_config")
        assert patch_user._route_config["method"] == HTTPMethod.PATCH

    def test_head_decorator(self):
        """Test HEAD decorator"""

        @head("/health")
        def health_check():
            return {}

        assert hasattr(health_check, "_route_config")
        assert health_check._route_config["method"] == HTTPMethod.HEAD

    def test_options_decorator(self):
        """Test OPTIONS decorator"""

        @options("/users")
        def user_options():
            return {}

        assert hasattr(user_options, "_route_config")
        assert user_options._route_config["method"] == HTTPMethod.OPTIONS

    def test_trace_decorator(self):
        """Test TRACE decorator"""

        @trace("/debug")
        def debug_trace():
            return {}

        assert hasattr(debug_trace, "_route_config")
        assert debug_trace._route_config["method"] == HTTPMethod.TRACE


class TestRouter:
    """Test router functionality"""

    @pytest.fixture
    def router(self):
        """Create a router instance"""
        return Router()

    def test_router_creation(self, router):
        """Test router instantiation"""
        assert router is not None
        assert hasattr(router, "routes")
        assert isinstance(router.routes, list)

    def test_add_route(self, router):
        """Test adding a route to the router"""

        def test_handler():
            return {"test": True}

        # Add route
        router.add_route("GET", "/test", test_handler)

        # Check route was added
        assert len(router.routes) == 1

        # Check the route structure
        route = router.routes[0]
        assert route.method == "GET"
        assert route.path == "/test"
        assert route.handler == test_handler

    def test_router_controller_cache(self, router):
        """Test that router caches controller instances"""
        class DummyController(Controller):
            pass

        class MockContainer:
            def __init__(self):
                self.instances = {}
            def is_singleton(self, cls):
                return True
            def resolve(self, cls):
                if cls not in self.instances:
                    self.instances[cls] = cls()
                return self.instances[cls]
                
        router._container = MockContainer()
        router._preload_controller(DummyController)

        # Should be cached
        assert DummyController in router._controller_cache
        c1 = router._controller_cache[DummyController]
        assert isinstance(c1, DummyController)
        
        # Second preload should not replace the instance
        c1.marker = True
        router._preload_controller(DummyController)
        assert getattr(router._controller_cache[DummyController], "marker", False) is True


class TestRouteRegistry:
    """Test route registry functionality"""

    @pytest.fixture
    def registry(self):
        """Create a route registry instance"""
        return RouteRegistry()

    def test_registry_creation(self, registry):
        """Test registry instantiation"""
        assert registry is not None
        assert hasattr(registry, "_items")
        assert isinstance(registry._items, dict)

    def test_register_route(self, registry):
        """Test registering a route"""

        class TestController(Controller):
            @get("/test")
            def test_handler(self):
                return {"registered": True}

        registry.register_controller(TestController)

        # Check route was registered
        routes = registry.get_all_routes()
        assert "/test" in routes
        assert "GET" in routes["/test"]
        route_info = routes["/test"]["GET"]
        assert route_info["controller"] == TestController
        assert route_info["handler_name"] == "test_handler"

    def test_get_routes(self, registry):
        """Test getting all routes"""

        class Controller1(Controller):
            @get("/route1")
            def handler1(self):
                return {"route": 1}

        class Controller2(Controller):
            @post("/route2")
            def handler2(self):
                return {"route": 2}

        registry.register_controller(Controller1)
        registry.register_controller(Controller2)

        routes = registry.get_all_routes()
        assert len(routes) == 2
        assert "/route1" in routes
        assert "/route2" in routes

    def test_find_route(self, registry):
        """Test finding a route by path and method"""

        class TestController(Controller):
            @get("/test")
            def test_handler(self):
                return {"found": True}

        registry.register_controller(TestController)

        route = registry.find_route("/test", "GET")
        assert route is not None
        assert route["controller"] == TestController
        assert route["handler_name"] == "test_handler"

    def test_find_route_not_found(self, registry):
        """Test finding a non-existent route"""
        route = registry.find_route("/nonexistent", "GET")
        assert route is None
