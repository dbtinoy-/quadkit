"""Development tooling health checks."""

from __future__ import annotations

import shutil

from quadkit.cli.registry.health_checks.base import (
    CheckResult,
    CheckStatus,
    HealthCheck,
)


class PackageManagerCheck(HealthCheck):
    """Check if uv package manager is available."""

    def get_name(self) -> str:
        return "Package Manager"

    def get_category(self) -> str:
        return "Tools"

    def check(self) -> CheckResult:
        uv_path = shutil.which("uv")
        if uv_path:
            return CheckResult(
                name=self.get_name(),
                status=CheckStatus.PASS,
                message=f"uv found at {uv_path}",
            )
        return CheckResult(
            name=self.get_name(),
            status=CheckStatus.FAIL,
            message="uv not installed",
        )


class RequiredToolsCheck(HealthCheck):
    """Check if required development tools are installed."""

    TOOLS = ["pytest", "ruff", "mypy"]

    def get_name(self) -> str:
        return "Required Tools"

    def get_category(self) -> str:
        return "Tools"

    def check(self) -> CheckResult:
        missing = []
        found = []

        for tool in self.TOOLS:
            if shutil.which(tool):
                found.append(tool)
            else:
                missing.append(tool)

        if not missing:
            return CheckResult(
                name=self.get_name(),
                status=CheckStatus.PASS,
                message=f"All required tools available: {', '.join(found)}",
            )
        if found:
            return CheckResult(
                name=self.get_name(),
                status=CheckStatus.WARNING,
                message=f"Missing tools: {', '.join(missing)}",
            )
        return CheckResult(
            name=self.get_name(),
            status=CheckStatus.FAIL,
            message=f"No tools found. Required: {', '.join(self.TOOLS)}",
        )


__all__ = ["PackageManagerCheck", "RequiredToolsCheck"]
