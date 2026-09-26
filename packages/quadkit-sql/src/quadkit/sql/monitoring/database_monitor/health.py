"""Database monitoring classes"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock
from quadkit.sql.exceptions import DatabaseConnectionError, DatabaseError
from quadkit.sql.lib import infer_provider_type_from_url
from quadkit.sql.monitoring.metrics import (
    DbMetricsCollector,
    HealthStatus,
)

logger = get_logger(__name__)


class DatabaseHealthChecker:
    """Database health checker - avoids collision with quadkit.health.HealthChecker"""

    def __init__(
        self,
        collector: DbMetricsCollector,
    ):
        self.collector = collector

    def _get_time(self) -> float:
        """Get current timestamp."""
        return ambient_clock.timestamp()

    def _get_datetime(self) -> datetime:
        """Get current datetime."""
        return ambient_clock.now()

    async def check_database_health(
        self,
        connection_string: str,
        timeout: float = 5.0,
    ) -> HealthStatus:
        """Check database connectivity and basic health"""

        from sqlalchemy import (
            create_engine,
            text,
        )

        component = "database"
        start_time = self._get_time()

        try:
            # Create connection with timeout where supported. For SQLite URIs we skip
            # connect_args because the sqlite DBAPI doesn't accept them.
            try:
                # Prefer canonical provider detection but fall back to startswith for
                # non-conforming inputs to remain permissive.
                try:
                    is_sqlite = (
                        infer_provider_type_from_url(connection_string) == "sqlite"
                    )
                except (ValueError, TypeError):
                    is_sqlite = isinstance(
                        connection_string,
                        str,
                    ) and connection_string.startswith("sqlite:")

                if is_sqlite:
                    engine = create_engine(connection_string)
                else:
                    engine = create_engine(
                        connection_string,
                        connect_args={"connect_timeout": timeout},
                    )
            except (ValueError, TypeError, RuntimeError, OSError):
                # Some drivers may still raise; fall back to a no-args engine
                engine = create_engine(connection_string)

            async def check_connectivity() -> bool:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, _sync_check_connectivity)

            def _sync_check_connectivity() -> bool:
                with engine.connect() as conn:
                    # Simple health check query
                    result = conn.execute(text("SELECT 1 as health_check"))
                    row = result.fetchone()
                    if row is None:
                        return False
                    return bool(row[0] == 1)

            # Run with timeout and allow a fallback attempt without connect_args if the
            # first attempt fails (some drivers like SQLite reject certain connect args)
            try:
                result = await asyncio.wait_for(check_connectivity(), timeout=timeout)
            except Exception as first_exc:  # noqa: BLE001 — any first-attempt failure (incl. DBAPI rejecting connect_args) triggers the fallback
                # Try again with a fresh engine that does not pass connect_args
                try:
                    engine.dispose()
                except (RuntimeError, OSError) as e:
                    logger.debug(
                        "Engine dispose failed during health check fallback: %s",
                        e,
                        exc_info=True,
                    )

                try:
                    engine_no_connect_args = create_engine(connection_string)

                    async def _check_no_args() -> bool:
                        loop = asyncio.get_event_loop()
                        return await loop.run_in_executor(None, _sync_check_no_args)

                    def _sync_check_no_args() -> bool:
                        with engine_no_connect_args.connect() as conn:
                            result = conn.execute(text("SELECT 1 as health_check"))
                            row = result.fetchone()
                            return bool(row and row[0] == 1)

                    result = await asyncio.wait_for(_check_no_args(), timeout=timeout)
                    engine = engine_no_connect_args
                except Exception as second_exc:  # noqa: BLE001 — any second-attempt failure is re-raised for the outer handler
                    # If both attempts failed, surface the original error message
                    raise second_exc from first_exc

            if result:
                status = "healthy"
                message = "Database connection successful"
            else:
                status = "critical"
                message = "Database health check failed"

        except TimeoutError:
            status = "critical"
            message = f"Database connection timeout after {timeout}s"
        except Exception as e:  # noqa: BLE001 — health checks must never raise; any failure is a critical status
            logger.exception("Database health check failed")
            status = "critical"
            message = f"Database connection failed: {e!s}"
        finally:
            if "engine" in locals():
                engine.dispose()

        response_time = self._get_time() - start_time

        return HealthStatus(
            component=component,
            status=status,  # type: ignore[arg-type]
            message=message,
            timestamp=self._get_datetime(),
            details={"response_time": response_time, "timeout": timeout},
        )

    async def check_connection_pool_health(self, pool: Any) -> HealthStatus:
        """Check connection pool health"""
        component = "connection_pool"
        status = "critical"
        message = "Connection pool health check failed"
        details = {}

        try:
            # Get pool statistics
            active = getattr(pool, "_active_connections", 0)
            total = getattr(pool, "_total_connections", 0)
            available = total - active

            # Check utilization
            utilization = active / total if total > 0 else 0

            if utilization > 0.95:
                status = "critical"
                message = f"Connection pool critically overutilized: {utilization:.1%}"
            elif utilization > 0.85:
                status = "warning"
                message = f"Connection pool highly utilized: {utilization:.1%}"
            else:
                status = "healthy"
                message = f"Connection pool healthy: {utilization:.1%}"

            details = {
                "active_connections": active,
                "total_connections": total,
                "available_connections": available,
                "utilization": utilization,
            }

        except (
            DatabaseError,
            DatabaseConnectionError,
            OSError,
            ConnectionError,
            RuntimeError,
            TimeoutError,
            TypeError,
            AttributeError,
        ) as e:
            # Log full traceback for diagnostics then return critical status
            logger.exception("Connection pool health check failed")
            details = {"error": str(e)}

        return HealthStatus(
            component=component,
            status=status,  # type: ignore[arg-type]
            message=message,
            timestamp=self._get_datetime(),
            details=details,
        )

    async def check_performance_health(
        self,
        time_range_seconds: int = 3600,
    ) -> list[HealthStatus]:
        """Check performance against baselines"""
        baselines = await self.collector.get_performance_baselines()
        query_stats = await self.collector.get_query_stats(time_range_seconds)
        transaction_stats = await self.collector.get_transaction_stats(
            time_range_seconds,
        )

        health_checks = []

        # Check query performance
        if query_stats["total_queries"] > 0:
            avg_query_time = query_stats["average_execution_time"]
            baseline = next(
                (b for b in baselines if b.metric_name == "query_execution_time"),
                None,
            )

            if baseline:
                if avg_query_time > baseline.critical_threshold:
                    status = "critical"
                    message = f"Average query time critically high: {avg_query_time:.3f}s > {baseline.critical_threshold}s"
                elif avg_query_time > baseline.warning_threshold:
                    status = "warning"
                    message = f"Average query time elevated: {avg_query_time:.3f}s > {baseline.warning_threshold}s"
                else:
                    status = "healthy"
                    message = f"Query performance healthy: {avg_query_time:.3f}s"

                health_checks.append(
                    HealthStatus(
                        component="query_performance",
                        status=status,  # type: ignore[arg-type]
                        message=message,
                        timestamp=self._get_datetime(),
                        details={
                            "average_query_time": avg_query_time,
                            "baseline_expected": baseline.expected_value,
                            "baseline_warning": baseline.warning_threshold,
                            "baseline_critical": baseline.critical_threshold,
                        },
                    ),
                )

        # Check transaction performance
        if transaction_stats["total_transactions"] > 0:
            commit_ratio = transaction_stats["commit_ratio"]
            baseline = next(
                (b for b in baselines if b.metric_name == "transaction_commit_ratio"),
                None,
            )

            if baseline:
                if commit_ratio < baseline.critical_threshold:
                    status = "critical"
                    message = (
                        f"Transaction commit ratio critically low: {commit_ratio:.1%} "
                        f"< {baseline.critical_threshold:.1%}"
                    )
                elif commit_ratio < baseline.warning_threshold:
                    status = "warning"
                    message = f"Transaction commit ratio low: {commit_ratio:.1%} < {baseline.warning_threshold:.1%}"
                else:
                    status = "healthy"
                    message = f"Transaction success rate healthy: {commit_ratio:.1%}"

                health_checks.append(
                    HealthStatus(
                        component="transaction_performance",
                        status=status,  # type: ignore[arg-type]
                        message=message,
                        timestamp=self._get_datetime(),
                        details={
                            "commit_ratio": commit_ratio,
                            "total_transactions": transaction_stats[
                                "total_transactions"
                            ],
                            "successful_transactions": transaction_stats[
                                "successful_transactions"
                            ],
                            "failed_transactions": transaction_stats[
                                "failed_transactions"
                            ],
                        },
                    ),
                )

        return health_checks
