"""Tests for `quadkit gen provider` command."""

from __future__ import annotations

import ast
import os
from pathlib import Path

from typer.testing import CliRunner

from quadkit.cli.assembly.assembler import _detect_src_dir


class TestGenProvider:
    def setup_method(self) -> None:
        self.runner = CliRunner()

    def test_gen_provider_creates_file(
        self, temp_project, cli_app_with_core_generators
    ) -> None:
        result = self.runner.invoke(
            cli_app_with_core_generators,
            [
                "gen",
                "provider",
                "MyAwesome",
            ],
        )
        assert result.exit_code == 0
        created = temp_project / "src/test_project/shared/providers/my_awesome_provider.py"
        # The console hard-wraps a long path mid-word, so compare with all
        # whitespace removed rather than on where rich broke the line.
        assert "".join(f"Created: {created}".split()) in "".join(
            result.output.split()
        )
        assert created.exists()

    def test_gen_provider_content(
        self, temp_project, cli_app_with_core_generators
    ) -> None:
        result = self.runner.invoke(
            cli_app_with_core_generators,
            [
                "gen",
                "provider",
                "MyAwesome",
            ],
        )
        assert result.exit_code == 0
        content = (temp_project / "src/test_project/shared/providers/my_awesome_provider.py").read_text()
        assert "class MyAwesomeProvider(Provider):" in content

    def test_gen_provider_is_valid_python(
        self,
        temp_project,
        tmp_path: Path,
        cli_app_with_core_generators,
    ) -> None:
        """Generated provider must parse without SyntaxError."""
        result = self.runner.invoke(
            cli_app_with_core_generators,
            ["gen", "provider", "billing", "--output-dir", str(tmp_path)],
        )
        assert result.exit_code == 0
        provider_file = tmp_path / "billing_provider.py"
        assert provider_file.exists()
        ast.parse(provider_file.read_text())

    def test_gen_provider_correct_imports(
        self,
        temp_project,
        tmp_path: Path,
        cli_app_with_core_generators,
    ) -> None:
        """Generated provider must use correct quadkit.di import path."""
        self.runner.invoke(
            cli_app_with_core_generators,
            ["gen", "provider", "billing", "--output-dir", str(tmp_path)],
        )
        content = (tmp_path / "billing_provider.py").read_text()
        assert "from quadkit.di import" in content
        assert "Provider" in content

    def test_gen_provider_pascal_case_class(
        self,
        temp_project,
        tmp_path: Path,
        cli_app_with_core_generators,
    ) -> None:
        """Provider name is converted to PascalCase for the class name."""
        self.runner.invoke(
            cli_app_with_core_generators,
            ["gen", "provider", "my_billing", "--output-dir", str(tmp_path)],
        )
        content = (tmp_path / "my_billing_provider.py").read_text()
        assert "class MyBillingProvider(Provider):" in content


class TestDetectSrcDir:
    """Test _detect_src_dir auto-detection logic."""

    def test_returns_default_when_no_src(self, tmp_path: Path) -> None:
        original = Path.cwd()
        os.chdir(tmp_path)
        try:
            assert _detect_src_dir("src") == "src"
        finally:
            os.chdir(original)

    def test_detects_single_package_in_src(self, tmp_path: Path) -> None:
        src = tmp_path / "src" / "my_app"
        src.mkdir(parents=True)
        (src / "__init__.py").touch()
        original = Path.cwd()
        os.chdir(tmp_path)
        try:
            result = _detect_src_dir("src")
            assert result == "src/my_app"
        finally:
            os.chdir(original)

    def test_returns_default_when_multiple_packages(self, tmp_path: Path) -> None:
        for pkg in ("pkg_a", "pkg_b"):
            p = tmp_path / "src" / pkg
            p.mkdir(parents=True)
            (p / "__init__.py").touch()
        original = Path.cwd()
        os.chdir(tmp_path)
        try:
            assert _detect_src_dir("src") == "src"
        finally:
            os.chdir(original)
