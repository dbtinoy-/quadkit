"""Framework provider and architecture health checks."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, distribution, entry_points
from pathlib import Path
from typing import Any

from quadkit.cli.package_names import module_for

from quadkit.cli.registry.health_checks.base import (
    CheckResult,
    CheckStatus,
    HealthCheck,
)

def _provider_packages() -> dict[str, str]:
    """Discover provider distributions from the installed provider plugins."""

    return {
        point.name: point.dist.name
        for point in entry_points(group="quadkit.providers")
        if point.dist is not None
    }



class ProviderPackagesCheck(HealthCheck):
    """Verify that each provider declared in application.yaml has its package installed."""

    def get_name(self) -> str:
        """Return the display name of this check."""
        return "Provider Packages"

    def get_category(self) -> str:
        """Return the grouping category for this check."""
        return "Framework"

    def check(self) -> CheckResult:
        """Cross-reference application.yaml providers with installed distributions."""
        config_path = Path("application.yaml")
        if not config_path.exists():
            return CheckResult(
                name=self.get_name(),
                status=CheckStatus.SKIP,
                message="application.yaml not found — no providers to check",
            )

        try:
            import yaml

            with open(config_path) as f:
                config: dict[str, Any] = yaml.safe_load(f) or {}
        except Exception as exc:  # noqa: BLE001 — provider check failures are failed results
            return CheckResult(
                name=self.get_name(),
                status=CheckStatus.FAIL,
                message=f"Failed to read application.yaml: {exc}",
            )

        missing: list[str] = []
        present: list[str] = []

        for provider_key, pkg_name in _provider_packages().items():
            if provider_key not in config:
                continue
            try:
                distribution(pkg_name)
                present.append(provider_key)
            except PackageNotFoundError:
                missing.append(f"{provider_key} (needs {pkg_name})")

        if not (missing or present):
            return CheckResult(
                name=self.get_name(),
                status=CheckStatus.SKIP,
                message="No known provider sections in application.yaml",
            )
        if missing:
            return CheckResult(
                name=self.get_name(),
                status=CheckStatus.FAIL,
                message=f"Missing packages for: {', '.join(missing)}",
                details={"missing": missing, "present": present},
            )
        return CheckResult(
            name=self.get_name(),
            status=CheckStatus.PASS,
            message=f"All {len(present)} configured provider package(s) installed",
        )


class CrossExtensionImportCheck(HealthCheck):
    """Detect direct cross-extension imports that violate the dependency graph.

    Scans every ``*.py`` file under ``src/`` using Python's ``ast`` module
    and flags any ``import`` or ``from … import`` that crosses the boundary
    between two optional extension namespaces instead of going through
    contracts.
    """

    #: (source prefix, forbidden_import_prefix) pairs.
    _FORBIDDEN_PAIRS: list[tuple[str, str]] = [
        (module_for("web"), module_for("sql")),
        (module_for("web"), module_for("cache")),
        (module_for("web"), module_for("tasks")),
        (module_for("auth"), module_for("sql")),
        (module_for("auth"), module_for("cache")),
        (module_for("cache"), module_for("sql")),
        (module_for("tasks"), module_for("sql")),
        (module_for("tasks"), module_for("web")),
        (module_for("search"), module_for("sql")),
        (module_for("search"), module_for("cache")),
    ]

    def get_name(self) -> str:
        """Return the display name of this check."""
        return "Architecture Violations"

    def get_category(self) -> str:
        """Return the grouping category for this check."""
        return "Architecture"

    def check(self) -> CheckResult:
        """Walk src/ with ast to find forbidden cross-extension import statements."""
        import ast

        src_path = Path("src")
        if not src_path.exists():
            return CheckResult(
                name=self.get_name(),
                status=CheckStatus.SKIP,
                message="No src/ directory found — skipping architecture check",
            )

        violations: list[str] = []

        for py_file in sorted(src_path.rglob("*.py")):
            # Determine which namespace this file belongs to
            module_path = str(py_file).replace("/", ".")
            owning_prefix: str | None = None
            for src_prefix, _ in self._FORBIDDEN_PAIRS:
                if src_prefix in module_path:
                    owning_prefix = src_prefix
                    break
            if owning_prefix is None:
                continue

            try:
                tree = ast.parse(py_file.read_text(), filename=str(py_file))
            except SyntaxError:
                continue

            # Collect all imported module names in this file
            imported_modules: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_modules.append(alias.name)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_modules.append(node.module)

            # Detect forbidden pairs
            for _, forbidden_prefix in [
                pair for pair in self._FORBIDDEN_PAIRS if pair[0] == owning_prefix
            ]:
                if any(
                    m == forbidden_prefix or m.startswith(forbidden_prefix + ".")
                    for m in imported_modules
                ):
                    violations.append(
                        f"{py_file}: {owning_prefix} imports from {forbidden_prefix}"
                    )

        if violations:
            return CheckResult(
                name=self.get_name(),
                status=CheckStatus.FAIL,
                message=f"{len(violations)} cross-extension violation(s) found",
                details={"violations": violations},
            )
        return CheckResult(
            name=self.get_name(),
            status=CheckStatus.PASS,
            message="No cross-extension import violations detected",
        )


__all__ = ["CrossExtensionImportCheck", "ProviderPackagesCheck"]
