"""Tests for the CockroachDB backend (asyncpg-based, DSN normalisation)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.sql.backends.cockroachdb import (
    CockroachDBConnection,
    create_cockroachdb_pool,
)
from quadkit.sql.backends.postgres import PostgresConnectionPool


class TestDefaults:
    def test_constructor_defaults(self) -> None:
        conn = CockroachDBConnection()
        assert conn.host == "localhost"
        assert conn.port == 26257
        assert conn.user == "root"
        assert conn.database == "defaultdb"
        assert conn._COMPONENT_NAME == "cockroachdb"  # noqa: SLF001

    def test_explicit_params(self) -> None:
        conn = CockroachDBConnection(host="db.internal", port=31415, user="svc")
        assert conn.host == "db.internal"
        assert conn.port == 31415
        assert conn.user == "svc"


class TestDsnNormalisation:
    def test_cockroachdb_scheme_rewritten(self) -> None:
        dsn = "cockroachdb://root@localhost:26257/defaultdb"
        assert (
            CockroachDBConnection._normalize_dsn(dsn)  # noqa: SLF001
            == "postgresql://root@localhost:26257/defaultdb"
        )

    def test_postgresql_scheme_untouched(self) -> None:
        dsn = "postgresql://u:p@h:5432/db"
        assert CockroachDBConnection._normalize_dsn(dsn) == dsn  # noqa: SLF001

    def test_other_schemes_untouched(self) -> None:
        dsn = "mysql://u@h:3306/db"
        assert CockroachDBConnection._normalize_dsn(dsn) == dsn  # noqa: SLF001


class TestCreatePool:
    async def test_server_settings_injected(self) -> None:
        captured: dict[str, object] = {}

        async def _fake_super(self, pool_kwargs: dict) -> None:
            captured.update(pool_kwargs)

        with patch.object(PostgresConnectionPool, "_create_pool", _fake_super):
            await CockroachDBConnection()._create_pool({"min_size": 1})

        settings = captured["server_settings"]
        assert isinstance(settings, dict)
        assert settings["application_name"] == "quadkit-cockroachdb"

    async def test_preserves_existing_settings(self) -> None:
        captured: dict[str, object] = {}

        async def _fake_super(self, pool_kwargs: dict) -> None:
            captured.update(pool_kwargs)

        with patch.object(PostgresConnectionPool, "_create_pool", _fake_super):
            await CockroachDBConnection()._create_pool(
                {"server_settings": {"statement_timeout": "30s"}},
            )

        settings = captured["server_settings"]
        assert settings["statement_timeout"] == "30s"
        assert settings["application_name"] == "quadkit-cockroachdb"

    async def test_instance_pool_kwargs_not_mutated(self) -> None:
        captured: dict[str, object] = {}

        async def _fake_super(self, pool_kwargs: dict) -> None:
            captured.update(pool_kwargs)

        conn = CockroachDBConnection(server_settings={"a": "1"})
        original = conn.pool_kwargs["server_settings"]
        # initialize() passes a shallow copy; the override must leave the
        # instance's stored settings untouched for retry/re-init reuse.
        with patch.object(PostgresConnectionPool, "_create_pool", _fake_super):
            await conn._create_pool(dict(conn.pool_kwargs))

        assert original == {"a": "1"}
        assert captured["server_settings"]["application_name"] == "quadkit-cockroachdb"


class TestHealthCheckComponent:
    async def test_component_replaced(self) -> None:
        conn = CockroachDBConnection()
        fake_result = HealthCheckResult(
            component="database",
            status=HealthStatus.HEALTHY,
            message="ok",
        )

        with patch.object(
            PostgresConnectionPool,
            "health_check",
            AsyncMock(return_value=fake_result),
        ) as spy:
            result = await conn.health_check(timeout=2.0)

        spy.assert_awaited_once_with(2.0)
        assert result.component == "cockroachdb"
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "ok"
        # the parent result is untouched (dataclasses.replace)
        assert fake_result.component == "database"


class TestFactory:
    def test_defaults_without_dsn(self) -> None:
        pool = create_cockroachdb_pool()
        assert pool.host == "localhost"
        assert pool.port == 26257
        assert pool.user == "root"
        assert pool.database == "defaultdb"
        assert pool.min_size == 5
        assert pool.max_size == 20

    def test_dsn_parsed(self) -> None:
        pool = create_cockroachdb_pool(
            "cockroachdb://alice:secret%40x@crdb.example.com:26257/proddb"
        )
        assert pool.host == "crdb.example.com"
        assert pool.port == 26257
        assert pool.user == "alice"
        assert pool.password == "secret@x"
        assert pool.database == "proddb"

    def test_dsn_without_port_keeps_default(self) -> None:
        pool = create_cockroachdb_pool("cockroachdb://root@h/defaultdb")
        assert pool.host == "h"
        assert pool.port == 26257
        assert pool.user == "root"
        assert pool.database == "defaultdb"

    def test_postgresql_dsn_accepted(self) -> None:
        pool = create_cockroachdb_pool("postgresql://u:p@h:7000/d")
        assert pool.host == "h"
        assert pool.port == 7000
        assert pool.database == "d"

    def test_explicit_kwargs_forwarded(self) -> None:
        pool = create_cockroachdb_pool(min_size=2, max_size=9)
        assert pool.min_size == 2
        assert pool.max_size == 9

    def test_returns_cockroachdb_instance(self) -> None:
        assert isinstance(create_cockroachdb_pool(), CockroachDBConnection)
