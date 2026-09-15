"""Version-control and container health checks."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from quadkit.cli.registry.health_checks.base import (
    CheckResult,
    CheckStatus,
    HealthCheck,
)
from quadkit.logging import get_logger

logger = get_logger(__name__)


class GitCheck(HealthCheck):
    """Check if git is initialized."""

    def get_name(self) -> str:
        return "Git"

    def get_category(self) -> str:
        return "Version Control"

    def check(self) -> CheckResult:
        git_path = shutil.which("git")
        if not git_path:
            return CheckResult(
                name=self.get_name(),
                status=CheckStatus.SKIP,
                message="git not installed",
            )

        git_dir = Path(".git")
        if git_dir.exists():
            try:
                result = subprocess.run(
                    ["git", "status"],  # noqa: S607 — static CLI tool on PATH (operator-invoked)
                    capture_output=True,
                    check=False,
                )
                if result.returncode == 0:
                    return CheckResult(
                        name=self.get_name(),
                        status=CheckStatus.PASS,
                        message="Git repository initialized",
                    )
            except Exception as exc:  # noqa: BLE001 — git check failures are logged, never raised
                logger.debug("git_check_failed", error=str(exc))

        return CheckResult(
            name=self.get_name(),
            status=CheckStatus.WARNING,
            message="Not a git repository",
        )


class DockerCheck(HealthCheck):
    """Check if Docker is available."""

    def get_name(self) -> str:
        return "Docker"

    def get_category(self) -> str:
        return "Container"

    def check(self) -> CheckResult:
        docker_path = shutil.which("docker")
        if not docker_path:
            return CheckResult(
                name=self.get_name(),
                status=CheckStatus.SKIP,
                message="Docker not installed (optional)",
            )

        try:
            result = subprocess.run(
                ["docker", "version"],  # noqa: S607 — static CLI tool on PATH (operator-invoked)
                capture_output=True,
                check=False,
            )
            if result.returncode == 0:
                return CheckResult(
                    name=self.get_name(),
                    status=CheckStatus.PASS,
                    message="Docker available",
                )
        except Exception as exc:  # noqa: BLE001 — docker check failures are logged, never raised
            logger.debug("docker_check_failed", error=str(exc))

        return CheckResult(
            name=self.get_name(),
            status=CheckStatus.WARNING,
            message="Docker installed but not running",
        )


__all__ = ["DockerCheck", "GitCheck"]
