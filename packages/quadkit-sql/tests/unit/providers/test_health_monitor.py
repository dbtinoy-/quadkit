"""Tests for the database provider health monitor."""

from __future__ import annotations

from quadkit.contracts.core import HealthCheckCategory, HealthStatus
from quadkit.sql.exceptions import DatabaseError
from quadkit.sql.providers.health_monitor import HealthMonitor


class _Manager:
    def __init__(self, connected: bool = True, database_type: str = "postgresql") -> None:
        self.connected = connected
        self.database_type = database_type
        self.queries: list[str] = []

    async def execute_query(self, sql: str) -> object:
        self.queries.append(sql)
        return None


class TestHealthCheck:
    async def test_healthy_via_provider(self) -> None:
        manager = _Manager()
        result = await HealthMonitor(manager).health_check()
        assert result.status == HealthStatus.HEALTHY
        assert result.component == "database"
        assert result.category == HealthCheckCategory.READINESS
        assert manager.queries == ["SELECT 1 as health_check"]
        assert result.details["database_type"] == "postgresql"
        assert result.duration_ms >= 0

    async def test_healthy_via_nested_provider_attr(self) -> None:
        inner = _Manager()
        wrapper = type("_Wrapper", (), {"provider": inner})()
        result = await HealthMonitor(wrapper).health_check()
        assert result.status == HealthStatus.HEALTHY
        assert inner.queries == ["SELECT 1 as health_check"]

    async def test_unhealthy_on_database_error(self) -> None:
        class _Broken:
            async def execute_query(self, sql: str) -> None:
                msg = "connection refused"
                raise DatabaseError(msg)

        result = await HealthMonitor(_Broken()).health_check()
        assert result.status == HealthStatus.UNHEALTHY
        assert "connection refused" in (result.message or "")
        assert "connection refused" in (result.error or "")
        assert result.details["database_type"] == "unknown"

    async def test_unhealthy_on_os_error(self) -> None:
        class _Broken:
            async def execute_query(self, sql: str) -> None:
                raise OSError("network down")

        result = await HealthMonitor(_Broken()).health_check()
        assert result.status == HealthStatus.UNHEALTHY
        assert "network down" in (result.error or "")

    async def test_unhealthy_on_timeout(self) -> None:
        class _Broken:
            async def execute_query(self, sql: str) -> None:
                raise TimeoutError("slow")

        result = await HealthMonitor(_Broken()).health_check()
        assert result.status == HealthStatus.UNHEALTHY

    async def test_fallback_ping_when_executor_falsy(self) -> None:
        pings = {"n": 0}

        class _Conn:
            async def ping(self) -> None:
                pings["n"] += 1

        class _Mgr:
            # falsy manager forces the get_connection() fallback path
            def __bool__(self) -> bool:
                return False

            def get_connection(self):
                import contextlib

                @contextlib.asynccontextmanager
                async def _ctx():
                    yield _Conn()

                return _ctx()

        result = await HealthMonitor(_Mgr()).health_check()
        assert result.status == HealthStatus.HEALTHY
        assert pings["n"] == 1

    async def test_result_serialisation(self) -> None:
        result = await HealthMonitor(_Manager()).health_check()
        d = result.to_dict()
        assert d["component"] == "database"
        assert "status" in d
        assert "duration_ms" in d


class TestGetStats:
    async def test_stats_fields(self) -> None:
        manager = _Manager(connected=False, database_type="mysql")
        stats = await HealthMonitor(manager).get_stats()
        assert stats["database_type"] == "mysql"
        assert stats["connected"] is False
        assert stats["connection_pool"] is False
        assert stats["query_logger"] is False

    async def test_stats_unknown_type(self) -> None:
        class _Bare:
            connected = True

        stats = await HealthMonitor(_Bare()).get_stats()
        assert stats["database_type"] == "unknown"
        assert stats["connected"] is True
        assert stats["connection_pool"] is False
