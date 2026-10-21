"""SQLAlchemy engine pool adapter — a managed pool view over a raw ``AsyncEngine``.

Applications commonly create their engine directly with
``create_async_engine`` (or through a thin wrapper of their own) rather than
going through :class:`~quadkit.sql.di.provider.DatabaseProvider`. Everything
framework-side that inspects the database — the admin dashboard's pool and
query widgets, health reporting, any consumer of
:class:`~quadkit.contracts.data.ConnectionPoolProtocol` — then has no pool to
report against, so those widgets and probes render "Unavailable" for a
perfectly healthy database.

:class:`AsyncEnginePool` bridges that gap: it presents the engine's own
SQLAlchemy pool in the framework's pool shape, and derives the cumulative
acquire/release counters the widgets report from SQLAlchemy's ``checkout`` /
``checkin`` pool events (SQLAlchemy tracks only current occupancy). Counters
are process-local, which is the correct scope for a per-engine pool view.

Example:
    ```python
    from sqlalchemy.ext.asyncio import create_async_engine
    from quadkit.sql.pool.engine import AsyncEnginePool

    engine = create_async_engine("postgresql+asyncpg://...", pool_size=10)
    pool = AsyncEnginePool(engine)
    stats = await pool.get_pool_stats()      # active/max/acquired/released/...
    health = await pool.health_check()       # SELECT 1 round trip
    ```
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover — typing only
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

logger = get_logger(__name__)

#: Pools without an occupancy API (``NullPool``, ``StaticPool``) still report a
#: coherent snapshot, just without queue-depth numbers.
_NO_OCCUPANCY = (AttributeError, NotImplementedError)


class AsyncEnginePool:
    """Expose a SQLAlchemy ``AsyncEngine`` as a framework connection pool.

    Args:
        engine: The async engine whose pool is reported.
        name: Backend name used in logs and health messages.
        primary: Whether this pool is the provider's primary backend.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        name: str = "primary",
        primary: bool = True,
    ) -> None:
        self._engine = engine
        self._name = name
        self._primary = primary
        self._acquired = 0
        self._released = 0
        self._listeners_installed = False
        self._install_listeners()

    # ------------------------------------------------------------------
    # identity
    # ------------------------------------------------------------------
    @property
    def name(self) -> str:
        """Return the backend name this pool reports for."""
        return self._name

    @property
    def is_primary(self) -> bool:
        """Return whether this is the provider's primary backend."""
        return self._primary

    @property
    def engine(self) -> AsyncEngine:
        """Return the wrapped engine."""
        return self._engine

    @property
    def dialect(self) -> str:
        """Return the SQL dialect name (``postgresql``, ``sqlite``, ...)."""
        return str(self._engine.sync_engine.dialect.name)

    # ------------------------------------------------------------------
    # ConnectionPoolProtocol surface
    # ------------------------------------------------------------------
    @property
    def max_connections(self) -> int:
        """Return the pool ceiling (``0`` when the pool has no bound)."""
        pool = self._engine.sync_engine.pool
        size = self._int_attr(pool, "size")
        overflow = self._int_attr(pool, "max_overflow")
        if size is None:
            return 0
        return size + (overflow or 0)

    @property
    def connection_timeout(self) -> float:
        """Return the configured checkout timeout in seconds."""
        timeout = self._float_attr(self._engine.sync_engine.pool, "timeout")
        return timeout if timeout is not None else 30.0

    @property
    def acquired_connections(self) -> int:
        """Return cumulative successful checkouts observed by this adapter."""
        return self._acquired

    @property
    def released_connections(self) -> int:
        """Return cumulative check-ins observed by this adapter."""
        return self._released

    async def initialize(self) -> None:
        """Open the engine's pool without forcing a connection.

        SQLAlchemy pools are lazy, so there is nothing to do beyond priming
        the dialect — ``warm()`` is the way to pre-create connections.
        """
        self._install_listeners()

    async def shutdown(self) -> None:
        """Dispose the engine's pool.

        The engine is owned by whoever created it; disposal here is the
        contract member apps call when they hand the pool lifecycle to the
        framework, so it stays idempotent.
        """
        await self._engine.dispose()

    @asynccontextmanager
    async def get_connection(self) -> AsyncIterator[AsyncConnection]:
        """Check a connection out of the engine's pool.

        Yields:
            An :class:`~sqlalchemy.ext.asyncio.AsyncConnection`.
        """
        async with self._engine.connect() as connection:
            yield connection

    async def get_pool_stats(self) -> dict[str, Any]:
        """Return pool occupancy and cumulative counters.

        Returns:
            The framework's pool-stat shape: current occupancy, ceiling,
            cumulative acquired/released counts, and utilization rate. Keys
            without a value for this pool type are reported as ``0`` rather
            than omitted, so widget templates never render a blank cell.
        """
        sync_pool = self._engine.sync_engine.pool
        active = self._int_attr(sync_pool, "checkedout") or 0
        idle = self._int_attr(sync_pool, "checkedin")
        if idle is None:
            size = self._int_attr(sync_pool, "size") or 0
            idle = max(size - active, 0)
        maximum = self.max_connections
        return {
            "name": self._name,
            "dialect": self.dialect,
            "pool_class": type(sync_pool).__name__,
            "pool_size": idle,
            "active_connections": active,
            "idle_connections": idle,
            "max_connections": maximum,
            "acquired_connections": self._acquired,
            "released_connections": self._released,
            "utilization_rate": (active / maximum) if maximum > 0 else 0.0,
        }

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:  # noqa: ARG002
        """Probe the pool with a ``SELECT 1`` round trip.

        Args:
            timeout: Accepted for interface compatibility; the engine's own
                connect timeout governs the probe.

        Returns:
            ``HEALTHY`` when the round trip succeeds, ``UNHEALTHY`` otherwise.
        """
        from sqlalchemy import text

        try:
            async with self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001 — health probes never raise
            logger.warning("sql.engine_pool_unhealthy", pool=self._name, error=str(exc))
            return HealthCheckResult(
                component=f"pool:{self._name}",
                status=HealthStatus.UNHEALTHY,
                message=str(exc),
            )
        return HealthCheckResult(
            component=f"pool:{self._name}",
            status=HealthStatus.HEALTHY,
            message=f"Pool '{self._name}' responded to SELECT 1",
            details={"dialect": self.dialect},
        )

    async def get_query_stats(self, time_range_seconds: int = 3600) -> dict[str, Any]:
        """Return the adapter's own counters.

        SQLAlchemy does not record statement statistics on the pool, so this
        reports the acquire/release counters this adapter tracks. Statement
        timings belong to the query logger / tracer.

        Args:
            time_range_seconds: Accepted for interface compatibility.

        Returns:
            Mapping with the cumulative acquire/release counters.
        """
        return {
            "time_range_seconds": time_range_seconds,
            "acquired_connections": self._acquired,
            "released_connections": self._released,
        }

    async def warm(self, count: int | None = None) -> None:
        """Pre-create pooled connections to avoid cold-start latency.

        Args:
            count: Number of connections to open concurrently. Defaults to the
                pool ceiling (at least one).
        """

        target = count if count is not None else max(self.max_connections, 1)
        keep: list[Any] = []
        try:
            for _ in range(target):
                keep.append(await self._engine.connect())
        except Exception as exc:  # noqa: BLE001 — warming is best effort
            logger.debug(
                "sql.engine_pool_warm_incomplete", pool=self._name, error=str(exc)
            )
        finally:
            for connection in keep:
                await connection.close()

    async def validate_connections(self) -> int:
        """Validate the pool by opening one connection and closing it.

        Returns:
            ``1`` when the pool answered, ``0`` when it did not.
        """
        from sqlalchemy import text

        try:
            async with self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001 — validation reports, never raises
            logger.warning("sql.engine_pool_invalid", pool=self._name, error=str(exc))
            return 0
        return 1

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _install_listeners(self) -> None:
        """Attach checkout/checkin counters to the engine's pool once."""
        if self._listeners_installed:
            return
        from sqlalchemy import event

        sync_engine = self._engine.sync_engine

        def _on_checkout(*_args: Any, **_kwargs: Any) -> None:
            self._acquired += 1

        def _on_checkin(*_args: Any, **_kwargs: Any) -> None:
            self._released += 1

        try:
            event.listen(sync_engine, "checkout", _on_checkout)
            event.listen(sync_engine, "checkin", _on_checkin)
        except Exception as exc:  # noqa: BLE001 — counters are advisory
            logger.debug("sql.engine_pool_events_unavailable", error=str(exc))
            return
        self._listeners_installed = True

    @staticmethod
    def _int_attr(target: Any, attribute: str) -> int | None:
        """Return ``target.attribute`` as an int, or ``None`` when absent."""
        getter = getattr(target, attribute, None)
        if not callable(getter):
            return None
        try:
            value = getter()
        except _NO_OCCUPANCY:
            return None
        except Exception:  # noqa: BLE001 — pool introspection is best effort
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _float_attr(target: Any, attribute: str) -> float | None:
        """Return ``target.attribute`` as a float, or ``None`` when absent."""
        value = getattr(target, attribute, None)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


__all__ = ["AsyncEnginePool"]
