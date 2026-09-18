"""Logging, CORS, CSRF, middleware, and exception-filter protocols."""

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



class TestHttpRequestLoggerProtocol:
    """Tests for HttpRequestLoggerProtocol."""

    @pytest.mark.parametrize(
        ("method", "path", "status_code", "duration_ms"),
        [
            ("GET", "/api/users", 200, 45.2),
            ("POST", "/api/users", 201, 120.5),
            ("DELETE", "/api/users/1", 204, 30.1),
        ],
    )
    async def test_has_log_request_method(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        """Test protocol has log_request async method."""

        class Logger:
            async def log_request(
                self,
                method: str,
                path: str,
                status_code: int,
                duration_ms: float,
                request_id: str | None = None,
                **metadata: Any,
            ) -> None:
                pass

        logger = Logger()
        assert isinstance(logger, HttpRequestLoggerProtocol)
        await logger.log_request(method, path, status_code, duration_ms)

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Logger:
            async def log_request(
                self,
                method: str,
                path: str,
                status_code: int,
                duration_ms: float,
                request_id: str | None = None,
                **metadata: Any,
            ) -> None:
                pass

        assert isinstance(Logger(), HttpRequestLoggerProtocol)


class TestCORSPolicyProtocol:
    """Tests for CORSPolicyProtocol."""

    def test_has_is_origin_allowed_method(self) -> None:
        """Test protocol has is_origin_allowed method."""

        class CORS:
            def is_origin_allowed(self, origin: str) -> bool:
                return True

            def get_allowed_headers(self) -> list[str]:
                return ["content-type"]

            def get_allowed_methods(self) -> list[str]:
                return ["GET", "POST"]

            def get_max_age(self) -> int:
                return 3600

        cors = CORS()
        assert isinstance(cors, CORSPolicyProtocol)
        assert cors.is_origin_allowed("https://example.com") is True
        assert cors.get_allowed_headers() == ["content-type"]
        assert cors.get_allowed_methods() == ["GET", "POST"]
        assert cors.get_max_age() == 3600

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class CORS:
            def is_origin_allowed(self, origin: str) -> bool:
                return True

            def get_allowed_headers(self) -> list[str]:
                return []

            def get_allowed_methods(self) -> list[str]:
                return []

            def get_max_age(self) -> int:
                return 0

        assert isinstance(CORS(), CORSPolicyProtocol)


class TestBackgroundTaskRunnerProtocol:
    """Tests for BackgroundTaskRunnerProtocol."""

    def test_has_add_task_method(self) -> None:
        """Test protocol has add_task method."""

        class Runner:
            def add_task(
                self,
                func: Any,
                *args: Any,
                **kwargs: Any,
            ) -> None:
                pass

        runner = Runner()
        assert isinstance(runner, BackgroundTaskRunnerProtocol)

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Runner:
            def add_task(
                self,
                func: Any,
                *args: Any,
                **kwargs: Any,
            ) -> None:
                pass

        assert isinstance(Runner(), BackgroundTaskRunnerProtocol)


class TestCSRFProtectionProtocol:
    """Tests for CSRFProtectionProtocol."""

    def test_has_required_methods(self) -> None:
        """Test protocol has all required CSRF methods."""

        class CSRF:
            def generate_token(self, session_id: str) -> str:
                return "token123"

            def validate_token(self, token: str, session_id: str) -> bool:
                return True

            def get_cookie_name(self) -> str:
                return "csrf_token"

            def get_header_name(self) -> str:
                return "X-CSRF-Token"

        csrf = CSRF()
        assert isinstance(csrf, CSRFProtectionProtocol)
        assert csrf.generate_token("sess1") == "token123"
        assert csrf.validate_token("token", "sess1") is True
        assert csrf.get_cookie_name() == "csrf_token"
        assert csrf.get_header_name() == "X-CSRF-Token"

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class CSRF:
            def generate_token(self, session_id: str) -> str:
                return ""

            def validate_token(self, token: str, session_id: str) -> bool:
                return False

            def get_cookie_name(self) -> str:
                return ""

            def get_header_name(self) -> str:
                return ""

        assert isinstance(CSRF(), CSRFProtectionProtocol)


class TestWebMiddlewareProtocol:
    """Tests for WebMiddlewareProtocol."""

    @pytest.mark.asyncio
    async def test_has_call_method(self) -> None:
        """Test protocol has __call__ method."""

        class Middleware:
            async def __call__(
                self,
                request: Any,
                call_next: Any,
            ) -> Any:
                return await call_next(request)

        middleware = Middleware()
        assert isinstance(middleware, WebMiddlewareProtocol)

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Middleware:
            async def __call__(
                self,
                request: Any,
                call_next: Any,
            ) -> Any:
                pass

        assert isinstance(Middleware(), WebMiddlewareProtocol)


class TestExceptionFilterProtocol:
    """Tests for ExceptionFilterProtocol."""

    def test_has_required_methods(self) -> None:
        """Test protocol has can_handle and handle methods."""

        class Filter:
            def can_handle(self, exc: Exception) -> bool:
                return isinstance(exc, ValueError)

            def handle(self, exc: Exception, request: Any) -> Any:
                return {"error": str(exc)}

        filter_inst = Filter()
        assert isinstance(filter_inst, ExceptionFilterProtocol)
        assert filter_inst.can_handle(ValueError("test")) is True
        assert filter_inst.can_handle(TypeError("test")) is False

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Filter:
            def can_handle(self, exc: Exception) -> bool:
                return False

            def handle(self, exc: Exception, request: Any) -> Any:
                return None

        assert isinstance(Filter(), ExceptionFilterProtocol)


