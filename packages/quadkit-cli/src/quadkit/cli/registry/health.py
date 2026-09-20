"""Health check registry for system diagnostics.

This module provides a registry pattern for running various health checks
on the system, configuration, and dependencies. The check implementations
live in the ``health_checks`` package (one module per domain cluster) and
are re-exported here so the public surface of this module is unchanged.
"""

from __future__ import annotations

from quadkit.cli.registry.health_checks.base import (
    CheckResult as CheckResult,
)
from quadkit.cli.registry.health_checks.base import (
    CheckStatus as CheckStatus,
)
from quadkit.cli.registry.health_checks.base import (
    HealthCheck as HealthCheck,
)
from quadkit.cli.registry.health_checks.deps import (
    InstalledQuadkitPackagesCheck as InstalledQuadkitPackagesCheck,
)
from quadkit.cli.registry.health_checks.project import (
    ConfigFileCheck as ConfigFileCheck,
)
from quadkit.cli.registry.health_checks.project import (
    DependenciesCheck as DependenciesCheck,
)
from quadkit.cli.registry.health_checks.project import (
    ProjectStructureCheck as ProjectStructureCheck,
)
from quadkit.cli.registry.health_checks.providers import (
    CrossExtensionImportCheck as CrossExtensionImportCheck,
)
from quadkit.cli.registry.health_checks.providers import (
    ProviderPackagesCheck as ProviderPackagesCheck,
)
from quadkit.cli.registry.health_checks.python_env import (
    PythonVersionCheck as PythonVersionCheck,
)
from quadkit.cli.registry.health_checks.tools import (
    PackageManagerCheck as PackageManagerCheck,
)
from quadkit.cli.registry.health_checks.tools import (
    RequiredToolsCheck as RequiredToolsCheck,
)
from quadkit.cli.registry.health_checks.vcs_docker import (
    DockerCheck as DockerCheck,
)
from quadkit.cli.registry.health_checks.vcs_docker import (
    GitCheck as GitCheck,
)


class HealthCheckRegistry:
    """Registry for health checks.

    Instances are always empty — use :meth:`with_defaults` for the
    in-package built-ins or :meth:`register` for plugin checks.
    """

    def __init__(self) -> None:
        self._checks: list[type[HealthCheck]] = []

    def register(self, check: type[HealthCheck]) -> None:
        """Register a health check class."""
        self._checks.append(check)

    def get_all_checks(self) -> list[type[HealthCheck]]:
        """Get all registered health check classes."""
        return self._checks.copy()

    def get_checks_by_category(self) -> dict[str, list[HealthCheck]]:
        """Get all checks organized by category."""
        by_category: dict[str, list[HealthCheck]] = {}

        for check_class in self.get_all_checks():
            instance = check_class()
            category = instance.get_category()
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(instance)

        return by_category

    @classmethod
    def _default_entries(cls) -> tuple[type[HealthCheck], ...]:
        """The complete in-package built-in set, declared exactly once."""
        return (
            PythonVersionCheck,
            PackageManagerCheck,
            RequiredToolsCheck,
            ConfigFileCheck,
            ProjectStructureCheck,
            DependenciesCheck,
            GitCheck,
            DockerCheck,
            InstalledQuadkitPackagesCheck,
            ProviderPackagesCheck,
            CrossExtensionImportCheck,
        )

    @classmethod
    def with_defaults(cls) -> HealthCheckRegistry:
        """Return an instance populated with the built-in checks."""
        registry = cls()
        for entry in cls._default_entries():
            registry.register(entry)
        return registry


def run_health_checks() -> dict[str, list[CheckResult]]:
    """Run all health checks and return results organized by category."""
    by_category = HealthCheckRegistry.with_defaults().get_checks_by_category()
    results: dict[str, list[CheckResult]] = {}

    for category, checks in by_category.items():
        results[category] = []
        for check in checks:
            try:
                result = check.check()
            except Exception as e:  # noqa: BLE001 — health check failures are failed results
                result = CheckResult(
                    name=check.get_name(),
                    status=CheckStatus.FAIL,
                    message=f"Check failed with error: {e}",
                )
            results[category].append(result)

    return results


__all__ = [
    "CheckResult",
    "CheckStatus",
    "ConfigFileCheck",
    "CrossExtensionImportCheck",
    "DependenciesCheck",
    "DockerCheck",
    "GitCheck",
    "HealthCheck",
    "HealthCheckRegistry",
    "InstalledQuadkitPackagesCheck",
    "PackageManagerCheck",
    "ProjectStructureCheck",
    "ProviderPackagesCheck",
    "PythonVersionCheck",
    "RequiredToolsCheck",
    "run_health_checks",
]
