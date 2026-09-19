"""Tests for GeneratorBase output-dir resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from quadkit.codegen.base import GeneratorBase


class _StubGenerator(GeneratorBase):
    def generate(self, name: str, **options: object) -> object:
        return None


class TestRelativeOutputDirResolution:
    def test_relative_path_anchors_to_nearest_project(self, tmp_path: Path) -> None:
        project = tmp_path / "my-app"
        (project / "src").mkdir(parents=True)
        (project / "pyproject.toml").write_text(
            "[project]\nname = 'my-app'\nversion = '0.1.0'\n", encoding="utf-8"
        )
        gen = _StubGenerator(output_dir=project / "src" / "consumers")
        assert isinstance(gen.output_dir, Path)

    def test_absolute_output_dir_untouched(self, tmp_path: Path) -> None:
        gen = _StubGenerator(output_dir=tmp_path / "out")
        assert gen.output_dir == tmp_path / "out"

    def test_raw_output_dir_preserved_for_naming(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = tmp_path / "my-app"
        project.mkdir()
        (project / "pyproject.toml").write_text(
            "[project]\nname = 'my-app'\nversion = '0.1.0'\n", encoding="utf-8"
        )
        monkeypatch.chdir(project)

        gen = _StubGenerator(output_dir="src/consumers")
        assert gen.raw_output_dir == Path("src/consumers")
        assert gen.output_dir == project / "src" / "consumers"


class TestVirtualRootRefusal:
    def test_relative_path_at_virtual_root_raises_before_any_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        virtual_root = tmp_path / "workspace"
        virtual_root.mkdir()
        (virtual_root / "pyproject.toml").write_text(
            "[tool.uv.workspace]\nmembers = ['pkgs/*']\n", encoding="utf-8"
        )
        monkeypatch.chdir(virtual_root)
        target = virtual_root / "src" / "consumers"

        with pytest.raises(ValueError, match="absolute --output-dir"):
            _StubGenerator(output_dir="src/consumers")

        assert not target.exists(), "must not touch filesystem on refusal"

    def test_relative_path_without_any_project_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bare = tmp_path / "random-dir"
        bare.mkdir()
        monkeypatch.chdir(bare)

        with pytest.raises(ValueError, match="inside the package"):
            _StubGenerator(output_dir="src/gen")

    def test_relative_path_inside_member_anchors_to_member(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace = tmp_path / "ws"
        member = workspace / "pkgs" / "quadkit-demo"
        member.mkdir(parents=True)
        (member / "sub" / "dir").mkdir(parents=True)
        (workspace / "pyproject.toml").write_text(
            "[tool.uv.workspace]\nmembers = ['pkgs/*']\n", encoding="utf-8"
        )
        (member / "pyproject.toml").write_text(
            "[project]\nname = 'quadkit-demo'\nversion = '0.1.0'\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(member / "sub" / "dir")

        gen = _StubGenerator(output_dir="src/consumers")
        assert gen.output_dir == member / "src" / "consumers"


class TestNameContainment:
    """Path-traversal and content-injection guards (spec finding 15)."""

    def test_snake_case_rejects_path_separators(self) -> None:
        gen = _StubGenerator(output_dir=Path.cwd() / "out")
        with pytest.raises(ValueError, match="Invalid generator name"):
            gen._validate_component_name("../../evil")

    def test_snake_case_rejects_absolute(self) -> None:
        gen = _StubGenerator(output_dir=Path.cwd() / "out")
        with pytest.raises(ValueError, match="Invalid generator name"):
            gen._validate_component_name("/etc/passwd")

    def test_valid_names_pass(self) -> None:
        gen = _StubGenerator(output_dir=Path.cwd() / "out")
        assert gen._validate_component_name("PetController") == "PetController"
        assert gen._validate_component_name("my-widget") == "my-widget"

    def test_write_file_rejects_escape(self, tmp_path: Path) -> None:
        out = tmp_path / "out"
        gen = _StubGenerator(output_dir=str(out))
        escape = out / ".." / "evil.py"
        with pytest.raises(ValueError, match="escapes output directory"):
            gen.write_file(escape, "x = 1\n")

    def test_write_file_allows_inside(self, tmp_path: Path) -> None:
        out = tmp_path / "out"
        gen = _StubGenerator(output_dir=str(out))
        result = gen.write_file(out / "ok.py", "x = 1\n")
        assert result.files_created == [out / "ok.py"]


class TestPackageNameResolution:
    """Generated cross-package imports must follow the project layout."""

    @staticmethod
    def _anchored(tmp_path: Path, *parts: str) -> Path:
        """Create an anchored project and return one of its directories."""
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname = 'my-app'\nversion = '0.1.0'\n", encoding="utf-8"
        )
        target = tmp_path.joinpath(*parts)
        target.mkdir(parents=True, exist_ok=True)
        return target

    def test_structured_layout_has_no_prefix(self, tmp_path: Path) -> None:
        """Component packages sit directly under ``src`` in structured layouts."""
        out = self._anchored(tmp_path, "src", "controllers")
        assert GeneratorBase._get_package_name(out) == "controllers"
        assert GeneratorBase._sibling_package(out, "repositories") == "repositories"

    def test_minimal_layout_is_prefixed_with_the_app_package(
        self, tmp_path: Path
    ) -> None:
        """Minimal layouts nest component packages under the app package."""
        out = self._anchored(tmp_path, "src", "app", "controllers")
        assert GeneratorBase._get_package_name(out) == "app.controllers"
        assert GeneratorBase._sibling_package(out, "repositories") == "app.repositories"

    def test_modular_layout_includes_the_feature_module(self, tmp_path: Path) -> None:
        """Modular layouts nest component packages under the feature module."""
        out = self._anchored(tmp_path, "src", "app", "modules", "billing", "controllers")
        assert GeneratorBase._get_package_name(out) == "app.modules.billing.controllers"
        assert (
            GeneratorBase._sibling_package(out, "repositories")
            == "app.modules.billing.repositories"
        )

    def test_unanchored_directory_falls_back_to_the_bare_name(
        self, tmp_path: Path
    ) -> None:
        """Outside a project the sibling package name is used as-is."""
        out = tmp_path / "controllers"
        out.mkdir()
        assert GeneratorBase._import_parts(out) is None
        assert GeneratorBase._sibling_package(out, "repositories") == "repositories"

    def test_directory_outside_the_anchor_falls_back(self, tmp_path: Path) -> None:
        """A directory that is not inside the anchor cannot be named."""
        project = tmp_path / "my-app"
        project.mkdir()
        (project / "pyproject.toml").write_text(
            "[project]\nname = 'my-app'\nversion = '0.1.0'\n", encoding="utf-8"
        )
        elsewhere = tmp_path / "elsewhere" / "controllers"
        elsewhere.mkdir(parents=True)
        assert GeneratorBase._import_parts(elsewhere) is None

    def test_root_directory_is_not_a_package(self, tmp_path: Path) -> None:
        """The anchor itself contributes no package parts."""
        self._anchored(tmp_path)
        assert GeneratorBase._import_parts(tmp_path) == ()
