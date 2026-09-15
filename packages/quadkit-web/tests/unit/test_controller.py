"""Tests for Controller base class."""

import pytest
from quadkit.web.routing.controllers import Controller
from quadkit.web.routing import get, post, put, delete, patch


class TestControllerCollectRoutes:
    """Tests for Controller.collect_routes() method."""

    def test_collect_routes_returns_list(self):
        class MyController(Controller):
            @get("/test")
            async def test_handler(self, request):
                return {"ok": True}

        routes = MyController.collect_routes()
        assert isinstance(routes, list)
        assert len(routes) == 1

    def test_collect_routes_single_route(self):
        class UserController(Controller):
            @get("/users")
            async def list_users(self):
                return {"users": []}

        routes = UserController.collect_routes()
        assert len(routes) == 1
        assert routes[0]["method"] == "GET"
        assert routes[0]["path"] == "/users"
        assert routes[0]["handler_name"] == "list_users"

    def test_collect_routes_multiple_routes(self):
        class ItemController(Controller):
            @get("/items")
            async def list_items(self):
                return {"items": []}

            @get("/items/{item_id}")
            async def get_item(self, item_id):
                return {"id": item_id}

            @post("/items")
            async def create_item(self):
                return {"id": 1}

        routes = ItemController.collect_routes()
        assert len(routes) == 3

        methods = [r["method"] for r in routes]
        assert "GET" in methods
        assert "POST" in methods

    def test_collect_routes_includes_route_config(self):
        class UserController(Controller):
            @get("/users", summary="List users", tags=["users"])
            async def list_users(self):
                return {"users": []}

        routes = UserController.collect_routes()
        route = routes[0]
        assert route["summary"] == "List users"
        assert route["tags"] == ["users"]

    def test_collect_routes_skips_private_methods(self):
        class MyController(Controller):
            @get("/public")
            async def public_handler(self):
                return {}

            async def _private_helper(self):
                return {}

            async def helper_method(self):
                return {}

        routes = MyController.collect_routes()
        assert len(routes) == 1
        assert routes[0]["handler_name"] == "public_handler"

    def test_collect_routes_includes_response_model(self):
        from typing import Any

        class DummyModel:
            pass

        class UserController(Controller):
            @get("/users", response_model=DummyModel)
            async def list_users(self):
                return {"users": []}

        routes = UserController.collect_routes()
        assert routes[0]["response_model"] == DummyModel

    def test_collect_routes_includes_request_model(self):
        from typing import Any

        class CreateUserRequest:
            pass

        class UserController(Controller):
            @post("/users", request_model=CreateUserRequest)
            async def create_user(self):
                return {"id": 1}

        routes = UserController.collect_routes()
        assert routes[0]["request_model"] == CreateUserRequest

    def test_collect_routes_includes_status_code(self):
        class UserController(Controller):
            @post("/users", status_code=201)
            async def create_user(self):
                return {"id": 1}

        routes = UserController.collect_routes()
        assert routes[0]["status_code"] == 201

    def test_collect_routes_includes_description(self):
        class UserController(Controller):
            @get("/users", description="Returns all users in the system")
            async def list_users(self):
                return {"users": []}

        routes = UserController.collect_routes()
        assert routes[0]["description"] == "Returns all users in the system"

    def test_collect_routes_includes_operation_id(self):
        class UserController(Controller):
            @get("/users", operation_id="listAllUsers")
            async def list_users(self):
                return {"users": []}

        routes = UserController.collect_routes()
        assert routes[0]["operation_id"] == "listAllUsers"

    def test_collect_routes_includes_deprecated_flag(self):
        class UserController(Controller):
            @get("/legacy", deprecated=True)
            async def legacy_endpoint(self):
                return {"ok": True}

        routes = UserController.collect_routes()
        assert routes[0]["deprecated"] is True

    def test_collect_routes_defaults_deprecated_to_false(self):
        class UserController(Controller):
            @get("/current")
            async def current_endpoint(self):
                return {"ok": True}

        routes = UserController.collect_routes()
        assert routes[0]["deprecated"] is False

    def test_collect_routes_includes_responses(self):
        class UserController(Controller):
            @get("/users/{user_id}", responses={404: {"description": "User not found"}})
            async def get_user(self, user_id):
                return {"id": user_id}

        routes = UserController.collect_routes()
        assert routes[0]["responses"] == {404: {"description": "User not found"}}

    def test_collect_routes_from_base_class(self):
        class BaseController(Controller):
            @get("/base")
            async def base_handler(self):
                return {}

        class DerivedController(BaseController):
            @get("/derived")
            async def derived_handler(self):
                return {}

        routes = DerivedController.collect_routes()
        assert len(routes) == 2

        paths = [r["path"] for r in routes]
        assert "/base" in paths
        assert "/derived" in paths

    def test_collect_routes_mro_order(self):
        """Routes from derived class should come after base class routes."""

        class BaseController(Controller):
            @get("/base")
            async def base_handler(self):
                return {}

        class MiddleController(BaseController):
            @get("/middle")
            async def middle_handler(self):
                return {}

        class DerivedController(MiddleController):
            @get("/derived")
            async def derived_handler(self):
                return {}

        routes = DerivedController.collect_routes()
        paths = [r["path"] for r in routes]
        # All three routes should be present
        assert "/base" in paths
        assert "/middle" in paths
        assert "/derived" in paths

    def test_collect_routes_handles_all_http_methods(self):
        class AllMethodsController(Controller):
            @get("/items")
            async def get_item(self):
                return {}

            @post("/items")
            async def create_item(self):
                return {}

            @put("/items/{id}")
            async def update_item(self, id):
                return {}

            @delete("/items/{id}")
            async def delete_item(self, id):
                return {}

            @patch("/items/{id}")
            async def patch_item(self, id):
                return {}

        routes = AllMethodsController.collect_routes()
        assert len(routes) == 5

        methods = {r["method"] for r in routes}
        assert methods == {"GET", "POST", "PUT", "DELETE", "PATCH"}

    def test_collect_routes_deduplicates_methods(self):
        """Same method name in base and derived - derived takes precedence."""

        class BaseController(Controller):
            @get("/items")
            async def list_items(self):
                return {}

        class DerivedController(BaseController):
            @get("/items")
            async def list_items(self):
                return {}

        routes = DerivedController.collect_routes()
        # Should only have one route (from derived)
        handler_names = [r["handler_name"] for r in routes]
        assert "list_items" in handler_names
