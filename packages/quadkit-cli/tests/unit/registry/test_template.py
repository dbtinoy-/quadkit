from __future__ import annotations

from pathlib import Path

import pytest

from quadkit.cli.registry.template import (
    ApiTemplate,
    ProjectBuilder,
    ProjectTemplate,
    TemplateConfig,
    TemplateRegistry,
)


class TestTemplateConfig:
    def test_defaults(self) -> None:
        cfg = TemplateConfig(name="test")
        assert cfg.name == "test"
        assert cfg.packages == []
        assert cfg.files == {}

    def test_custom(self) -> None:
        cfg = TemplateConfig(
            name="api", packages=["quadkit-web"], options={"db": "sqlite"}
        )
        assert "quadkit-web" in cfg.packages
        assert cfg.options == {"db": "sqlite"}


class TestProjectTemplate:
    def test_abc_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            ProjectTemplate()

    def test_get_dependencies_default(self):
        class TestTemplate(ProjectTemplate):
            name = "test"
            description = "test"
            packages = ["pkg1", "pkg2"]

            def get_config(self):
                return TemplateConfig(name=self.name)

        t = TestTemplate()
        deps = t.get_dependencies()
        assert "pkg1" in deps
        assert "pkg2" in deps


class TestApiTemplate:
    def test_name(self) -> None:
        assert ApiTemplate.name == "api"

    def test_packages(self) -> None:
        pkgs = ApiTemplate.packages
        assert "quadkit" in pkgs
        assert "quadkit-web" in pkgs

    def test_get_config(self) -> None:
        t = ApiTemplate()
        cfg = t.get_config()
        assert cfg.name == "api"

    def test_get_dependencies(self) -> None:
        t = ApiTemplate()
        deps = t.get_dependencies()
        assert "quadkit" in deps
        assert "quadkit-web" in deps


class TestTemplateRegistry:
    def test_register_and_get(self) -> None:
        registry = TemplateRegistry()
        registry.register(ApiTemplate)
        template = registry.get("api")
        assert template is not None
        assert template.name == "api"

    def test_get_nonexistent(self) -> None:
        registry = TemplateRegistry()
        assert registry.get("nonexistent") is None

    def test_get_all(self) -> None:
        registry = TemplateRegistry()
        registry.register(ApiTemplate)
        all_t = registry.get_all()
        assert "api" in all_t

    def test_get_choices(self) -> None:
        registry = TemplateRegistry.with_defaults()
        assert registry.get_choices() == ["api"]

    def test_with_defaults_populates_the_single_template(self) -> None:
        registry = TemplateRegistry.with_defaults()
        assert registry.get("api") is not None
        assert registry.get_choices() == ["api"]


class TestProjectBuilder:
    def test_init_with_string(self) -> None:
        builder = ProjectBuilder("api")
        assert builder.template.name == "api"

    def test_init_with_unknown_string(self) -> None:
        with pytest.raises(ValueError):
            ProjectBuilder("nonexistent")

    def test_init_with_template_obj(self) -> None:
        t = ApiTemplate()
        builder = ProjectBuilder(t)
        assert builder.template is t

    def test_create_project_dir_not_empty(self) -> None:
        builder = ProjectBuilder(ApiTemplate())

        tmp_dir = Path("/tmp/test_project_builder")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        (tmp_dir / "existing_file.txt").write_text("content")

        with pytest.raises(ValueError):
            builder.create_project("test", tmp_dir)

    def test_create_project_success(self, tmp_path: Path) -> None:
        builder = ProjectBuilder("api")

        project_dir = tmp_path / "myapp"
        builder.create_project("myapp", project_dir)

        assert (project_dir / "pyproject.toml").exists()
        assert (project_dir / "application.yaml").exists()
        assert (project_dir / ".env.example").exists()
        assert (project_dir / "src" / "myapp" / "__init__.py").exists()
        assert (project_dir / "src" / "myapp" / "app.py").exists()
