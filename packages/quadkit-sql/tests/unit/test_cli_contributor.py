from __future__ import annotations

from importlib import import_module
import pathlib
import tomllib

from quadkit.contracts.cli.protocols import CliContributorProtocol
from quadkit.contracts.cli.types import GeneratorDefinition
from quadkit.sql.cli.contributor import SqlCliContributor


class TestSqlCliContributor:
    def test_contributor_implements_protocol_shape_directly(self) -> None:
        contributor = SqlCliContributor()

        assert isinstance(contributor, CliContributorProtocol)
        assert SqlCliContributor.__bases__ == (object,)

    def test_contributor_id_is_sql(self) -> None:
        contributor = SqlCliContributor()

        assert contributor.contributor_id == "sql"

    def test_exposes_exact_expected_generator_names(self) -> None:
        contributor = SqlCliContributor()

        generators = contributor.get_generators()
        names = [generator.name for generator in generators]

        assert names == [
            "repository",
            "filter",
            "seeder",
            "health",
            "domain",
            "migration",
            "service",
        ]

    def test_generators_are_valid_definitions(self) -> None:
        contributor = SqlCliContributor()

        for generator in contributor.get_generators():
            assert isinstance(generator, GeneratorDefinition)
            assert generator.contributor == "sql"

    def test_generator_paths_are_package_local(self) -> None:
        contributor = SqlCliContributor()

        generator_paths = {
            generator.name: generator.generator_path
            for generator in contributor.get_generators()
        }

        assert generator_paths == {
            "repository": "quadkit.sql.cli.generators.database_repository:DatabaseRepositoryGenerator",
            "filter": "quadkit.sql.cli.generators.filter:FilterGenerator",
            "seeder": "quadkit.sql.cli.generators.seeder:SeederGenerator",
            "health": "quadkit.sql.cli.generators.health_check:HealthCheckGenerator",
            "domain": "quadkit.sql.cli.generators.entity_model:EntityModelGenerator",
            "migration": "quadkit.sql.cli.generators.entity_migration:EntityMigrationGenerator",
            "service": "quadkit.sql.cli.generators.service:ServiceGenerator",
        }

    def test_generator_classes_are_importable(self) -> None:
        contributor = SqlCliContributor()

        for generator in contributor.get_generators():
            module_path, _, class_name = generator.generator_path.partition(":")
            module = import_module(module_path)
            generator_class = getattr(module, class_name)

            assert isinstance(generator_class, type)


class TestSqlCliContributorPyproject:
    def test_sql_contributor_entry_point_declared(self) -> None:
        pyproject_path = pathlib.Path(__file__).parent.parent.parent / "pyproject.toml"
        data = tomllib.loads(pyproject_path.read_text())

        entry_points = data.get("project", {}).get("entry-points", {})
        group = entry_points.get("quadkit.cli.contributors", {})

        assert group["sql"] == "quadkit.sql.cli.contributor:SqlCliContributor"
