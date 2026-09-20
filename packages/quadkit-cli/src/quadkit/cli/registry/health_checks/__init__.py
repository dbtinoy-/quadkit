"""Health check plugin modules, grouped by domain cluster."""

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

__all__ = [
    "CheckResult",
    "CheckStatus",
    "ConfigFileCheck",
    "CrossExtensionImportCheck",
    "DependenciesCheck",
    "DockerCheck",
    "GitCheck",
    "HealthCheck",
    "InstalledQuadkitPackagesCheck",
    "PackageManagerCheck",
    "ProjectStructureCheck",
    "ProviderPackagesCheck",
    "PythonVersionCheck",
    "RequiredToolsCheck",
]
