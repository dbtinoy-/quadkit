"""Storage CLI contributor definitions."""

from __future__ import annotations

from quadkit.contracts.cli.contributions import (
    DoctorCheckContribution,
    HealthCheckContribution,
)
from quadkit.contracts.cli.types import GeneratorDefinition

# (name, description, generator_path, output_dir) — titles derive via make()
_SPECS: tuple[tuple[str, str, str, str], ...] = (
    (
        "storage_driver",
        "Generate a file storage backend driver",
        "quadkit.storage.cli.generators.storage_driver:StorageDriverGenerator",
        "src/storage/backends",
    ),
)

_GENERATOR_DEFINITIONS: tuple[GeneratorDefinition, ...] = tuple(
    GeneratorDefinition.make(
        name,
        description=description,
        generator_path=generator_path,
        output_dir=output_dir,
        contributor="storage",
    )
    for name, description, generator_path, output_dir in _SPECS
)


class StorageCliContributor:
    """CLI contributor for the quadkit-storage package."""

    @property
    def contributor_id(self) -> str:
        """Return the contributor identifier."""
        return "storage"

    def get_generators(self) -> list[GeneratorDefinition]:
        """Return generator definitions for storage."""
        return list(_GENERATOR_DEFINITIONS)

    def get_commands(self) -> list:
        """Return no command contributions."""
        return []

    def get_health_checks(self) -> list[HealthCheckContribution]:
        """Return storage backend connectivity health check."""
        return [
            HealthCheckContribution(
                name="storage_backend_connection",
                description="Verify file storage backend connectivity",
                check_path="quadkit.storage.cli.checks:check_storage_backend",
                contributor="storage",
                category="storage",
                timeout=10.0,
            ),
        ]

    def get_doctor_checks(self) -> list[DoctorCheckContribution]:
        """Return storage configuration doctor checks."""
        return [
            DoctorCheckContribution(
                name="storage_configured",
                description="Check storage backend is configured in application.yaml",
                check_path="quadkit.storage.cli.doctor:check_storage_configured",
                contributor="storage",
                category="storage",
            ),
        ]

    def get_shell_context(self) -> list:
        """Return no shell context contributions."""
        return []

    def get_hooks(self) -> list:
        """Return no hook contributions."""
        return []


__all__ = ["StorageCliContributor"]
