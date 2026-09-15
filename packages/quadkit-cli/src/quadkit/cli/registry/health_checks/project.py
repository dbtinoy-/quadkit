"""Project layout and dependency health checks."""

from __future__ import annotations

from pathlib import Path

from quadkit.cli.registry.health_checks.base import (
    CheckResult,
    CheckStatus,
    HealthCheck,
)


class ConfigFileCheck(HealthCheck):
    """Check if application.yaml exists and is valid."""

    def get_name(self) -> str:
        return "Configuration File"

    def get_category(self) -> str:
        return "Project"

    def check(self) -> CheckResult:
        config_path = Path("application.yaml")

        if not config_path.exists():
            return CheckResult(
                name=self.get_name(),
                status=CheckStatus.FAIL,
                message="application.yaml not found",
            )

        try:
            import yaml

            with open(config_path) as f:
                yaml.safe_load(f)
            return CheckResult(
                name=self.get_name(),
                status=CheckStatus.PASS,
                message="application.yaml found and valid",
            )
        except yaml.YAMLError as e:
            return CheckResult(
                name=self.get_name(),
                status=CheckStatus.FAIL,
                message=f"Invalid YAML: {e}",
            )
        except Exception as e:  # noqa: BLE001 — project check failures are failed results
            return CheckResult(
                name=self.get_name(),
                status=CheckStatus.FAIL,
                message=f"Error: {e}",
            )


class ProjectStructureCheck(HealthCheck):
    """Check if required project directories exist."""

    REQUIRED_PATHS = [
        ("src/", "Source directory"),
        ("pyproject.toml", "Project file"),
    ]

    def get_name(self) -> str:
        return "Project Structure"

    def get_category(self) -> str:
        return "Project"

    def check(self) -> CheckResult:
        missing = []
        found = []

        for path, desc in self.REQUIRED_PATHS:
            p = Path(path)
            if p.exists():
                found.append(desc)
            else:
                missing.append(desc)

        if not missing:
            return CheckResult(
                name=self.get_name(),
                status=CheckStatus.PASS,
                message=f"All required paths exist: {', '.join(found)}",
            )
        return CheckResult(
            name=self.get_name(),
            status=CheckStatus.WARNING,
            message=f"Missing: {', '.join(missing)}",
        )


class DependenciesCheck(HealthCheck):
    """Check if project dependencies are installed."""

    def get_name(self) -> str:
        return "Dependencies"

    def get_category(self) -> str:
        return "Project"

    def check(self) -> CheckResult:
        pyproject_path = Path("pyproject.toml")
        if not pyproject_path.exists():
            return CheckResult(
                name=self.get_name(),
                status=CheckStatus.FAIL,
                message="pyproject.toml not found",
            )

        if Path("node_modules").exists() or any(Path().glob("*.egg-info")):
            return CheckResult(
                name=self.get_name(),
                status=CheckStatus.PASS,
                message="Dependencies appear to be installed",
            )

        uv_lock = Path("uv.lock")
        if uv_lock.exists():
            return CheckResult(
                name=self.get_name(),
                status=CheckStatus.WARNING,
                message="uv.lock exists but dependencies may not be installed",
            )

        return CheckResult(
            name=self.get_name(),
            status=CheckStatus.WARNING,
            message="Run 'uv sync' to install dependencies",
        )


__all__ = ["ConfigFileCheck", "DependenciesCheck", "ProjectStructureCheck"]
