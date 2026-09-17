"""Feature tour: health — strict deep checks, humane probes.

Two complementary contracts ship out of the box. The probe trio
(`/health/live`, `/health/ready`, `/health/startup`) answers the
questions orchestrators ask: a running application always reports its
own truthful baseline ("application running") even with zero providers,
so a stock app passes Kubernetes liveness and readiness out of the
box. The deep `/health` endpoint is deliberately strict: every missing
optional dependency (database, cache) shows up as an unhealthy
component and drives a 503, `DEGRADED` maps to 207, so alerting sees
exactly the wiring gaps instead of a green veneer.
"""

import pytest

from quadkit import Application, Provider
from quadkit.contracts.core.di import ContainerRegistrarProtocol
from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.contracts.data import DatabaseProviderProtocol
from quadkit.contracts.infra.cache import CacheBackendProtocol
from quadkit.testing import WebTestBed
from quadkit.web import WebModule


def make_app() -> Application:
    app = Application()
    app.add_module(WebModule.configure(controllers=[]))
    return app


@pytest.mark.asyncio
async def test_probe_trio_answers_truly_out_of_the_box() -> None:
    async with WebTestBed(make_app()) as bed:
        for path in ("/health/live", "/health/ready", "/health/startup"):
            response = bed.get(path)
            assert response.status_code == 200, f"{path}: {response.text}"
            body = response.json
            assert body["status"] == "healthy"
            # At least one truthful component speaks — never an empty shell.
            assert body["components"]


@pytest.mark.asyncio
async def test_deep_health_is_strict_about_missing_dependencies() -> None:
    async with WebTestBed(make_app()) as bed:
        response = bed.get("/health")
        assert response.status_code == 503
        body = response.json
        assert body["status"] == "unhealthy"
        components = body["components"]
        # Missing optional dependencies are named, with the reason attached.
        assert components["database"]["status"] == "unhealthy"
        assert "not configured" in components["database"]["message"]
        assert components["redis"]["status"] == "unhealthy"
        assert "not configured" in components["redis"]["message"]


class FakeDatabase:
    """Full DatabaseProviderProtocol stand-in (query calls stay inert)."""

    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def is_connected(self) -> bool:
        return True

    async def get_primary_pool(self) -> object:
        return object()

    async def execute_query(self, *a, **k) -> list:
        return []

    async def execute_insert(self, *a, **k) -> int:
        return 0

    async def execute_update(self, *a, **k) -> int:
        return 0

    async def execute_delete(self, *a, **k) -> int:
        return 0

    async def execute(self, *a, **k) -> object:
        return object()

    def transaction(self, *a, **k) -> object:
        return object()

    def begin_transaction(self, *a, **k) -> object:
        return object()

    async def commit_transaction(self, *a, **k) -> None: ...
    async def rollback_transaction(self, *a, **k) -> None: ...
    async def table_exists(self, *a, **k) -> bool:
        return True

    def scoped_context(self, *a, **k) -> object:
        return object()

    async def get_scoped_connection(self, *a, **k) -> object:
        return object()

    async def acquire(self, *a, **k) -> object:
        return object()

    async def release(self, *a, **k) -> None: ...

    async def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(
            component="database",
            status=HealthStatus.HEALTHY,
            message="pg pool: 9/10 idle",
        )


class DegradedCache:
    """CacheBackendProtocol stand-in whose cache is hurting."""

    async def get(self, key):
        return None

    async def set(self, key, value, ttl=None) -> bool:
        return True

    async def delete(self, key) -> bool:
        return True

    async def delete_many(self, keys) -> int:
        return 0

    async def delete_pattern(self, pattern) -> int:
        return 0

    async def exists(self, key) -> bool:
        return False

    async def clear(self) -> bool:
        return True

    async def get_many(self, keys):
        return {}

    async def set_many(self, mapping, ttl=None) -> bool:
        return True

    async def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(
            component="redis",
            status=HealthStatus.DEGRADED,
            message="evictions above threshold",
        )


class InfraProvider(Provider):
    async def register(self, container: ContainerRegistrarProtocol) -> None:
        container.singleton(DatabaseProviderProtocol, FakeDatabase())  # type: ignore[type-abstract]
        container.singleton(CacheBackendProtocol, DegradedCache())  # type: ignore[type-abstract]


@pytest.mark.asyncio
async def test_degraded_dependency_maps_to_207() -> None:
    app = make_app()
    app.add_provider(InfraProvider())
    async with WebTestBed(app) as bed:
        response = bed.get("/health")
        assert response.status_code == 207
        body = response.json
        assert body["status"] == "degraded"
        assert body["components"]["database"]["status"] == "healthy"
        assert body["components"]["redis"]["status"] == "degraded"
        assert body["components"]["redis"]["message"] == "evictions above threshold"
