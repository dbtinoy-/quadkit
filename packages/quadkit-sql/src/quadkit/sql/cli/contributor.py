"""SQL CLI contributor definitions."""

from __future__ import annotations

from quadkit.contracts.cli.contributions import (
    CommandContribution,
    DoctorCheckContribution,
    HealthCheckContribution,
    ShellContextContribution,
)
from quadkit.contracts.cli.types import GeneratorDefinition, GeneratorOption

_FIELDS_OPTION = GeneratorOption(
    name="fields",
    type_hint="str",
    description="Field spec in name:type[?][!unique][!fk=Model][=default] format",
)

# (name, description, generator_path, output_dir) — titles derive via make()
_SPECS: tuple[tuple[str, str, str, str], ...] = (
    (
        "repository",
        "Generate a database repository with query methods",
        "quadkit.sql.cli.generators.database_repository:DatabaseRepositoryGenerator",
        "src/repositories",
    ),
    (
        "filter",
        "Generate a query filter for database models",
        "quadkit.sql.cli.generators.filter:FilterGenerator",
        "src/filters",
    ),
    (
        "seeder",
        "Generate a database seeder for test/dev data",
        "quadkit.sql.cli.generators.seeder:SeederGenerator",
        "src/seeders",
    ),
    (
        "health",
        "Generate a database health check",
        "quadkit.sql.cli.generators.health_check:HealthCheckGenerator",
        "src/health",
    ),
    (
        "domain",
        "Generate a Pydantic domain entity with Create/Update DTOs",
        "quadkit.sql.cli.generators.entity_model:EntityModelGenerator",
        "src/domains",
    ),
    (
        "migration",
        "Generate a chained alembic migration for an entity",
        "quadkit.sql.cli.generators.entity_migration:EntityMigrationGenerator",
        "migrations/versions",
    ),
    (
        "service",
        "Generate a service with unit of work",
        "quadkit.sql.cli.generators.service:ServiceGenerator",
        "src/services",
    ),
)

_OPTIONS: dict[str, tuple[GeneratorOption, ...]] = {
    "repository": (_FIELDS_OPTION,),
    "filter": (
        _FIELDS_OPTION,
        GeneratorOption(
            name="exception_type",
            type_hint="str",
            description="Base exception type",
        ),
    ),
    "seeder": (_FIELDS_OPTION,),
    "service": (_FIELDS_OPTION,),
    "domain": (_FIELDS_OPTION,),
    "migration": (),
    "health": (
        GeneratorOption(
            name="critical",
            type_hint="bool",
            description="Fail health checks on error",
        ),
    ),
}

# Titles that make() cannot derive exactly.
_TITLES: dict[str, str] = {"health": "Generate Health Check"}

_GENERATOR_DEFINITIONS: tuple[GeneratorDefinition, ...] = tuple(
    GeneratorDefinition.make(
        name,
        description=description,
        generator_path=generator_path,
        output_dir=output_dir,
        contributor="sql",
        category="database",
        options=_OPTIONS.get(name, ()),
        title=_TITLES.get(name),
    )
    for name, description, generator_path, output_dir in _SPECS
)


class SqlCliContributor:
    """CLI contributor for the quadkit-sql package."""

    @property
    def contributor_id(self) -> str:
        """Return the contributor identifier."""
        return "sql"

    def get_generators(self) -> list[GeneratorDefinition]:
        """Return generator definitions for SQL."""
        return list(_GENERATOR_DEFINITIONS)

    def get_commands(self) -> list[CommandContribution]:
        """Return the contributed `db` command group."""
        return [
            CommandContribution(
                name="db",
                help="Database migration and management commands",
                app_factory_path="quadkit.sql.cli.commands:create_db_app",
                contributor="sql",
                category="database",
                requires_app_context=False,
            ),
        ]

    def get_health_checks(self) -> list[HealthCheckContribution]:
        """Return database connectivity health check."""
        return [
            HealthCheckContribution(
                name="database_connection",
                description="Verify database connectivity and migration status",
                check_path="quadkit.sql.cli.checks:check_database_connection",
                contributor="sql",
                category="database",
                timeout=15.0,
                critical=True,
            ),
        ]

    def get_doctor_checks(self) -> list[DoctorCheckContribution]:
        """Return database configuration doctor checks."""
        return [
            DoctorCheckContribution(
                name="database_url_configured",
                description="Check DATABASE_URL or application.yaml database config exists",
                check_path="quadkit.sql.cli.doctor:check_database_url",
                contributor="sql",
                category="database",
            ),
            DoctorCheckContribution(
                name="migrations_dir_exists",
                description="Check migrations directory exists with valid structure",
                check_path="quadkit.sql.cli.doctor:check_migrations_dir",
                contributor="sql",
                category="database",
                can_fix=True,
            ),
        ]

    def get_shell_context(self) -> list[ShellContextContribution]:
        """Return database shell context contributions."""
        return [
            ShellContextContribution(
                name="db",
                description="Database provider for interactive queries",
                factory_path="quadkit.sql.cli.shell:provide_db",
                contributor="sql",
            ),
            ShellContextContribution(
                name="migration",
                description="Migration runner for interactive use",
                factory_path="quadkit.sql.cli.shell:provide_migration",
                contributor="sql",
            ),
        ]

    def get_hooks(self) -> list:
        """Return no hook contributions."""
        return []


__all__ = ["SqlCliContributor"]
