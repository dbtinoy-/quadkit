"""
Health monitoring for database providers.

Handles health checks, statistics, and monitoring operations.
"""

from __future__ import annotations

from typing import Any

from quadkit.contracts.core import HealthCheckCategory, HealthCheckResult, HealthStatus
from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock
from quadkit.sql.exceptions import DatabaseConnectionError, DatabaseError

logger = get_logger(__name__)


class HealthMonitor:
    """
    Monitors database health and provides statistics.

    This class handles health checks, connection status monitoring,
    and database statistics collection.
    """

    def __init__(
        self,
        connection_manager: Any,
    ) -> None:
        self.connection_manager = connection_manager

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform health check"""
        start_time = ambient_clock.timestamp()
        try:
            # Use the connection manager to execute a simple query
            executor = getattr(
                self.connection_manager, "provider", self.connection_manager
            )
            if executor:
                await executor.execute_query("SELECT 1 as health_check")
            else:
                # Fallback if no crud operations available
                async with self.connection_manager.get_connection() as conn:
                    # Simple ping if possible
                    if hasattr(conn, "ping"):
                        await conn.ping()

            response_time = (ambient_clock.timestamp() - start_time) * 1000  # ms
            return HealthCheckResult(
                component="database",
                status=HealthStatus.HEALTHY,
                message="Database connection successful",
                duration_ms=response_time,
                details={
                    "message": "Database connection successful",
                    "database_type": getattr(
                        self.connection_manager,
                        "database_type",
                        "unknown",
                    ),
                },
                checked_at=ambient_clock.now(),
                category=HealthCheckCategory.READINESS,
            )
        except (
            DatabaseError,
            DatabaseConnectionError,
            OSError,
            ConnectionError,
            RuntimeError,
            TimeoutError,
        ) as e:
            logger.exception("Health check failed")
            response_time = (ambient_clock.timestamp() - start_time) * 1000  # ms
            return HealthCheckResult(
                component="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection failed: {e!s}",
                error=f"Database connection failed: {e!s}",
                duration_ms=response_time,
                details={
                    "message": f"Database connection failed: {e!s}",
                    "database_type": getattr(
                        self.connection_manager,
                        "database_type",
                        "unknown",
                    ),
                },
                checked_at=ambient_clock.now(),
                category=HealthCheckCategory.READINESS,
            )

    async def get_stats(self) -> dict[str, Any]:
        """Get database statistics"""
        return {
            "database_type": getattr(
                self.connection_manager,
                "database_type",
                "unknown",
            ),
            "connected": self.connection_manager.connected,
            "connection_pool": getattr(self.connection_manager, "connection_pool", None)
            is not None,
            "query_logger": getattr(self, "query_logger", None) is not None,
        }
