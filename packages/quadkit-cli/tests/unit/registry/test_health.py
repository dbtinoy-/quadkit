from __future__ import annotations

from unittest.mock import MagicMock, patch

from quadkit.cli.registry.health import (
    CheckResult,
    CheckStatus,
    ConfigFileCheck,
    DependenciesCheck,
    DockerCheck,
    GitCheck,
    HealthCheckRegistry,
    PackageManagerCheck,
    ProjectStructureCheck,
    PythonVersionCheck,
    RequiredToolsCheck,
    run_health_checks,
)


class TestCheckResult:
    def test_icon_pass(self) -> None:
        r = CheckResult(name="t", status=CheckStatus.PASS)
        assert r.icon == "✓"

    def test_icon_warning(self) -> None:
        r = CheckResult(name="t", status=CheckStatus.WARNING)
        assert r.icon == "⚠"

    def test_icon_fail(self) -> None:
        r = CheckResult(name="t", status=CheckStatus.FAIL)
        assert r.icon == "✗"

    def test_icon_skip(self) -> None:
        r = CheckResult(name="t", status=CheckStatus.SKIP)
        assert r.icon == "○"

    def test_color_pass(self) -> None:
        r = CheckResult(name="t", status=CheckStatus.PASS)
        assert r.color == "success"

    def test_color_warning(self) -> None:
        r = CheckResult(name="t", status=CheckStatus.WARNING)
        assert r.color == "warning"

    def test_color_fail(self) -> None:
        r = CheckResult(name="t", status=CheckStatus.FAIL)
        assert r.color == "error"

    def test_color_skip(self) -> None:
        r = CheckResult(name="t", status=CheckStatus.SKIP)
        assert r.color == "dim"


class TestPythonVersionCheck:
    def test_pass_on_current_python(self) -> None:
        mock_vi = MagicMock()
        mock_vi.major = 3
        mock_vi.minor = 11
        mock_vi.micro = 0
        with patch(
            "quadkit.cli.registry.health_checks.python_env.sys.version_info", mock_vi
        ):
            result = PythonVersionCheck().check()
            assert result.status is CheckStatus.PASS

    def test_fail_on_old_python(self) -> None:
        mock_vi = MagicMock()
        mock_vi.major = 3
        mock_vi.minor = 9
        mock_vi.micro = 0
        with patch(
            "quadkit.cli.registry.health_checks.python_env.sys.version_info", mock_vi
        ):
            result = PythonVersionCheck().check()
            assert result.status is CheckStatus.FAIL

    def test_name(self) -> None:
        assert PythonVersionCheck().get_name() == "Python Version"

    def test_category(self) -> None:
        assert PythonVersionCheck().get_category() == "Runtime"


class TestPackageManagerCheck:
    def test_uv_found(self) -> None:
        with patch(
            "quadkit.cli.registry.health_checks.tools.shutil.which",
            return_value="/usr/bin/uv",
        ):
            result = PackageManagerCheck().check()
            assert result.status is CheckStatus.PASS
            assert "uv found" in result.message

    def test_uv_not_found(self) -> None:
        with patch(
            "quadkit.cli.registry.health_checks.tools.shutil.which",
            return_value=None,
        ):
            result = PackageManagerCheck().check()
            assert result.status is CheckStatus.FAIL
            assert "uv not installed" in result.message

    def test_name(self) -> None:
        assert PackageManagerCheck().get_name() == "Package Manager"


class TestRequiredToolsCheck:
    def test_all_tools_available(self) -> None:
        with patch(
            "quadkit.cli.registry.health_checks.tools.shutil.which",
            return_value="/usr/bin/tool",
        ):
            result = RequiredToolsCheck().check()
            assert result.status is CheckStatus.PASS

    def test_some_missing(self) -> None:
        with patch(
            "quadkit.cli.registry.health_checks.tools.shutil.which",
            side_effect=lambda x: "/bin/pytest" if x == "pytest" else None,
        ):
            result = RequiredToolsCheck().check()
            assert result.status is CheckStatus.WARNING

    def test_all_missing(self) -> None:
        with patch(
            "quadkit.cli.registry.health_checks.tools.shutil.which",
            return_value=None,
        ):
            result = RequiredToolsCheck().check()
            assert result.status is CheckStatus.FAIL


class TestConfigFileCheck:
    def test_file_not_found(self) -> None:
        with patch(
            "quadkit.cli.registry.health_checks.project.Path.exists",
            return_value=False,
        ):
            result = ConfigFileCheck().check()
            assert result.status is CheckStatus.FAIL

    def test_valid_yaml(self, tmp_path: Path) -> None:
        config = tmp_path / "application.yaml"
        config.write_text("key: value\n")
        with patch(
            "quadkit.cli.registry.health_checks.project.Path", return_value=config
        ):
            result = ConfigFileCheck().check()
            assert result.status is CheckStatus.PASS

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        config = tmp_path / "application.yaml"
        config.write_text(": invalid")
        with patch(
            "quadkit.cli.registry.health_checks.project.Path", return_value=config
        ):
            result = ConfigFileCheck().check()
            assert result.status is CheckStatus.FAIL


class TestProjectStructureCheck:
    def test_all_exist(self) -> None:
        with patch(
            "quadkit.cli.registry.health_checks.project.Path.exists",
            return_value=True,
        ):
            result = ProjectStructureCheck().check()
            assert result.status is CheckStatus.PASS

    def test_some_missing(self) -> None:
        with patch(
            "quadkit.cli.registry.health_checks.project.Path.exists",
            side_effect=[True, False],
        ):
            result = ProjectStructureCheck().check()
            assert result.status is CheckStatus.WARNING


class TestDependenciesCheck:
    def test_no_pyproject(self) -> None:
        with patch(
            "quadkit.cli.registry.health_checks.project.Path.exists",
            return_value=False,
        ):
            result = DependenciesCheck().check()
            assert result.status is CheckStatus.FAIL

    def test_node_modules_exists(self) -> None:
        with patch(
            "quadkit.cli.registry.health_checks.project.Path.exists",
            side_effect=[True, True],
        ):
            result = DependenciesCheck().check()
            assert result.status is CheckStatus.PASS

    def test_uv_lock_exists(self) -> None:
        with patch(
            "quadkit.cli.registry.health_checks.project.Path.exists",
            side_effect=[True, False, True],
        ):
            with patch(
                "quadkit.cli.registry.health_checks.project.Path.glob",
                return_value=[],
            ):
                result = DependenciesCheck().check()
                assert result.status is CheckStatus.WARNING


class TestGitCheck:
    def test_git_not_installed(self) -> None:
        with patch(
            "quadkit.cli.registry.health_checks.vcs_docker.shutil.which",
            return_value=None,
        ):
            result = GitCheck().check()
            assert result.status is CheckStatus.SKIP

    def test_git_repo(self) -> None:
        with patch(
            "quadkit.cli.registry.health_checks.vcs_docker.shutil.which",
            return_value="/usr/bin/git",
        ):
            with patch(
                "quadkit.cli.registry.health_checks.vcs_docker.Path.exists",
                return_value=True,
            ):
                with patch(
                    "quadkit.cli.registry.health_checks.vcs_docker.subprocess.run"
                ) as mock_run:
                    mock_run.return_value.returncode = 0
                    result = GitCheck().check()
                    assert result.status is CheckStatus.PASS

    def test_no_git_dir(self) -> None:
        with patch(
            "quadkit.cli.registry.health_checks.vcs_docker.shutil.which",
            return_value="/usr/bin/git",
        ):
            with patch(
                "quadkit.cli.registry.health_checks.vcs_docker.Path.exists",
                return_value=False,
            ):
                result = GitCheck().check()
                assert result.status is CheckStatus.WARNING


class TestDockerCheck:
    def test_docker_not_installed(self) -> None:
        with patch(
            "quadkit.cli.registry.health_checks.vcs_docker.shutil.which",
            return_value=None,
        ):
            result = DockerCheck().check()
            assert result.status is CheckStatus.SKIP

    def test_docker_available(self) -> None:
        with patch(
            "quadkit.cli.registry.health_checks.vcs_docker.shutil.which",
            return_value="/usr/bin/docker",
        ):
            with patch(
                "quadkit.cli.registry.health_checks.vcs_docker.subprocess.run"
            ) as mock_run:
                mock_run.return_value.returncode = 0
                result = DockerCheck().check()
                assert result.status is CheckStatus.PASS

    def test_docker_not_running(self) -> None:
        with patch(
            "quadkit.cli.registry.health_checks.vcs_docker.shutil.which",
            return_value="/usr/bin/docker",
        ):
            with patch(
                "quadkit.cli.registry.health_checks.vcs_docker.subprocess.run"
            ) as mock_run:
                mock_run.return_value.returncode = 1
                result = DockerCheck().check()
                assert result.status is CheckStatus.WARNING


class TestHealthCheckRegistry:
    def test_with_defaults_populates_all_checks(self) -> None:
        registry = HealthCheckRegistry.with_defaults()
        checks = registry.get_all_checks()
        assert len(checks) >= 11

    def test_get_checks_by_category(self) -> None:
        registry = HealthCheckRegistry.with_defaults()
        by_cat = registry.get_checks_by_category()
        assert "Runtime" in by_cat
        assert "Tools" in by_cat
        assert "Project" in by_cat

    def test_empty_registry_by_default(self) -> None:
        registry = HealthCheckRegistry()
        assert registry.get_all_checks() == []

class TestRunHealthChecks:
    def test_returns_dict(self) -> None:
        HealthCheckRegistry._checks = [PythonVersionCheck]
        results = run_health_checks()
        assert isinstance(results, dict)
