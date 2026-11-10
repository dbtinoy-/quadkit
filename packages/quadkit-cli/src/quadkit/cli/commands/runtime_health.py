"""Explicit, application-owned execution of async runtime health contributions."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from importlib import import_module
import math

from quadkit.app.base import Application, AppState
from quadkit.cli.registry.health import CheckResult, CheckStatus
from quadkit.contracts.cli.contributions import HealthCheckContribution
from quadkit.contracts.core import HealthCheckResult, HealthStatus


def load_symbol(path: str) -> object:
    """Load an explicit module:attribute target; never evaluate expressions."""
    module, separator, attribute = path.partition(":")
    if (
        not separator
        or not module
        or not attribute
        or any(
            not part.isidentifier()
            for part in (*module.split("."), *attribute.split("."))
        )
    ):
        raise ValueError("Expected a module:attribute target")
    value: object = import_module(module)
    for part in attribute.split("."):
        value = getattr(value, part)
    return value


def _valid_timeout(value: float) -> bool:
    return not isinstance(value, bool) and math.isfinite(value) and value > 0


def select_checks(
    available: Sequence[HealthCheckContribution], requested: Sequence[str]
) -> list[HealthCheckContribution]:
    """Require unambiguous contributor:name selections before booting anything."""
    if not requested or len(set(requested)) != len(requested):
        raise ValueError("Select distinct runtime checks with --check contributor:name")
    checks: dict[str, HealthCheckContribution] = {}
    for check in available:
        key = f"{check.contributor}:{check.name}"
        if key not in requested:
            continue
        if key in checks:
            raise ValueError("Selected runtime check has ambiguous contributions")
        if not _valid_timeout(check.timeout) or type(check.critical) is not bool:
            raise ValueError(
                "Selected runtime check has invalid timeout or critical metadata"
            )
        checks[key] = check
    if set(requested) != set(checks):
        raise ValueError("Unknown runtime check; use an installed contributor:name")
    return [checks[key] for key in requested]


async def run_runtime_checks(
    target: str,
    checks: Sequence[HealthCheckContribution],
    *,
    lifecycle_timeout: float = 60.0,
) -> list[CheckResult]:
    """Start a fresh selected Application, probe its container, always stop it.

    Application.start owns partial-boot cleanup. We additionally stop in finally,
    including probe cancellation. An already-owned/running application is rejected
    before lifecycle changes. No ASGI server or replacement provider is started.
    """
    if not _valid_timeout(lifecycle_timeout):
        raise ValueError("Lifecycle timeout must be finite and positive")
    if not checks:
        raise ValueError("At least one explicit runtime check is required")
    checks = select_checks(checks, [f"{c.contributor}:{c.name}" for c in checks])
    application = load_symbol(target)
    if (
        not isinstance(application, Application)
        or application.state is not AppState.CREATED
    ):
        raise ValueError(
            "--app must name a Quadkit Application instance in CREATED state"
        )
    results: list[CheckResult] = []
    try:
        async with asyncio.timeout(lifecycle_timeout):
            await application.start()
        for check in checks:
            name = f"{check.contributor}:{check.name}"
            try:
                async with asyncio.timeout(check.timeout):
                    probe = load_symbol(check.check_path)
                    if not callable(probe):
                        raise TypeError("Health contribution must be callable")
                    result = await probe(application.container)
                    if not isinstance(result, HealthCheckResult) or not isinstance(
                        result.status, HealthStatus
                    ):
                        raise TypeError(
                            "Health contribution must return HealthCheckResult"
                        )
                    status = result.status
            except Exception:  # CLI probe boundary; cancellation propagates to cleanup.
                status = HealthStatus.UNHEALTHY
            disposition = (
                CheckStatus.PASS
                if status is HealthStatus.HEALTHY
                else CheckStatus.FAIL
                if check.critical
                else CheckStatus.WARNING
            )
            # Never echo provider error/message text, which can contain credentials.
            results.append(
                CheckResult(name=name, status=disposition, message=status.value)
            )
    finally:
        async with asyncio.timeout(lifecycle_timeout):
            await application.stop()
    return results
