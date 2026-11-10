"""CLI health checks for quadkit-sql."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, cast

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.data.sql.database import DatabaseProviderProtocol
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.core.di import ContainerResolverProtocol

logger = get_logger(__name__)
_CONNECTIVITY_TIMEOUT = 5.0


async def check_database_connection(
    container: ContainerResolverProtocol,
) -> HealthCheckResult:
    """Observe the configured provider's connectivity health, not migrations.

    The caller owns application boot/shutdown. Resolve through the booted DI
    container without constructing a second provider or reading database URLs.
    Bound resolution plus probing, preserve provider evidence and cancellation,
    and report failures without exposing exception text containing credentials.
    """
    try:
        async with asyncio.timeout(_CONNECTIVITY_TIMEOUT):
            provider = cast(
                "DatabaseProviderProtocol",
                await container.resolve(DatabaseProviderProtocol),
            )
            result = await provider.health_check(timeout=_CONNECTIVITY_TIMEOUT)
            if not isinstance(result, HealthCheckResult) or not isinstance(
                result.status, HealthStatus
            ):
                raise TypeError("Provider returned an invalid health result")
            return result
    except Exception as exc:  # Health boundary; cancellation must propagate.
        logger.warning(
            "sql_cli_connectivity_check_failed", error_type=type(exc).__name__
        )
        return HealthCheckResult(
            component="database_connection",
            status=HealthStatus.UNHEALTHY,
            error="Database connectivity could not be verified",
        )
