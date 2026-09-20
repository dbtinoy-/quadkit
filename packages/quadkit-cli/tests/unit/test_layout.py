"""Tests for the canonical generator -> path layout module."""

from __future__ import annotations

from pathlib import Path

import pytest

from quadkit.cli.layout import (
    component_packages,
    read_project_layout,
    resolve_output_dir,
    validate_definition,
)


class TestResolveOutputDir:
    """Per-node generator path resolution.

    There is one project layout, so nothing here is parametrised over a
    structure any more. Two questions decide every path: is the component
    cross-cutting, and is the node in a module.
    """

    def test_components_nest_inside_the_app_package(self) -> None:
        assert (
            resolve_output_dir("src/controllers", app_package="my_app")
            == "src/my_app/controllers"
        )
        assert (
            resolve_output_dir("src/vector/collections", app_package="my_app")
            == "src/my_app/shared/vector/collections"
        )
        assert resolve_output_dir("src", app_package="my_app") == "src/my_app"

    def test_root_dirs_stay_at_the_project_root(self) -> None:
        assert resolve_output_dir("tests/unit", app_package="my_app") == "tests/unit"
        assert (
            resolve_output_dir("migrations/versions", app_package="my_app")
            == "migrations/versions"
        )

    def test_cross_cutting_components_land_in_shared(self) -> None:
        for default, expected in (
            ("src/errors", "src/my_app/shared/errors"),
            ("src/filters", "src/my_app/shared/filters"),
            ("src/schema", "src/my_app/shared/schema"),
            ("src/schema/dataloaders", "src/my_app/shared/schema/dataloaders"),
            ("src/vector/collections", "src/my_app/shared/vector/collections"),
            ("src/providers", "src/my_app/shared/providers"),
            ("src/storage/backends", "src/my_app/shared/storage/backends"),
        ):
            assert resolve_output_dir(default, app_package="my_app") == expected

    def test_cross_cutting_components_ignore_a_module(self) -> None:
        """Scope is legal on a shared kind; it just does not move the file."""
        for default in ("src/errors", "src/schema/dataloaders"):
            assert resolve_output_dir(
                default, app_package="my_app", module="auth"
            ) == resolve_output_dir(default, app_package="my_app")

    def test_module_local_components_without_a_module(self) -> None:
        """The state every node starts in: at the app root, not an error."""
        for default, expected in (
            ("src/controllers", "src/my_app/controllers"),
            ("src/domains", "src/my_app/domains"),
            ("src/services", "src/my_app/services"),
            ("src/repositories", "src/my_app/repositories"),
            ("src/events", "src/my_app/events"),
            ("src/admin/actions", "src/my_app/admin/actions"),
        ):
            assert resolve_output_dir(default, app_package="my_app") == expected

    def test_module_local_components_with_a_module(self) -> None:
        assert (
            resolve_output_dir(
                "src/controllers", app_package="my_app", module="auth"
            )
            == "src/my_app/modules/auth/controllers"
        )
        assert (
            resolve_output_dir(
                "src/admin/resources", app_package="my_app", module="admin"
            )
            == "src/my_app/modules/admin/admin/resources"
        )

    def test_tests_follow_their_module(self) -> None:
        assert (
            resolve_output_dir("tests/unit", app_package="my_app", module="billing")
            == "src/my_app/modules/billing/tests"
        )

    def test_resource_resolves_to_the_package_root(self) -> None:
        assert (
            resolve_output_dir("src", app_package="my_app", generator="resource")
            == "src/my_app"
        )
        assert (
            resolve_output_dir(
                "src", app_package="my_app", generator="resource", module="auth"
            )
            == "src/my_app/modules/auth"
        )

    def test_src_root_generators(self) -> None:
        assert (
            resolve_output_dir("src", app_package="my_app", generator="mcp-server")
            == "src/my_app"
        )

    def test_unknown_output_dir_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown generator output directory"):
            resolve_output_dir("migrations/other", app_package="my_app")


class TestValidateDefinition:
    """Alignment between generator definitions and the canonical map."""

    def test_aligned_definitions(self) -> None:
        assert validate_definition("controller", "src/controllers") is None
        assert validate_definition("graphql", "src/schema") is None
        assert validate_definition("dataloader", "src/schema/dataloaders") is None
        assert (
            validate_definition("vector_collection", "src/vector/collections")
            is None
        )
        assert validate_definition("migration", "migrations/versions") is None
        assert validate_definition("seeder", "seeds") is None
        assert validate_definition("test", "tests/unit") is None
        assert validate_definition("mcp-server", "src") is None
        assert validate_definition("resource", "src") is None

    def test_drift_is_detected(self) -> None:
        assert validate_definition("controller", "src/schema") is not None
        assert validate_definition("graphql", "src/controllers") is not None
        assert validate_definition("controller", "src") is not None
        assert validate_definition("unknown", "src/nowhere") is not None


class TestReadProjectLayout:
    """Project metadata discovery from pyproject.toml."""

    def test_no_pyproject_returns_the_default_package(self, tmp_path: Path) -> None:
        layout = read_project_layout(tmp_path)
        assert layout.app_package == "app"
        assert layout.declared is False

    def test_reads_the_app_package_from_the_module_target(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.quadkit]\nmodule = "my_app.app:app"\n'
        )
        layout = read_project_layout(tmp_path)
        assert layout.app_package == "my_app"
        assert layout.declared is True
        assert layout.module_target() == "my_app.app:app"

    def test_a_stale_structure_key_is_ignored(self, tmp_path: Path) -> None:
        """Projects generated before the collapse still resolve.

        The key is not read, not validated and not migrated: it is simply
        not part of the layout any more, and a project carrying one behaves
        exactly like a project that does not.
        """
        (tmp_path / "pyproject.toml").write_text(
            '[tool.quadkit]\nstructure = "modular"\nmodule = "old_app.app:app"\n'
        )

        layout = read_project_layout(tmp_path)

        assert layout.app_package == "old_app"
        assert not hasattr(layout, "structure")


class TestComponentPackages:
    """Scaffold-facing canonical map helpers."""

    def test_covers_renamed_packages(self) -> None:
        packages = component_packages()
        assert "schema" in packages
        assert "schema/dataloaders" in packages
        assert "vector/collections" in packages
        assert "collections" not in packages
        assert "graphql" not in packages
