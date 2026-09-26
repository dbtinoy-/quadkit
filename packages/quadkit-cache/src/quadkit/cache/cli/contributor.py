"""Cache CLI contributor definitions."""

from __future__ import annotations

from quadkit.contracts.cli.contributions import (
    CommandContribution,
    DoctorCheckContribution,
    HealthCheckContribution,
    ShellContextContribution,
)
from quadkit.contracts.cli.types import GeneratorDefinition

# (name, description, generator_path, output_dir) — titles derive via make()
_SPECS: tuple[tuple[str, str, str, str], ...] = (
    (
        "cache_repo",
        "Generate a cache-backed repository with TTL support",
        "quadkit.cache.cli.generators.cache_repository:CacheRepositoryGenerator",
        "src/repositories",
    ),
)

# Titles that make() cannot derive exactly.
_TITLES: dict[str, str] = {"cache_repo": "Generate Cache Repository"}

_GENERATOR_DEFINITIONS: tuple[GeneratorDefinition, ...] = tuple(
    GeneratorDefinition.make(
        name,
        description=description,
        generator_path=generator_path,
        output_dir=output_dir,
        contributor="cache",
        category="cache",
        title=_TITLES.get(name),
    )
    for name, description, generator_path, output_dir in _SPECS
)


class CacheCliContributor:
    """CLI contributor for the quadkit-cache package."""

    @property
    def contributor_id(self) -> str:
        """Return the contributor identifier."""
        return "cache"

    def get_generators(self) -> list[GeneratorDefinition]:
        """Return generator definitions for cache."""
        return list(_GENERATOR_DEFINITIONS)

    def get_commands(self) -> list[CommandContribution]:
        """Return the contributed `cache` command group."""
        return [
            CommandContribution(
                name="cache",
                help="Cache inspection and management commands",
                app_factory_path="quadkit.cache.cli.commands:create_cache_app",
                contributor="cache",
                category="infrastructure",
                requires_app_context=True,
            ),
        ]

    def get_health_checks(self) -> list[HealthCheckContribution]:
        """Return cache connectivity health check."""
        return [
            HealthCheckContribution(
                name="cache_connection",
                description="Verify cache backend connectivity",
                check_path="quadkit.cache.cli.checks:check_cache_connection",
                contributor="cache",
                category="infrastructure",
                timeout=5.0,
            ),
        ]

    def get_doctor_checks(self) -> list[DoctorCheckContribution]:
        """Return cache configuration doctor checks."""
        return [
            DoctorCheckContribution(
                name="cache_backend_configured",
                description="Check cache backend is configured in application.yaml",
                check_path="quadkit.cache.cli.doctor:check_cache_configured",
                contributor="cache",
                category="infrastructure",
            ),
        ]

    def get_shell_context(self) -> list[ShellContextContribution]:
        """Return cache shell context."""
        return [
            ShellContextContribution(
                name="cache",
                description="Cache backend for interactive use",
                factory_path="quadkit.cache.cli.shell:provide_cache",
                contributor="cache",
            ),
        ]

    def get_hooks(self) -> list:
        """Return no hook contributions."""
        return []


__all__ = ["CacheCliContributor"]
