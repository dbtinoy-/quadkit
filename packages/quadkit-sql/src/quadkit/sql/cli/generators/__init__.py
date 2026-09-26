"""SQL CLI generators."""

from __future__ import annotations

from quadkit.sql.cli.generators.database_repository import DatabaseRepositoryGenerator
from quadkit.sql.cli.generators.entity_migration import EntityMigrationGenerator
from quadkit.sql.cli.generators.entity_model import EntityModelGenerator
from quadkit.sql.cli.generators.filter import FilterGenerator
from quadkit.sql.cli.generators.health_check import HealthCheckGenerator
from quadkit.sql.cli.generators.seeder import SeederGenerator
from quadkit.sql.cli.generators.service import ServiceGenerator

__all__ = [
    "DatabaseRepositoryGenerator",
    "EntityMigrationGenerator",
    "EntityModelGenerator",
    "FilterGenerator",
    "HealthCheckGenerator",
    "SeederGenerator",
    "ServiceGenerator",
]
