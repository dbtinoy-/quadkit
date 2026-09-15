"""Tests for web constants."""

import pytest
from quadkit.web.constants import (
    ENV_PREFIX,
    ENV_NESTED_DELIMITER,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_WORKERS,
    DEFAULT_RELOAD,
    DEFAULT_HEALTH_PATH,
    DEFAULT_DOCS_PATH,
    DEFAULT_OPENAPI_PATH,
    DEFAULT_DEBUG_ROUTES_PATH,
    DEFAULT_CORS_ALLOW_ORIGINS,
    DEFAULT_RATE_LIMIT_REQUESTS,
    DEFAULT_RATE_LIMIT_WINDOW,
    DEFAULT_PAGE_SIZE,
    DEFAULT_MAX_PAGE_SIZE,
)


class TestWebEnvConstants:
    def test_env_prefix(self) -> None:
        assert ENV_PREFIX == "QK_WEB__"

    def test_env_nested_delimiter(self) -> None:
        assert ENV_NESTED_DELIMITER == "__"


class TestServerDefaults:
    def test_default_host(self) -> None:
        assert DEFAULT_HOST == "0.0.0.0"

    def test_default_port(self) -> None:
        assert DEFAULT_PORT == 8000

    def test_default_workers(self) -> None:
        assert DEFAULT_WORKERS == 1

    def test_default_reload(self) -> None:
        assert DEFAULT_RELOAD is False


class TestRoutePaths:
    def test_health_path(self) -> None:
        assert DEFAULT_HEALTH_PATH == "/health"

    def test_docs_path(self) -> None:
        assert DEFAULT_DOCS_PATH == "/docs"

    def test_openapi_path(self) -> None:
        assert DEFAULT_OPENAPI_PATH == "/openapi.json"

    def test_debug_routes_path(self) -> None:
        assert DEFAULT_DEBUG_ROUTES_PATH == "/_debug/routes"


class TestSecurityDefaults:
    def test_cors_allow_origins(self) -> None:
        assert DEFAULT_CORS_ALLOW_ORIGINS == ("*",)

    def test_rate_limit_requests(self) -> None:
        assert DEFAULT_RATE_LIMIT_REQUESTS == 100

    def test_rate_limit_window(self) -> None:
        assert DEFAULT_RATE_LIMIT_WINDOW == 60


class TestPaginationDefaults:
    def test_page_size(self) -> None:
        assert DEFAULT_PAGE_SIZE == 20

    def test_max_page_size(self) -> None:
        assert DEFAULT_MAX_PAGE_SIZE == 100
