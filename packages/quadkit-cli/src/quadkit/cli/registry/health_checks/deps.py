"""Installed-distribution health checks."""

from __future__ import annotations

from importlib.metadata import distributions

from quadkit.cli.registry.health_checks.base import (
    CheckResult,
    CheckStatus,
    HealthCheck,
)


class InstalledQuadkitPackagesCheck(HealthCheck):
    """Report all installed quadkit-* packages and their versions."""

    def get_name(self) -> str:
        """Return the display name of this check."""
        return "Installed Packages"

    def get_category(self) -> str:
        """Return the grouping category for this check."""
        return "Framework"

    def check(self) -> CheckResult:
        """Scan the active environment for installed quadkit-* distributions."""
        pkgs: dict[str, str] = {}
        for dist in distributions():
            name: str = dist.metadata["Name"] if dist.metadata.get("Name") else ""  # type: ignore[attr-defined]
            if name.startswith("quadkit"):
                version: str = (
                    dist.metadata["Version"] if "Version" in dist.metadata else "?"  # noqa: SIM401
                )
                pkgs[name] = version

        if pkgs:
            pkg_list = ", ".join(f"{n}=={v}" for n, v in sorted(pkgs.items()))
            return CheckResult(
                name=self.get_name(),
                status=CheckStatus.PASS,
                message=f"{len(pkgs)} package(s): {pkg_list}",
                details={"packages": pkgs},
            )
        return CheckResult(
            name=self.get_name(),
            status=CheckStatus.WARNING,
            message="No quadkit-* packages found in active environment",
        )


__all__ = ["InstalledQuadkitPackagesCheck"]
