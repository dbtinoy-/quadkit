from __future__ import annotations

import re
from importlib import import_module
import pathlib
import tomllib

from quadkit.cache.cli.contributor import CacheCliContributor
from quadkit.cache.cli.generators.cache_repository import CacheRepositoryGenerator
from quadkit.contracts.cli.protocols import CliContributorProtocol
from quadkit.contracts.cli.types import GeneratorDefinition


class TestCacheCliContributor:
    def test_contributor_implements_protocol_shape_directly(self) -> None:
        contributor = CacheCliContributor()

        assert isinstance(contributor, CliContributorProtocol)
        assert CacheCliContributor.__bases__ == (object,)

    def test_contributor_id_is_cache(self) -> None:
        contributor = CacheCliContributor()

        assert contributor.contributor_id == "cache"

    def test_exposes_exactly_one_generator_named_cache_repo(self) -> None:
        contributor = CacheCliContributor()

        generators = contributor.get_generators()

        assert len(generators) == 1
        assert generators[0].name == "cache_repo"

    def test_generator_definition_fields(self) -> None:
        contributor = CacheCliContributor()

        definition = contributor.get_generators()[0]

        assert isinstance(definition, GeneratorDefinition)
        assert definition.contributor == "cache"
        assert definition.default_output_dir == "src/repositories"
        assert definition.category == "cache"

    def test_generator_path_is_package_local(self) -> None:
        contributor = CacheCliContributor()

        definition = contributor.get_generators()[0]

        assert definition.generator_path == (
            "quadkit.cache.cli.generators.cache_repository:CacheRepositoryGenerator"
        )


class TestCacheRepositoryGenerator:
    def test_generator_class_is_importable(self) -> None:
        contributor = CacheCliContributor()
        definition = contributor.get_generators()[0]

        module_path, _, class_name = definition.generator_path.partition(":")
        module = import_module(module_path)
        generator_class = getattr(module, class_name)

        assert isinstance(generator_class, type)

    def test_template_name_attribute_set(self) -> None:
        assert CacheRepositoryGenerator.template_name == "cache_repository.py.jinja2"

    def test_dry_run_returns_result_with_expected_file_path(
        self, tmp_path: pathlib.Path
    ) -> None:
        generator = CacheRepositoryGenerator(output_dir=tmp_path)
        result = generator.generate("Pet", dry_run=True)

        expected_file = tmp_path / "pet_repository.py"
        assert expected_file in result.files_created

    def test_dry_run_does_not_write_file(self, tmp_path: pathlib.Path) -> None:
        generator = CacheRepositoryGenerator(output_dir=tmp_path)
        generator.generate("Pet", dry_run=True)

        expected_file = tmp_path / "pet_repository.py"
        assert not expected_file.exists()

    # ------------------------------------------------------------------
    # Generated content tests (regression guards)
    # ------------------------------------------------------------------

    def _render(
        self,
        tmp_path: pathlib.Path,
        name: str = "Pet",
        *,
        fields_str: str | None = None,
    ) -> str:
        """Write and return the generated file content."""
        generator = CacheRepositoryGenerator(output_dir=tmp_path)
        generator.generate(name, fields_str=fields_str)
        return (tmp_path / f"{name.lower()}_repository.py").read_text()

    def test_generated_imports_cache_service_from_public_surface(
        self, tmp_path: pathlib.Path
    ) -> None:
        content = self._render(tmp_path)

        assert "from quadkit.cache import CacheService" in content

    def test_generated_imports_repository_protocol_from_contracts(
        self, tmp_path: pathlib.Path
    ) -> None:
        content = self._render(tmp_path)

        assert "from quadkit.contracts.data import RepositoryProtocol" in content

    def test_generated_no_internal_cache_service_import(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Regression: must not import from internal cache.service.core."""
        content = self._render(tmp_path)

        assert "from quadkit.cache.service.core" not in content

    def test_generated_no_sql_internal_import(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Regression: must not import from quadkit.sql.repositories.base."""
        content = self._render(tmp_path)

        assert "from quadkit.sql.repositories.base" not in content

    def test_generated_init_accepts_repository_and_cache(
        self, tmp_path: pathlib.Path
    ) -> None:
        content = self._render(tmp_path)

        # Both dependencies must appear in __init__ signature
        assert "repository: RepositoryProtocol[PetEntity]" in content
        assert "cache: CacheService" in content

    def test_generated_get_by_id_falls_back_to_repository(
        self, tmp_path: pathlib.Path
    ) -> None:
        content = self._render(tmp_path)

        # Cache-aside read path must call the underlying repository
        assert "get_by_id" in content
        assert "self._repository.get(" in content

    def test_generated_list_all_falls_back_to_repository(
        self, tmp_path: pathlib.Path
    ) -> None:
        content = self._render(tmp_path)

        assert "list_all" in content
        assert "self._repository.list(" in content

    def test_generated_save_delegates_and_invalidates(
        self, tmp_path: pathlib.Path
    ) -> None:
        content = self._render(tmp_path)

        assert "self._repository.save(" in content
        assert "self._cache.delete(" in content

    def test_generated_delete_delegates_and_invalidates(
        self, tmp_path: pathlib.Path
    ) -> None:
        content = self._render(tmp_path)

        assert "self._repository.delete(" in content
        # Both item key and list-all key must be evicted
        assert content.count("self._cache.delete(") >= 2  # save + delete paths

    def test_generated_default_fields_id_and_name(
        self, tmp_path: pathlib.Path
    ) -> None:
        """When no fields_str is provided the entity gets id:int and name:str."""
        content = self._render(tmp_path)

        assert "id: int" in content
        assert "name: str" in content

    def test_generated_respects_custom_fields(
        self, tmp_path: pathlib.Path
    ) -> None:
        content = self._render(tmp_path, fields_str="species:str,age:int")

        assert "species: str" in content
        assert "age: int" in content

    def test_generated_pk_param_avoids_builtin_shadow(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Default pk is 'id'; method signatures must use 'entity_id' instead."""
        content = self._render(tmp_path)

        # Should use entity_id not bare id as a parameter name
        assert "entity_id: int" in content
        # The bare parameter name 'id' must not appear in a def signature
        for match in re.finditer(r"def \w+\(self.*?\):", content, re.DOTALL):
            assert " id:" not in match.group(), (
                "Builtin 'id' used as parameter name in: " + match.group()
            )

    def test_generated_custom_pk_used_in_signatures(
        self, tmp_path: pathlib.Path
    ) -> None:
        """When the PK field is not named 'id' it appears verbatim in signatures."""
        generator = CacheRepositoryGenerator(output_dir=tmp_path)
        generator.generate("Order", fields_str="order_id:str,total:float")
        content = (tmp_path / "order_repository.py").read_text()

        # pk_name=order_id is not a builtin, so it must be used as-is
        assert "order_id: str" in content

    def test_generated_entity_is_dataclass(self, tmp_path: pathlib.Path) -> None:
        content = self._render(tmp_path)

        assert "@dataclass" in content


class TestCacheCliContributorPyproject:
    def test_cache_contributor_entry_point_declared(self) -> None:
        pyproject_path = pathlib.Path(__file__).resolve().parents[2] / "pyproject.toml"
        data = tomllib.loads(pyproject_path.read_text())

        entry_points = data.get("project", {}).get("entry-points", {})
        group = entry_points.get("quadkit.cli.contributors", {})

        assert group["cache"] == "quadkit.cache.cli.contributor:CacheCliContributor"
