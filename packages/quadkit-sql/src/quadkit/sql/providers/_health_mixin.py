"""Health check and table existence mixin for DatabaseService."""

from __future__ import annotations

from typing import Any, cast

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock
from quadkit.sql.exceptions import (
    DatabaseConnectionError,
    DatabaseError,
    DatabaseTimeoutError,
    QueryError,
)

logger = get_logger(__name__)


class _HealthMixin:
    """Mixin providing health check and table existence methods for DatabaseService.

    All ``self.*`` attribute accesses here are satisfied by ``DatabaseService.__init__``
    or sibling mixins; ``# type: ignore[attr-defined]`` comments suppress mypy errors
    for attributes not declared on this mixin but guaranteed to exist at runtime.
    """

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform health checks on the database and connection pool.

        Returns:
            HealthCheckResult with status and details.
        """
        details = {}

        def get_status(h: Any) -> str:
            if h is None:
                return "unknown"
            status_obj = getattr(h, "status", None)
            if status_obj is not None:
                return getattr(status_obj, "value", str(status_obj))
            if isinstance(h, dict):
                return cast("str", h.get("status", "unknown"))
            return "unknown"

        def get_error(h: Any) -> str | None:
            if h is None:
                return None
            err = getattr(h, "error", None)
            if err is not None:
                return cast("str | None", err)
            return h.get("error") if isinstance(h, dict) else None

        def get_details(h: Any) -> dict[str, Any]:
            if h is None:
                return {}
            det = getattr(h, "details", None)
            if det is not None:
                return cast("dict[str, Any]", det)
            return h.get("details", {}) if isinstance(h, dict) else {}

        if self.db_provider and hasattr(self.db_provider, "health_check"):  # type: ignore[attr-defined]
            try:
                db_health = await self.db_provider.health_check()  # type: ignore[attr-defined]
                details["database"] = db_health
            except (
                DatabaseError,
                DatabaseConnectionError,
                DatabaseTimeoutError,
                QueryError,
                OSError,
                ConnectionError,
                RuntimeError,
                TimeoutError,
            ) as e:
                logger.error(
                    "DatabaseService.health_check encountered error: %s",
                    str(e),
                    exc_info=True,
                )
                details["database"] = {"status": "unhealthy", "error": str(e)}

        if self.connection_pool and hasattr(self.connection_pool, "health_check"):  # type: ignore[attr-defined]
            try:
                pool_health = await self.connection_pool.health_check()  # type: ignore[attr-defined]
                details["pool"] = pool_health
            except (
                DatabaseError,
                DatabaseConnectionError,
                DatabaseTimeoutError,
                QueryError,
                OSError,
                ConnectionError,
                RuntimeError,
                TimeoutError,
            ) as e:
                logger.error(
                    "DatabaseService.health_check encountered error: %s",
                    str(e),
                    exc_info=True,
                )
                details["pool"] = {"status": "unhealthy", "error": str(e)}

        if not details:
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                component=self.name,  # type: ignore[attr-defined]
                checked_at=ambient_clock.now(),
            )

        statuses = [get_status(r) for r in details.values()]
        overall_status_str = "healthy"
        error_msg = None

        if any(s == "unhealthy" for s in statuses):
            overall_status_str = (
                "unhealthy" if all(s == "unhealthy" for s in statuses) else "degraded"
            )
            error_msgs = [
                get_error(r) for r in details.values() if get_status(r) == "unhealthy"
            ]
            error_msg = "; ".join(filter(None, error_msgs))
        elif any(s in {"warning", "degraded"} for s in statuses):
            overall_status_str = "degraded"

        try:
            overall_status = HealthStatus(overall_status_str)
        except ValueError:
            overall_status = HealthStatus.UNKNOWN

        aggregated_details: dict[str, Any] = {}
        for r in details.values():
            d = get_details(r)
            if isinstance(d, dict):
                aggregated_details.update(d)

        return HealthCheckResult(
            status=overall_status,
            error=error_msg,
            details=aggregated_details,
            component=self.name,  # type: ignore[attr-defined]
            checked_at=ambient_clock.now(),
        )

    async def table_exists(self, table_name: str) -> bool:
        """Check whether a table exists in the database.

        Args:
            table_name: The name of the table to check.

        Returns:
            True if the table exists, False otherwise.
        """
        if not self.db_provider:  # type: ignore[attr-defined]
            await self.boot()  # type: ignore[attr-defined]
        if hasattr(self.db_provider, "table_exists"):  # type: ignore[attr-defined]
            return cast(
                "bool",
                await self.db_provider.table_exists(table_name),  # type: ignore[attr-defined]
            )
        return False
