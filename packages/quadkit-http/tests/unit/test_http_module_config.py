"""HTTP exceptions, constants, configs, and connection-pool tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.http.config import ConnectionPoolConfig, HTTPClientConfig
from quadkit.http.constants import (
    CONTENT_TYPE_JSON,
    DEFAULT_ENCODING,
    DEFAULT_MAX_CONNECTIONS,
    DEFAULT_TIMEOUT,
    GET,
    POST,
)
from quadkit.http.exceptions import (
    HTTPCircuitOpenError,
    HTTPClientError,
    HTTPConnectionError,
    HTTPInterceptorError,
    HTTPRetryExhaustedError,
    HTTPTimeoutError,
)
from quadkit.http.lib import (
    build_url,
    extract_json_type,
    format_timeout,
    merge_headers,
    parse_headers,
    parse_url_parts,
)
from quadkit.http.pool import ConnectionPool
from quadkit.http.types import RequestContext, ResponseContext
from quadkit.http.validation import (
    validate_host,
    validate_port,
    validate_positive_int,
    validate_timeout,
    validate_url,
)

# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------




class TestExceptionHierarchy:
    """Verify the exception hierarchy so callers can catch at any level."""

    def test_all_http_errors_inherit_from_http_error(self) -> None:
        from quadkit.contracts.exceptions import InfrastructureError

        for cls in (
            HTTPConnectionError,
            HTTPTimeoutError,
            HTTPInterceptorError,
            HTTPCircuitOpenError,
            HTTPRetryExhaustedError,
        ):
            assert issubclass(cls, HTTPClientError)
            assert issubclass(cls, InfrastructureError)

    def test_http_error_is_infrastructure_error(self) -> None:
        from quadkit.contracts.exceptions import InfrastructureError

        assert issubclass(HTTPClientError, InfrastructureError)

    def test_error_message_preserved(self) -> None:
        err = HTTPClientError("bad things happened")
        assert "bad things happened" in str(err)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_method_names(self) -> None:
        assert GET == "GET"
        assert POST == "POST"

    def test_defaults(self) -> None:
        assert DEFAULT_MAX_CONNECTIONS == 10
        assert DEFAULT_TIMEOUT == 30.0

    def test_content_type_json(self) -> None:
        assert "json" in CONTENT_TYPE_JSON.lower()

    def test_encoding(self) -> None:
        assert DEFAULT_ENCODING == "utf-8"


# ---------------------------------------------------------------------------
# Config dataclasses
# ---------------------------------------------------------------------------


class TestConnectionPoolConfig:
    def test_defaults(self) -> None:
        cfg = ConnectionPoolConfig()
        assert cfg.max_connections == DEFAULT_MAX_CONNECTIONS
        assert cfg.timeout == DEFAULT_TIMEOUT
        assert cfg.force_close is False

    def test_custom_values(self) -> None:
        cfg = ConnectionPoolConfig(max_connections=50, timeout=60.0, force_close=True)
        assert cfg.max_connections == 50
        assert cfg.timeout == 60.0
        assert cfg.force_close is True


class TestHTTPClientConfig:
    def test_defaults(self) -> None:
        cfg = HTTPClientConfig()
        assert isinstance(cfg.pool, ConnectionPoolConfig)

    def test_custom_pool(self) -> None:
        pool_cfg = ConnectionPoolConfig(max_connections=100)
        cfg = HTTPClientConfig(pool=pool_cfg)
        assert cfg.pool.max_connections == 100


# ---------------------------------------------------------------------------
# Connection pool
# ---------------------------------------------------------------------------


class TestConnectionPool:
    @pytest.mark.asyncio
    async def test_start_creates_session(self) -> None:
        pool = ConnectionPool()
        assert not pool.is_started()
        await pool.start()
        assert pool.is_started()
        assert pool._session is not None
        await pool.stop()

    @pytest.mark.asyncio
    async def test_stop_closes_session(self) -> None:
        pool = ConnectionPool()
        await pool.start()
        await pool.stop()
        assert not pool.is_started()
        assert pool._session is None

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self) -> None:
        pool = ConnectionPool()
        await pool.start()
        session_first = pool._session
        await pool.start()  # second call should not create another session
        assert pool._session is session_first
        await pool.stop()

    @pytest.mark.asyncio
    async def test_custom_limits_applied(self) -> None:
        pool = ConnectionPool(max_connections=50, max_connections_per_host=20)
        await pool.start()
        connector = pool._session.connector  # type: ignore[union-attr]
        assert connector.limit == 50
        assert connector.limit_per_host == 20
        await pool.stop()

    def test_defaults(self) -> None:
        pool = ConnectionPool()
        assert pool.max_connections == 10
        assert pool.max_keepalive_connections == 5
        assert pool.timeout == 30.0
        assert pool.ttl_dns_cache == 300
        assert pool.force_close is False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


