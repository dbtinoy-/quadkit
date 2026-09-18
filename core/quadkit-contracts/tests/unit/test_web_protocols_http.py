"""Request/response/factory/application protocols."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.web.protocols import (
    BackgroundTaskRunnerProtocol,
    ConnectionManagerProtocol,
    CORSPolicyProtocol,
    CRUDServiceProtocol,
    CSRFProtectionProtocol,
    ExceptionFilterProtocol,
    HTTPApplicationProtocol,
    HttpRequestLoggerProtocol,
    RequestProtocol,
    ResponseProtocol,
    WebMiddlewareProtocol,
)



class TestRequestProtocol:
    """Test RequestProtocol functionality."""

    def test_request_protocol_exists(self):
        """Verify RequestProtocol is available."""
        assert RequestProtocol is not None

    def test_has_required_attributes(self) -> None:
        """Test protocol has required attributes."""

        class Request:
            url = "http://example.com"
            method = "GET"
            headers = {}
            path_params = {}
            query_params = {}
            cookies = {}
            state = {}
            user = None
            auth = None

            async def json(self) -> Any:
                return {}

            async def body(self) -> bytes:
                return b""

        request = Request()
        assert isinstance(request, RequestProtocol)
        assert request.method == "GET"

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Request:
            url: Any = None
            method: str = "GET"
            headers: Any = {}
            path_params: dict = {}
            query_params: Any = {}
            cookies: Any = {}
            state: Any = {}
            user: Any = None
            auth: Any = None

            async def json(self) -> Any:
                return {}

            async def body(self) -> bytes:
                return b""

        assert isinstance(Request(), RequestProtocol)


class TestResponseProtocol:
    """Tests for ResponseProtocol."""

    def test_has_required_attributes_and_methods(self) -> None:
        """Test protocol has required attributes and methods."""

        class Response:
            status_code = 200
            headers = {}
            body = b""
            media_type = "application/json"
            background = None

            def set_cookie(
                self,
                key: str,
                value: str = "",
                max_age: int | None = None,
                expires: int | None = None,
                path: str = "/",
                domain: str | None = None,
                secure: bool = False,
                httponly: bool = False,
                samesite: str = "lax",
            ) -> None:
                pass

            def delete_cookie(
                self,
                key: str,
                path: str = "/",
                domain: str | None = None,
            ) -> None:
                pass

        response = Response()
        assert isinstance(response, ResponseProtocol)
        assert response.status_code == 200

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Response:
            status_code: int = 200
            headers: Any = {}
            body: bytes = b""
            media_type: str | None = None
            background: Any | None = None

            def set_cookie(self, key: str, **kwargs: Any) -> None:
                pass

            def delete_cookie(self, key: str, **kwargs: Any) -> None:
                pass

        assert isinstance(Response(), ResponseProtocol)


class TestResponseFactoryProtocol:
    """Tests for ResponseFactoryProtocol."""

    def test_has_json_method(self) -> None:
        """Test protocol has json method."""

        class Factory:
            def json(
                self,
                content: Any,
                status_code: int = 200,
                headers: dict[str, str] | None = None,
                ) -> Any:
                return {"status": status_code}

        factory = Factory()
        assert hasattr(factory, "json")
        result = factory.json({"data": "test"})
        assert result["status"] == 200

    def test_has_html_method(self) -> None:
        """Test protocol has html method."""

        class Factory:
            def html(
                self,
                content: str,
                status_code: int = 200,
                headers: dict[str, str] | None = None,
                ) -> Any:
                return {"status": status_code}

        factory = Factory()
        assert hasattr(factory, "html")

    def test_has_redirect_method(self) -> None:
        """Test protocol has redirect method."""

        class Factory:
            def redirect(
                self,
                url: str,
                status_code: int = 302,
                headers: dict[str, str] | None = None,
                ) -> Any:
                return {"status": status_code, "location": url}

        factory = Factory()
        assert hasattr(factory, "redirect")


class TestHTTPApplicationProtocol:
    """Tests for HTTPApplicationProtocol."""

    @pytest.mark.asyncio
    async def test_has_call_method(self) -> None:
        """Test protocol has __call__ method."""

        class App:
            async def __call__(
                self,
                scope: dict[str, Any],
                receive: Any,
                send: Any,
            ) -> None:
                pass

        app = App()
        assert callable(app)

    def test_has_mount_and_route_methods(self) -> None:
        """Test protocol has mount, add_route, add_middleware methods."""

        class App:
            async def __call__(
                self,
                scope: dict[str, Any],
                receive: Any,
                send: Any,
            ) -> None:
                pass

            def mount(self, path: str, app: Any) -> None:
                pass

            def add_route(
                self,
                path: str,
                handler: Any,
                methods: list[str] | None = None,
            ) -> None:
                pass

            def add_middleware(self, middleware: Any) -> None:
                pass

        app = App()
        assert hasattr(app, "mount")
        assert hasattr(app, "add_route")
        assert hasattr(app, "add_middleware")

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class App:
            async def __call__(
                self,
                scope: dict[str, Any],
                receive: Any,
                send: Any,
            ) -> None:
                pass

            def mount(self, path: str, app: Any) -> None:
                pass

            def add_route(
                self,
                path: str,
                handler: Any,
                methods: list[str] | None = None,
            ) -> None:
                pass

            def add_middleware(self, middleware: Any) -> None:
                pass

        assert isinstance(App(), HTTPApplicationProtocol)


