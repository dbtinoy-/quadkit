from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
import time
from typing import Any

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.logging import get_logger
from quadkit.monitor.health.base import HealthCheck
from quadkit.monitor.health.sanitize import safe_error_message
from quadkit.primitives.registry import Registry

logger = get_logger(__name__)


class HealthCheckRegistry(Registry[str, HealthCheck]):
    """Registry for managing health checks.

    Extends :class:`Registry` for unified introspection.  Sidecar lists
    track which checks participate in liveness vs readiness probes.
    """

    def __init__(self) -> None:
        super().__init__(name="health.checks", allow_overwrite=True)
        self._liveness_checks: list[str] = []
        self._readiness_checks: list[str] = []

    def _register(
        self,
        check: HealthCheck,
        liveness: bool = True,
        readiness: bool = True,
    ) -> None:
        super().register(check.name, check)
        if liveness and check.name not in self._liveness_checks:
            self._liveness_checks.append(check.name)
        if readiness and check.name not in self._readiness_checks:
            self._readiness_checks.append(check.name)

    def _register_function(
        self,
        name: str,
        func: Callable,
        critical: bool = True,
        liveness: bool = True,
        readiness: bool = True,
    ) -> None:
        from quadkit.monitor.health.functions import FunctionHealthCheck

        check = FunctionHealthCheck(name, func, critical)
        self._register(check, liveness, readiness)

    async def _run_named(
        self, name: str, check_names: list[str]
    ) -> dict[str, Any] | None:
        """Run a single registered check and return its result dict.

        Args:
            name: Name of the registered check.
            check_names: The probe list (liveness or readiness) the name
                must appear in.

        Returns:
            The check's result dict, or ``None`` when the name is not in
            ``check_names`` or is not registered.
        """
        if name not in check_names:
            return None
        check = self.get(name)
        if not check:
            return None

        try:
            start = time.time()
            result = await check.check()
            result = replace(result, duration_ms=(time.time() - start) * 1000)
            return result.to_dict()
        except Exception as e:  # noqa: BLE001 — any check failure is UNHEALTHY, never a raw raise
            logger.exception("Health check %s error", name)
            result = HealthCheckResult(
                component=name,
                status=HealthStatus.UNHEALTHY,
                message=safe_error_message(e),
            )
            return result.to_dict()

    async def run_check(self, name: str) -> dict[str, Any]:
        """Run a single named check and return its raw result dict.

        Args:
            name: Name of the registered check.

        Returns:
            The check's result dict, or an ``UNKNOWN`` dict when the name
            is not registered in either probe list.
        """
        result = None
        if name in self._liveness_checks:
            result = await self._run_named(name, self._liveness_checks)
        elif name in self._readiness_checks:
            result = await self._run_named(name, self._readiness_checks)
        if result is None:
            return {"status": "UNKNOWN", "component": name}
        return result

    async def _check_liveness(self) -> dict[str, Any]:
        results = []
        overall_status = HealthStatus.HEALTHY

        for check_name in self._liveness_checks:
            result = await self._run_named(check_name, self._liveness_checks)
            if result is None:
                continue

            results.append(result)
            if result["status"] == HealthStatus.UNHEALTHY.value:
                overall_status = HealthStatus.UNHEALTHY

        return {
            "status": overall_status.value,
            "checks": results,
            "timestamp": time.time(),
        }

    async def _check_readiness(self) -> dict[str, Any]:
        results = []
        overall_status = HealthStatus.HEALTHY

        for check_name in self._readiness_checks:
            check = self.get(check_name)
            result = await self._run_named(check_name, self._readiness_checks)
            if result is None:
                continue

            results.append(result)
            if (
                check is not None
                and check.critical
                and result["status"] != HealthStatus.HEALTHY.value
            ):
                overall_status = HealthStatus.UNHEALTHY
            elif (
                result["status"] != HealthStatus.HEALTHY.value
                and overall_status == HealthStatus.HEALTHY
            ):
                overall_status = HealthStatus.DEGRADED

        return {
            "status": overall_status.value,
            "checks": results,
            "timestamp": time.time(),
        }

    # --- HealthCheckRegistryProtocol Compliance ---

    def add(
        self,
        name: str,
        check: Callable[[], Any],
        *,
        timeout: float | None = None,
        critical: bool = True,
        category: Any = None,
    ) -> None:
        """Add a health check to satisfy HealthCheckRegistryProtocol."""
        is_liveness = (
            "liveness" in str(category).lower() or "startup" in str(category).lower()
        )
        is_readiness = "readiness" in str(category).lower() or category is None
        self._register_function(
            name,
            check,
            critical=critical,
            liveness=is_liveness,
            readiness=is_readiness,
        )

    async def run_all(self) -> tuple[Any, dict[str, Any]]:
        l_res = await self._check_liveness()
        r_res = await self._check_readiness()

        status = HealthStatus.HEALTHY
        if (
            l_res["status"] == HealthStatus.UNHEALTHY.value
            or r_res["status"] == HealthStatus.UNHEALTHY.value
        ):
            status = HealthStatus.UNHEALTHY
        elif (
            l_res["status"] == HealthStatus.DEGRADED.value
            or r_res["status"] == HealthStatus.DEGRADED.value
        ):
            status = HealthStatus.DEGRADED

        return status, {"liveness": l_res, "readiness": r_res}

    async def run_liveness(self) -> tuple[Any, dict[str, Any]]:
        res = await self._check_liveness()
        try:
            status = HealthStatus(res["status"])
        except ValueError:
            status = HealthStatus.UNKNOWN
        return status, res

    async def run_readiness(self) -> tuple[Any, dict[str, Any]]:
        res = await self._check_readiness()
        try:
            status = HealthStatus(res["status"])
        except ValueError:
            status = HealthStatus.UNKNOWN
        return status, res

    async def run_startup(self) -> tuple[Any, dict[str, Any]]:
        return await self.run_liveness()

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Satisfy HealthCheckProtocol."""
        status_val, details = await self.run_all()
        return HealthCheckResult(
            component="health_registry",
            status=status_val,
            details=details,
        )
