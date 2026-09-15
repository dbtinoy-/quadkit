"""Version registry for version management.

This module provides a registry pattern for version information.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
import subprocess

from quadkit.logging import get_logger

logger = get_logger(__name__)


@dataclass
class VersionInfo:
    """Information about a package version."""

    name: str
    version: str
    installed: bool = True


class VersionSource(abc.ABC):
    """Abstract base class for version sources."""

    name: str

    @abc.abstractmethod
    def get_version(self) -> str | None:
        """Get the version of a package."""


class PyPackageVersionSource(VersionSource):
    """Get version from installed Python package."""

    def __init__(self, package_name: str):
        self.package_name = package_name

    def get_version(self) -> str | None:
        try:
            import importlib.metadata

            return importlib.metadata.version(self.package_name)
        except (
            ModuleNotFoundError,
            RuntimeError,
            OSError,
            AttributeError,
            LookupError,
        ):
            # importlib.metadata.PackageNotFoundError subclasses ModuleNotFoundError,
            # so a missing distribution is treated as "no version available".
            return None


class GitVersionSource(VersionSource):
    """Get version from git tags."""

    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path

    def get_version(self) -> str | None:
        try:
            result = subprocess.run(
                ["git", "describe", "--tags", "--always"],  # noqa: S607 — static CLI tool on PATH (operator-invoked)
                check=False,
                capture_output=True,
                text=True,
                cwd=self.repo_path,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as exc:  # noqa: BLE001 — version check failures are logged, never raised
            logger.debug("version_check_failed", error=str(exc))
        return None


class VersionRegistry:
    """Registry for version information.

    Instances are always empty — use :meth:`with_defaults` for the
    in-package built-ins or :meth:`register` for plugin sources.
    """

    def __init__(self) -> None:
        self._sources: dict[str, VersionSource] = {}

    def register(self, name: str, source: VersionSource) -> None:
        """Register a version source."""
        self._sources[name] = source

    def get(self, name: str) -> VersionSource | None:
        """Get a version source by name."""
        return self._sources.get(name)

    def get_all(self) -> dict[str, VersionSource]:
        """Get all registered sources."""
        return self._sources.copy()

    @classmethod
    def _default_entries(cls) -> tuple[tuple[str, VersionSource], ...]:
        """The complete in-package built-in set, declared exactly once."""
        return (
            ("quadkit", PyPackageVersionSource("quadkit")),
            ("python", PyPackageVersionSource("python")),
            ("uv", PyPackageVersionSource("uv")),
            ("pytest", PyPackageVersionSource("pytest")),
            ("ruff", PyPackageVersionSource("ruff")),
            ("mypy", PyPackageVersionSource("mypy")),
        )

    @classmethod
    def with_defaults(cls) -> VersionRegistry:
        """Return an instance populated with the built-in sources."""
        registry = cls()
        for name, source in cls._default_entries():
            registry.register(name, source)
        return registry


def get_version(package: str) -> str | None:
    """Get version of a package."""
    registry = VersionRegistry.with_defaults()
    source = registry.get(package.lower())
    if source:
        return source.get_version()
    return PyPackageVersionSource(package).get_version()


def get_all_versions() -> dict[str, str]:
    """Get versions of all registered packages."""
    registry = VersionRegistry.with_defaults()
    versions = {}
    for name, source in registry.get_all().items():
        version = source.get_version()
        if version:
            versions[name] = version
    return versions


__all__ = [
    "GitVersionSource",
    "PyPackageVersionSource",
    "VersionInfo",
    "VersionRegistry",
    "VersionSource",
    "get_all_versions",
    "get_version",
]
