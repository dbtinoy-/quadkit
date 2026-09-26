"""DI provider that registers database services into the container.

This is the single canonical entry point for registering all database
services into the DI container.  ``DatabaseService`` is a plain facade
(not a DI ``Provider`` subclass), and ``DatabaseDriver`` is a raw
driver abstraction — neither of them should interact with the container
directly.
"""

from __future__ import annotations

import inspect
import time
from typing import TYPE_CHECKING, Any

from quadkit.contracts.core import (
    HealthCheckResult,
    HealthStatus,
)
from quadkit.contracts.core.hooks import HookRegistryProtocol
from quadkit.contracts.exceptions.infra import NoPrimaryBackendError
from quadkit.di.provider import Provider, ProviderPriority
from quadkit.logging import get_logger
from quadkit.primitives.context import Context
from quadkit.sql.providers.database_service import (  # noqa: F401 — tests patch this name here
    DatabaseService,
)

logger = get_logger(__name__)
_alembic_warned = [False]


def _warn_alembic_missing() -> None:
    """Emit a one-off warning when alembic is not installed."""

    if _alembic_warned[0]:
        return
    _alembic_warned[0] = True
    logger.warning(
        "alembic_not_installed",
        hint="pip install alembic",
        detail="migration management disabled",
    )


from quadkit.sql.config import DatabaseConfig

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )


from quadkit.sql.di._registration import _DatabaseRegistrationMixin


class DatabaseProvider(_DatabaseRegistrationMixin, Provider):
    """DI provider that registers database services into the container.
    config: DatabaseConfig | None
    _explicit_config: DatabaseConfig | None
    _db_provider: DatabaseService | None
    _migration_dir: str | Path | None

    Single registration path for all database-related singletons and
    scoped services: DatabaseService, protocol bindings, connection pool,
    query logger, migration manager, audit logger, unit-of-work, and
    optional metrics/tracer.

    Manages lifecycle: connect on boot, disconnect on shutdown.
    Multi-backend support: when ``config.backends`` is non-empty, each backend
    is registered under its name via ``container.singleton(name=entry.name)``.
    The primary backend (``primary=True`` or first entry) also receives the
    unnamed bindings for backward compatibility.
    """

    name = "database"
    priority = ProviderPriority.INFRASTRUCTURE
    config_key: str | None = "sql"
    config_model: type | None = DatabaseConfig

    def __init__(
        self,
        config: DatabaseConfig | str | None = None,
        migration_dir: str = "migrations",
        enable_migrations: bool = False,
    ) -> None:
        super().__init__()
        if isinstance(config, str):
            config = DatabaseConfig.from_url(config)
        self._explicit_config: DatabaseConfig | None = config
        self._migration_dir = migration_dir
        self._enable_migrations = enable_migrations
        self._db_provider: Any = None
        # Multi-backend: list of (name, db_service)
        self._db_services: list[tuple[str, Any]] = []
        self._clock: Any = None
        self._id_generator: Any = None
        self._tracer: Any = None
        self._metrics: Any = None

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Boot all database backends and wire optional observability integrations.

        In multi-backend mode all backends are connected in parallel.  In
        single-backend mode the existing sequential boot is preserved.
        """
        import asyncio

        context = None
        hooks = None
        resolve_optional = getattr(container, "resolve_optional", None)
        if callable(resolve_optional):
            maybe_context = resolve_optional(Context)
            context = (
                await maybe_context
                if inspect.isawaitable(maybe_context)
                else maybe_context
            )
            maybe_hooks = resolve_optional(HookRegistryProtocol)
            hooks = (
                await maybe_hooks if inspect.isawaitable(maybe_hooks) else maybe_hooks
            )
        services_to_wire = [svc for _, svc in self._db_services]
        if self._db_provider is not None:
            services_to_wire.append(self._db_provider)

        wired_service_ids: set[int] = set()
        for service in services_to_wire:
            service_id = id(service)
            if service_id in wired_service_ids:
                continue
            wired_service_ids.add(service_id)
            if hasattr(service, "set_context"):
                service.set_context(context)
            if hasattr(service, "set_hook_registry"):
                service.set_hook_registry(hooks)

        if self._db_services:
            # Multi-backend: connect all backends in parallel
            await asyncio.gather(*(svc.boot() for _, svc in self._db_services))
            logger.info(
                "all_databases_connected",
                count=len(self._db_services),
                names=[n for n, _ in self._db_services],
            )
        elif self._db_provider is not None:
            await self._db_provider.boot()
            logger.info("database_connected")
        else:
            return

        for service in services_to_wire:
            if hasattr(service, "set_context"):
                service.set_context(context)

        # Wire optional observability integrations into the primary backend
        if self._db_provider is None:
            return

        if self._db_provider.metrics is None:
            from quadkit.contracts.observability.metrics import (
                MetricsCollectorProtocol,
            )

            try:
                self._db_provider.metrics = await container.resolve(
                    MetricsCollectorProtocol
                )
            except Exception:  # noqa: BLE001 — optional metrics wiring degrades on any resolution failure
                logger.debug("metrics_collector_unavailable")

        if self._db_provider.tracer is None:
            from quadkit.contracts.observability.tracing import TracerProtocol

            try:
                self._db_provider.tracer = await container.resolve(TracerProtocol)
            except Exception:  # noqa: BLE001 — optional tracing wiring degrades on any resolution failure
                logger.debug("trace_provider_unavailable")

        # Wire optional resilience pipeline factory (provided by the optional provider).
        resilience = self._db_provider.resilience_handler
        if resilience._pipeline_factory is None:
            from quadkit.contracts.infra.resilience import (
                ResiliencePipelineFactoryProtocol,
            )

            try:
                resilience._pipeline_factory = await container.resolve(
                    ResiliencePipelineFactoryProtocol
                )
            except Exception:  # noqa: BLE001 — optional resilience wiring degrades on any resolution failure
                logger.debug("resilience_pipeline_factory_unavailable")

        await self._boot_admin_widgets(container)

    def _register_admin_widgets(
        self,
        container: ContainerRegistrarProtocol,
    ) -> None:
        """Register admin widget services (handlers, contributor).

        Called after database backend registration.
        """
        from quadkit.sql.admin.contributor import SqlAdminContributor
        from quadkit.sql.admin.handlers.migration_status import (
            MigrationStatusWidgetHandler,
        )
        from quadkit.sql.admin.handlers.pool_utilization import (
            PoolUtilizationWidgetHandler,
        )
        from quadkit.sql.admin.handlers.query_stats import QueryStatsWidgetHandler
        from quadkit.sql.migrations.runner import MigrationRunnerAdapter

        container.singleton(
            PoolUtilizationWidgetHandler,
            lambda: PoolUtilizationWidgetHandler(db=None),  # type: ignore[arg-type]
        )
        container.singleton(
            QueryStatsWidgetHandler,
            lambda: QueryStatsWidgetHandler(db=None),  # type: ignore[arg-type]
        )
        container.singleton(
            MigrationStatusWidgetHandler,
            lambda: MigrationStatusWidgetHandler(
                migration_manager=self._db_provider.migration_manager,
                migration_runner=MigrationRunnerAdapter(
                    self._db_provider.migration_manager
                ),
            ),
        )
        container.singleton(SqlAdminContributor, SqlAdminContributor)

    async def _boot_admin_widgets(
        self,
        container: ContainerResolverProtocol,
    ) -> None:
        """Boot admin widgets by calling on_admin_boot on the contributor."""
        from quadkit.sql.admin.contributor import SqlAdminContributor

        contributor = await container.resolve(SqlAdminContributor)
        await contributor.on_admin_boot(container)

    async def get_primary_pool(self) -> ConnectionPoolProtocol:  # type: ignore[name-defined]
        """Return the primary connection pool.

        For multi-backend setups, returns the backend marked `primary: true`.
        Raises NoPrimaryBackendError if no primary is marked or zero backends.

        Returns:
            The primary connection pool.

        Raises:
            NoPrimaryBackendError: If no primary backend is configured.
        """
        if self._db_provider is None:
            raise NoPrimaryBackendError(
                "No database backend is configured. "
                "Ensure DatabaseProvider is registered with a valid config."
            )

        pool = self._db_provider.connection_pool
        if pool is None:
            raise NoPrimaryBackendError(
                "Primary backend has no connection pool. "
                "Ensure the database backend was booted successfully."
            )

        return pool

    async def shutdown(self) -> None:
        """Disconnect all database backends in reverse registration order."""
        if self._db_services:
            for name, svc in reversed(self._db_services):
                await svc.shutdown()
                logger.info("database_disconnected", name=name)
        elif self._db_provider is not None:
            await self._db_provider.shutdown()
            logger.info("database_disconnected")

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check provider health across all registered backends.

        In multi-backend mode the overall status is the worst individual status.

        Args:
            timeout: Maximum seconds to wait for health check response.

        Returns:
            HealthCheckResult with status and component details.
        """
        import asyncio

        start = time.perf_counter()

        if self._db_provider is None and not self._db_services:
            return HealthCheckResult(
                component="database",
                status=HealthStatus.DEGRADED,
                message="database provider not initialized",
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        if self._db_services:
            results = await asyncio.gather(
                *(svc.health_check(timeout=timeout) for _, svc in self._db_services),
                return_exceptions=True,
            )
            statuses = []
            details: dict[str, str] = {}
            for (name, _), result in zip(self._db_services, results, strict=False):
                if isinstance(result, Exception):
                    statuses.append(HealthStatus.UNHEALTHY)
                    details[f"database:{name}"] = str(result)
                else:
                    statuses.append(result.status)  # type: ignore[union-attr]
                    details[f"database:{name}"] = result.status.value  # type: ignore[union-attr]

            overall = (
                HealthStatus.UNHEALTHY
                if HealthStatus.UNHEALTHY in statuses
                else HealthStatus.DEGRADED
                if HealthStatus.DEGRADED in statuses
                else HealthStatus.HEALTHY
            )
            return HealthCheckResult(
                component="database",
                status=overall,
                details=details,
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        # Single-backend fallback (existing behaviour unchanged)
        try:
            db_result = await self._db_provider.health_check(timeout=timeout)
            return HealthCheckResult(
                component="database",
                status=db_result.status,
                details=db_result.details,
                error=db_result.error,
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        except (ConnectionError, TimeoutError, RuntimeError) as exc:
            return HealthCheckResult(
                component="database",
                status=HealthStatus.UNHEALTHY,
                error=str(exc),
                duration_ms=(time.perf_counter() - start) * 1000,
            )
