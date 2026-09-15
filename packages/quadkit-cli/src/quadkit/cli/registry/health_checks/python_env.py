"""Runtime environment health checks."""

from __future__ import annotations

import sys

from quadkit.cli.registry.health_checks.base import (
    CheckResult,
    CheckStatus,
    HealthCheck,
)


class PythonVersionCheck(HealthCheck):
    """Check if Python version meets minimum requirements."""

    MIN_VERSION = (3, 11)

    def get_name(self) -> str:
        return "Python Version"

    def get_category(self) -> str:
        return "Runtime"

    def check(self) -> CheckResult:
        version = sys.version_info
        meets_min = (
            version.major >= self.MIN_VERSION[0]
            and version.minor >= self.MIN_VERSION[1]
        )

        if meets_min:
            return CheckResult(
                name=self.get_name(),
                status=CheckStatus.PASS,
                message=f"Python {version.major}.{version.minor}.{version.micro}",
            )
        return CheckResult(
            name=self.get_name(),
            status=CheckStatus.FAIL,
            message=f"Python {version.major}.{version.minor} (minimum {self.MIN_VERSION[0]}.{self.MIN_VERSION[1]} required)",
        )


__all__ = ["PythonVersionCheck"]
