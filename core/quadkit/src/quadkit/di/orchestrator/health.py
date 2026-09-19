"""Health coordinator for provider health checks."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from quadkit.contracts.core.health import (
    AggregateHealthResult,
    HealthCheckCategory,
    HealthCheckProtocol,
    HealthCheckResult,
    HealthStatus,
)
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.di.orchestrator.registry import ProviderRegistry
    from quadkit.di.provider import Provider

logger = get_logger(__name__)


class HealthCoordinator:
    """Coordinates health checks across registered providers and probes.

    The coordinator keeps the existing provider-scanning behavior for
    backward compatibility while also allowing explicit registration of
    category-tagged health checks.
    """

    def __init__(self, registry: ProviderRegistry) -> None:
        """Initialize with a provider registry.

        Args:
            registry: The provider registry containing all providers to check.
        """
        self._registry = registry
        self._checks: dict[str, tuple[Any, HealthCheckCategory]] = {}

    def register(
        self,
        name: str,
        check: HealthCheckProtocol,
        *,
        category: HealthCheckCategory = HealthCheckCategory.READINESS,
    ) -> None:
        """Register an explicit health check for aggregation.

        Args:
            name: Unique component name for this check.
            check: Object implementing :class:`HealthCheckProtocol`.
            category: Probe category for this check.
        """
        self._checks[name] = (check, category)

    def _coerce_category(
        self, category: HealthCheckCategory | str | None
    ) -> HealthCheckCategory | None:
        if category is None:
            return None
        if isinstance(category, HealthCheckCategory):
            return category
        return HealthCheckCategory(str(category).lower())

    def _collect_checks(self) -> list[tuple[str, Any, HealthCheckCategory]]:
        checks: dict[str, tuple[Any, HealthCheckCategory]] = {
            name: (provider, HealthCheckCategory.READINESS)
            for name, provider in self._registry._providers.items()
        }
        checks.update(self._checks)
        return [(name, check, category) for name, (check, category) in checks.items()]

    async def _run_check(
        self,
        name: str,
        check: Any,
        category: HealthCheckCategory,
        timeout: float,
    ) -> tuple[str, HealthCheckResult]:
        if not isinstance(check, HealthCheckProtocol):
            return name, HealthCheckResult(
                component=name,
                status=HealthStatus.HEALTHY,
                category=category,
            )

        try:
            try:
                probe = check.health_check(timeout)
            except TypeError:
                probe = check.health_check()
            result = await asyncio.wait_for(
                probe,
                timeout=timeout,
            )
            if result.category == HealthCheckCategory.READINESS and (
                category != HealthCheckCategory.READINESS
            ):
                result = HealthCheckResult(
                    component=result.component,
                    status=result.status,
                    message=result.message,
                    error=result.error,
                    category=category,
                )
            return name, result
        except TimeoutError:
            return name, HealthCheckResult(
                component=name,
                status=HealthStatus.UNHEALTHY,
                error="Health check timed out",
                category=category,
            )
        except Exception as err:  # noqa: BLE001 — a health check must never raise — report unhealthy
            return name, HealthCheckResult(
                component=name,
                status=HealthStatus.UNHEALTHY,
                error=f"{type(err).__name__}: {err}",
                category=category,
            )

    async def run_all(
        self,
        timeout: float = 5.0,
        *,
        category: HealthCheckCategory | str | None = None,
    ) -> AggregateHealthResult:
        """Run registered checks and aggregate the results."""
        requested_category = self._coerce_category(category)
        checks = self._collect_checks()

        if not checks:
            return AggregateHealthResult()

        results = await asyncio.gather(
            *[
                self._run_check(name, check, check_category, timeout)
                for name, check, check_category in checks
            ],
        )
        components = [result for _, result in results]
        if requested_category is not None:
            components = [
                result for result in components if result.category == requested_category
            ]
        return AggregateHealthResult(components=components)

    async def run_liveness(self, timeout: float = 5.0) -> AggregateHealthResult:
        """Run only liveness checks and aggregate the results."""
        return await self.run_all(
            timeout=timeout, category=HealthCheckCategory.LIVENESS
        )

    async def run_readiness(self, timeout: float = 5.0) -> AggregateHealthResult:
        """Run only readiness checks and aggregate the results."""
        return await self.run_all(
            timeout=timeout,
            category=HealthCheckCategory.READINESS,
        )

    async def run_startup(self, timeout: float = 5.0) -> AggregateHealthResult:
        """Run only startup checks and aggregate the results."""
        return await self.run_all(timeout=timeout, category=HealthCheckCategory.STARTUP)

    async def check_all(self, timeout: float = 5.0) -> dict[str, HealthCheckResult]:
        """Run health checks across all providers concurrently.

        Args:
            timeout: Maximum seconds to wait per provider health check.

        Returns:
            Mapping of provider name to HealthCheckResult.
        """
        result = await self.run_all(timeout=timeout)
        return {component.component: component for component in result.components}

    def get_module_health_providers(self, module_cls: type) -> list[Provider]:
        """Return the providers that contribute to the given module's health check.

        Uses the compiled module graph's health_providers configuration to determine
        which provider instances should be included in health checks for the module.

        Args:
            module_cls: The module class to get health providers for.

        Returns:
            List of booted Provider instances that contribute to this module's
            health check. Returns all providers for the module if health_providers
            is None, empty list if health_providers=[], or specific matching
            providers if health_providers=[...].

        Raises:
            RuntimeError: If called before the orchestrator has been booted
                (i.e., compiled graph is None).
        """
        compiled_graph = self._registry._compiled_graph
        if compiled_graph is None:
            raise RuntimeError("Orchestrator has not been booted yet")

        entries = compiled_graph.get_health_providers(module_cls)

        matched: list[Provider] = []
        for entry in entries:
            for provider in self._registry._providers.values():
                if entry.is_instance:
                    if entry.provider is provider:
                        matched.append(provider)
                        break
                elif entry.provider is type(provider):
                    matched.append(provider)
                    break

        return matched


__all__ = ["HealthCoordinator"]
