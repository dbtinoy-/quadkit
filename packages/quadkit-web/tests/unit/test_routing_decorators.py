"""Tests for HTTP route decorators (@get, @post, etc.)."""

import pytest


class TestRouteDecorator:
    """Tests for the base route() decorator."""

    def test_route_sets_route_config(self):
        from quadkit.web.routing.decorators import route

        @route("GET", "/test")
        async def handler(request):
            return {"ok": True}

        assert hasattr(handler, "_route_config")
        assert handler._route_config["method"] == "GET"
        assert handler._route_config["path"] == "/test"

    def test_route_preserves_function(self):
        from quadkit.web.routing.decorators import route

        @route("GET", "/test")
        async def handler(request):
            return {"ok": True}

        assert callable(handler)
        assert handler.__name__ == "handler"

    def test_route_accepts_additional_kwargs(self):
        from quadkit.web.routing.decorators import route

        @route(
            "POST",
            "/users",
            response_model=dict,
            status_code=201,
            summary="Create user",
            tags=["users"],
        )
        async def create_user(request):
            return {"id": 1}

        config = create_user._route_config
        assert config["method"] == "POST"
        assert config["path"] == "/users"
        assert config["response_model"] == dict
        assert config["status_code"] == 201
        assert config["summary"] == "Create user"
        assert config["tags"] == ["users"]


class TestHttpMethodDecorators:
    """Tests for HTTP method-specific decorators."""

    def test_get_decorator(self):
        from quadkit.web.routing.decorators import get

        @get("/users")
        async def list_users(request):
            return {"users": []}

        assert list_users._route_config["method"] == "GET"
        assert list_users._route_config["path"] == "/users"

    def test_post_decorator(self):
        from quadkit.web.routing.decorators import post

        @post("/users")
        async def create_user(request):
            return {"id": 1}

        assert create_user._route_config["method"] == "POST"
        assert create_user._route_config["path"] == "/users"

    def test_put_decorator(self):
        from quadkit.web.routing.decorators import put

        @put("/users/{user_id}")
        async def update_user(request, user_id):
            return {"id": user_id}

        assert update_user._route_config["method"] == "PUT"
        assert update_user._route_config["path"] == "/users/{user_id}"

    def test_delete_decorator(self):
        from quadkit.web.routing.decorators import delete

        @delete("/users/{user_id}")
        async def delete_user(request, user_id):
            return None

        assert delete_user._route_config["method"] == "DELETE"
        assert delete_user._route_config["path"] == "/users/{user_id}"

    def test_patch_decorator(self):
        from quadkit.web.routing.decorators import patch

        @patch("/users/{user_id}")
        async def patch_user(request, user_id):
            return {"id": user_id}

        assert patch_user._route_config["method"] == "PATCH"
        assert patch_user._route_config["path"] == "/users/{user_id}"

    def test_head_decorator(self):
        from quadkit.web.routing.decorators import head

        @head("/users")
        async def head_users(request):
            return None

        assert head_users._route_config["method"] == "HEAD"
        assert head_users._route_config["path"] == "/users"

    def test_options_decorator(self):
        from quadkit.web.routing.decorators import options

        @options("/users")
        async def options_users(request):
            return {"allowed": "GET, POST"}

        assert options_users._route_config["method"] == "OPTIONS"
        assert options_users._route_config["path"] == "/users"

    def test_trace_decorator(self):
        from quadkit.web.routing.decorators import trace

        @trace("/debug")
        async def trace_request(request):
            return {"traced": True}

        assert trace_request._route_config["method"] == "TRACE"
        assert trace_request._route_config["path"] == "/debug"

    def test_websocket_decorator(self):
        from quadkit.web.routing.decorators import websocket

        @websocket("/ws")
        async def ws_handler(websocket):
            await websocket.accept()

        assert ws_handler._route_config["method"] == "WEBSOCKET"
        assert ws_handler._route_config["path"] == "/ws"

    def test_decorator_preserves_function_metadata(self):
        from quadkit.web.routing import get

        @get("/users", summary="List all users", description="Returns user list")
        async def list_users(request):
            """List users endpoint."""
            return {"users": []}

        config = list_users._route_config
        assert config["summary"] == "List all users"
        assert config["description"] == "Returns user list"

    def test_decorator_with_path_parameters(self):
        from quadkit.web.routing import get, post

        @get("/users/{user_id}/posts/{post_id}")
        async def get_post(request, user_id, post_id):
            return {"user_id": user_id, "post_id": post_id}

        @post("/api/v1/{resource}/actions")
        async def action_endpoint(request, resource):
            return {"resource": resource}

        assert get_post._route_config["path"] == "/users/{user_id}/posts/{post_id}"
        assert action_endpoint._route_config["path"] == "/api/v1/{resource}/actions"

    def test_decorator_with_query_params(self):
        from quadkit.web.routing import get

        @get("/search")
        async def search(request):
            return {}

        assert search._route_config["path"] == "/search"

    def test_multiple_decorators_on_same_function(self):
        """Multiple route decorators on same function - last one wins."""
        from quadkit.web.routing.decorators import get, route

        @get("/first")
        async def handler(request):
            return {}

        # Apply another decorator
        from quadkit.web.routing import put
        decorated = put("/second")(handler)

        assert decorated._route_config["path"] == "/second"
