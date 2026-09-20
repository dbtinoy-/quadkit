"""Integration tests for quadkit-web"""

from unittest.mock import Mock

import pytest
from starlette.requests import Request

from quadkit.web import JSONResponse, get
from quadkit.web.middleware.cors import CORSMiddleware
from quadkit.web.routing.controllers import Controller
from quadkit.web.routing.router import Router
from quadkit.web.security.config import CORSConfig
from quadkit.web.security.guards import AuthGuard


class TestWebIntegration:
    """Integration tests for web functionality"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_request_flow(self, test_bed):
        """Test complete request flow from routing to response"""
        # Get router from container
        router = await test_bed.resolve(Router)

        # The router should be available and functional
        assert router is not None
        assert hasattr(router, "routes")
        assert isinstance(router.routes, list)

        # Check that the router can create endpoints
        assert hasattr(router, "_create_endpoint")

        # Test that basic router functionality works
        # (In a real scenario, controllers would be registered by WebProvider)
        routes = router.routes
        assert isinstance(routes, list)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_middleware_integration(self, test_bed):
        """Test CORS middleware can be instantiated with the ASGI API."""
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route
        from starlette.testclient import TestClient

        async def homepage(request):
            return JSONResponse({"ok": True})

        config = CORSConfig(allow_origins=["http://localhost:3000"])
        inner = Starlette(routes=[Route("/", homepage)])
        cors_middleware = CORSMiddleware(inner, config=config)
        client = TestClient(cors_middleware)
        response = client.get("/", headers={"origin": "http://localhost:3000"})
        assert response.status_code == 200

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_security_integration(self, test_bed):
        """Test security integration"""
        # Create auth guard
        auth_guard = AuthGuard()

        # Mock authenticated request.  ``Mock(spec=Request)`` is required:
        # an unspecced Mock satisfies the runtime-checkable
        # ``ExecutionContextProtocol`` via attribute auto-creation, which
        # diverts the guard down the ``context.request`` branch and makes
        # the unauthenticated assertion fail.
        request = Mock(spec=Request)
        request.state.user = Mock()
        request.state.user.is_authenticated = True

        can_activate = await auth_guard.can_activate(request)
        assert can_activate is True

        # Mock unauthenticated request
        request.state.user = None
        can_activate = await auth_guard.can_activate(request)
        assert can_activate is False

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_controller_with_dependencies(self, test_bed):
        """Test controller with dependency injection"""
        # Mock a service
        mock_service = Mock()

        async def get_data():
            return {"data": "from service"}

        mock_service.get_data = Mock(side_effect=get_data)

        class TestController(Controller):
            def __init__(self, service=None):
                self.service = service or Mock()

            @get("/api/data")
            async def get_data(self):
                return await self.service.get_data()

        # Create controller with injected service
        controller = TestController(mock_service)

        # Test the method
        result = await controller.get_data()
        assert result == {"data": "from service"}

        # Verify service was called
        mock_service.get_data.assert_called_once()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_error_handling(self, test_bed):
        """Test error handling through the system"""
        from quadkit.web.exceptions import NotFoundError
        from quadkit.web.filters import DefaultExceptionFilter

        # Create exception filter
        filter_instance = DefaultExceptionFilter()

        # Create mock request
        request = Mock()
        request.method = "GET"
        request.url = "/not-found"

        # Create not found exception
        exception = NotFoundError(detail="Resource not found")

        # Handle exception
        response = await filter_instance.handle(exception, request)

        # Verify proper error response
        assert response.status_code == 404
        response_body = response.body.decode()
        assert "Resource not found" in response_body

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_response_types_integration(self, test_bed):
        """Test different response types work together"""
        from quadkit.web import HTMLResponse, RedirectResponse

        # Test JSON response
        json_resp = JSONResponse({"type": "json"})
        assert json_resp.media_type == "application/json"

        # Test HTML response
        html_resp = HTMLResponse("<h1>HTML</h1>")
        assert html_resp.media_type == "text/html"

        # Test redirect response
        redirect_resp = RedirectResponse("/new-location")
        assert redirect_resp.status_code == 307
        assert redirect_resp.headers["location"] == "/new-location"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_routing_with_parameters(self, test_bed):
        """Test routing with path and query parameters"""
        router = await test_bed.resolve(Router)

        # Test that router can handle route creation
        assert router is not None
        assert hasattr(router, "add_route")

        # Test adding a route manually
        def test_handler():
            return {"test": True}

        router.add_route("GET", "/test", test_handler)

        # Verify route was added
        assert len(router.routes) > 0
        route = router.routes[-1]
        assert route.method == "GET"
        assert route.path == "/test"
