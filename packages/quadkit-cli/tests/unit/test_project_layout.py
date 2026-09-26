"""Tests for the one project layout: rendered trees and generator paths.

There is no project structure to choose. A scaffolded project is flat --
feature components under ``src/<app>/``, cross-cutting ones under
``src/<app>/shared/`` -- and grows bounded contexts in place. What used to
be three trees is one tree plus a per-node question: is this node in a
module?
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from quadkit.cli.commands.new import app as new_app
from quadkit.cli.scaffold import render_project, template_names

_TEMPLATES = tuple(
    name for name in ("api", "web-api", "full") if name in template_names()
)


@pytest.fixture
def runner() -> CliRunner:
    """CLI test runner."""
    return CliRunner()


class TestScaffoldedTree:
    """The rendered tree matches the canonical map."""

    def test_feature_components_sit_under_the_app_package(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        result = runner.invoke(
            new_app,
            [
                "project",
                "my-app",
                "--template",
                "web-api",
                "--directory",
                str(temp_dir),
            ],
        )

        assert result.exit_code == 0, result.output
        project = temp_dir / "my-app"
        assert (project / "src/my_app/app.py").exists()
        assert (project / "src/my_app/controllers/api.py").exists()
        # Nothing at the src root but the package itself.
        assert not (project / "src/controllers").exists()
        assert not (project / "src/app").exists()

    def test_cross_cutting_components_sit_under_shared(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        result = runner.invoke(
            new_app,
            [
                "project",
                "my-app",
                "--template",
                "web-api",
                "--directory",
                str(temp_dir),
            ],
        )

        assert result.exit_code == 0, result.output
        project = temp_dir / "my-app"
        assert (project / "src/my_app/shared/errors/__init__.py").exists()
        assert (project / "src/my_app/shared/schema/__init__.py").exists()
        assert (project / "src/my_app/shared/vector/collections/__init__.py").exists()
        assert (project / "src/my_app/infrastructure/__init__.py").exists()
        # `shared/` means cross-cutting and nothing else: a module-local
        # component has no business there even before any module exists.
        assert not (project / "src/my_app/shared/controllers").exists()
        assert not (project / "src/graphql").exists()
        assert not (project / "src/collections").exists()

    def test_a_fresh_project_declares_only_its_package(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        """``[tool.quadkit]`` names the ASGI target and nothing else.

        A `structure` key would be a second source of truth about a tree
        that is no longer variable, so there is not one to write or read.
        """
        result = runner.invoke(
            new_app,
            ["project", "my-app", "--directory", str(temp_dir)],
        )

        assert result.exit_code == 0, result.output
        pyproject = (temp_dir / "my-app" / "pyproject.toml").read_text()
        assert 'module = "my_app.app:app"' in pyproject
        assert "structure" not in pyproject

    def test_a_fresh_project_has_no_modules(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        """Modules are something the user creates, not something they inherit."""
        result = runner.invoke(
            new_app,
            [
                "project",
                "my-app",
                "--template",
                "web-api",
                "--directory",
                str(temp_dir),
            ],
        )

        assert result.exit_code == 0, result.output
        registry = (
            temp_dir / "my-app" / "src/my_app/modules/__init__.py"
        ).read_text()
        assert "MODULES" in registry
        assert not list(
            (temp_dir / "my-app" / "src/my_app/modules").glob("*/__init__.py")
        )

    @pytest.mark.parametrize("template", _TEMPLATES)
    def test_scaffolded_projects_pass_ruff(
        self, runner: CliRunner, temp_dir: Path, template: str
    ) -> None:
        """Every template is lint-clean."""
        result = runner.invoke(
            new_app,
            [
                "project",
                f"proj-{template}",
                "--template",
                template,
                "--directory",
                str(temp_dir),
            ],
        )
        assert result.exit_code == 0, result.output

        project_dir = temp_dir / f"proj-{template}"
        py_files = list(project_dir.rglob("*.py"))
        assert py_files, "No Python files generated"
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "--select",
                "E,F,I",
                "--",
                *[str(f) for f in py_files],
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, (
            f"ruff failed for {template}:\n{proc.stdout}\n{proc.stderr}"
        )


@pytest.fixture
def project(temp_dir: Path) -> Path:
    """A rendered web-api project."""
    render_project("web-api", "my-platform", Path(temp_dir) / "my-platform")
    return Path(temp_dir) / "my-platform"


class TestNewModuleCommand:
    """quadkit new module creates and registers a bounded context."""

    def test_creates_boundary_files(self, runner: CliRunner, project: Path) -> None:
        result = runner.invoke(
            new_app, ["module", "auth", "--directory", str(project)]
        )

        assert result.exit_code == 0, result.output
        module_dir = project / "src/my_platform/modules/auth"
        for name in ("__init__.py", "protocols.py", "provider.py", "services.py"):
            assert (module_dir / name).exists(), name
        init = (module_dir / "__init__.py").read_text()
        assert "class AuthModule(Module):" in init
        assert "@module()" in init

    def test_registers_module_in_registry(
        self, runner: CliRunner, project: Path
    ) -> None:
        runner.invoke(new_app, ["module", "auth", "--directory", str(project)])

        registry = (project / "src/my_platform/modules/__init__.py").read_text()
        assert "from my_platform.modules.auth import AuthModule" in registry
        assert "    AuthModule," in registry

    def test_refuses_existing_module(
        self, runner: CliRunner, project: Path
    ) -> None:
        first = runner.invoke(
            new_app, ["module", "billing", "--directory", str(project)]
        )
        assert first.exit_code == 0, first.output

        second = runner.invoke(
            new_app, ["module", "billing", "--directory", str(project)]
        )

        assert second.exit_code == 1
        assert "already exists" in second.output

    def test_registry_imports_and_boots_modules_package(
        self, runner: CliRunner, project: Path
    ) -> None:
        """The module registry imports cleanly against real quadkit APIs."""
        created = runner.invoke(
            new_app, ["module", "auth", "--directory", str(project)]
        )
        assert created.exit_code == 0, created.output

        original = os.getcwd()
        os.chdir(project)
        try:
            sys.path.insert(0, str(project / "src"))
            modules = importlib.import_module("my_platform.modules")
            assert [m.__name__ for m in modules.MODULES] == ["AuthModule"]
            auth = importlib.import_module("my_platform.modules.auth")
            assert hasattr(auth, "AuthModule")
        finally:
            sys.path.remove(str(project / "src"))
            os.chdir(original)


class TestGenModuleOption:
    """``quadkit gen --module`` decides where a component lands."""

    def test_module_local_component_without_a_module(
        self,
        runner: CliRunner,
        project: Path,
        cli_app_with_web_generators,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The default: at the app root, generated rather than refused.

        Every node starts unscoped, so refusing this is refusing the first
        thing a new project does.
        """
        monkeypatch.chdir(project)

        result = runner.invoke(
            cli_app_with_web_generators, ["gen", "controller", "users"]
        )

        assert result.exit_code == 0, result.output
        assert (
            project / "src/my_platform/controllers/users_controller.py"
        ).exists()

    def test_module_local_component_with_a_module(
        self,
        runner: CliRunner,
        project: Path,
        cli_app_with_web_generators,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(project)
        runner.invoke(new_app, ["module", "auth", "--directory", str(project)])

        result = runner.invoke(
            cli_app_with_web_generators,
            ["gen", "controller", "users", "--module", "auth"],
        )

        assert result.exit_code == 0, result.output
        assert (
            project / "src/my_platform/modules/auth/controllers/users_controller.py"
        ).exists()
        assert not (
            project / "src/my_platform/controllers/users_controller.py"
        ).exists()

    def test_cross_cutting_component_ignores_the_module(
        self,
        runner: CliRunner,
        project: Path,
        cli_app_with_core_generators,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(project)

        result = runner.invoke(
            cli_app_with_core_generators,
            ["gen", "provider", "billing", "--module", "auth"],
        )

        assert result.exit_code == 0, result.output
        assert (
            project / "src/my_platform/shared/di/billing_provider.py"
        ).exists()
