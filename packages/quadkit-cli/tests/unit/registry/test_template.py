from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from quadkit.cli.registry.template import (
    FullStackTemplate,
    GraphQLTemplate,
    MinimalTemplate,
    ProjectBuilder,
    ProjectTemplate,
    TemplateConfig,
    TemplateRegistry,
    WebAPITemplate,
    WorkerTemplate,
)


class TestTemplateConfig:
    def test_defaults(self) -> None:
        cfg = TemplateConfig(name="test")
        assert cfg.name == "test"
        assert cfg.packages == []
        assert cfg.files == {}

    def test_custom(self) -> None:
        cfg = TemplateConfig(name="api", packages=["quadkit-web"], env_vars={"DB": "sqlite"})
        assert "quadkit-web" in cfg.packages


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


class TestMinimalTemplate:
    def test_name(self) -> None:
        assert MinimalTemplate.name == "minimal"

    def test_packages(self) -> None:
        assert "quadkit" in MinimalTemplate.packages

    def test_get_config(self) -> None:
        t = MinimalTemplate()
        cfg = t.get_config()
        assert cfg.name == "minimal"
        assert "quadkit" in cfg.packages

    def test_get_dependencies(self) -> None:
        t = MinimalTemplate()
        assert "quadkit" in t.get_dependencies()


class TestWebAPITemplate:
    def test_name(self) -> None:
        assert WebAPITemplate.name == "web-api"

    def test_packages(self) -> None:
        pkgs = WebAPITemplate.packages
        assert "quadkit" in pkgs
        assert "quadkit-web" in pkgs

    def test_get_config(self) -> None:
        t = WebAPITemplate()
        cfg = t.get_config()
        assert cfg.name == "web-api"


class TestGraphQLTemplate:
    def test_name(self) -> None:
        assert GraphQLTemplate.name == "graphql"

    def test_packages(self) -> None:
        assert "quadkit-graphql" in GraphQLTemplate.packages


class TestWorkerTemplate:
    def test_name(self) -> None:
        assert WorkerTemplate.name == "worker"

    def test_packages(self) -> None:
        assert "quadkit-tasks" in WorkerTemplate.packages
        assert "quadkit-queue" in WorkerTemplate.packages


class TestFullStackTemplate:
    def test_name(self) -> None:
        assert FullStackTemplate.name == "fullstack"

    def test_packages(self) -> None:
        pkgs = FullStackTemplate.packages
        assert "quadkit-web" in pkgs
        assert "quadkit-auth" in pkgs
        assert "quadkit-admin" in pkgs


class TestTemplateRegistry:
    def test_register_and_get(self) -> None:
        registry = TemplateRegistry()
        registry.register(MinimalTemplate)
        template = registry.get("minimal")
        assert template is not None
        assert template.name == "minimal"

    def test_get_nonexistent(self) -> None:
        registry = TemplateRegistry()
        assert registry.get("nonexistent") is None

    def test_get_all(self) -> None:
        registry = TemplateRegistry()
        registry.register(MinimalTemplate)
        all_t = registry.get_all()
        assert "minimal" in all_t

    def test_get_choices(self) -> None:
        registry = TemplateRegistry.with_defaults()
        choices = registry.get_choices()
        assert "minimal" in choices
        assert "web-api" in choices

    def test_with_defaults_populates_all_templates(self) -> None:
        registry = TemplateRegistry.with_defaults()
        assert registry.get("minimal") is not None
        assert registry.get("fullstack") is not None

class TestProjectBuilder:
    def test_init_with_string(self) -> None:
        builder = ProjectBuilder("minimal")
        assert builder.template.name == "minimal"

    def test_init_with_unknown_string(self) -> None:
        with pytest.raises(ValueError):
            ProjectBuilder("nonexistent")

    def test_init_with_template_obj(self) -> None:
        t = MinimalTemplate()
        builder = ProjectBuilder(t)
        assert builder.template is t

    def test_create_project_dir_not_empty(self) -> None:
        builder = ProjectBuilder(MinimalTemplate())

        tmp_dir = Path("/tmp/test_project_builder")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        (tmp_dir / "existing_file.txt").write_text("content")

        with pytest.raises(ValueError):
            builder.create_project("test", tmp_dir)

    def test_create_project_success(self, tmp_path: Path) -> None:
        builder = ProjectBuilder("minimal")

        project_dir = tmp_path / "myapp"
        builder.create_project("myapp", project_dir)

        assert (project_dir / "pyproject.toml").exists()
        assert (project_dir / "application.yaml").exists()
        assert (project_dir / ".env.example").exists()
        assert (project_dir / "src" / "myapp" / "__init__.py").exists()
        assert (project_dir / "src" / "myapp" / "app.py").exists()
