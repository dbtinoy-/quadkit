from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quadkit.cli.registry.version import (
    GitVersionSource,
    PyPackageVersionSource,
    VersionInfo,
    VersionRegistry,
    VersionSource,
    get_all_versions,
    get_version,
)


class TestVersionInfo:
    def test_creation(self) -> None:
        info = VersionInfo(name="pkg", version="1.0")
        assert info.name == "pkg"
        assert info.version == "1.0"
        assert info.installed is True


class TestVersionSource:
    def test_abc_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            VersionSource()


class TestPyPackageVersionSource:
    @patch("importlib.metadata.version", return_value="1.2.3")
    def test_get_version_found(self, mock_version: MagicMock) -> None:
        source = PyPackageVersionSource("quadkit")
        assert source.get_version() == "1.2.3"

    @patch("importlib.metadata.version", side_effect=RuntimeError)
    def test_get_version_error(self, mock_version: MagicMock) -> None:
        source = PyPackageVersionSource("nonexistent")
        assert source.get_version() is None


class TestGitVersionSource:
    @patch("quadkit.cli.registry.version.subprocess.run")
    def test_get_version_success(self, mock_run: MagicMock) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout.strip.return_value = "v1.0.0"
        mock_run.return_value = mock_result
        source = GitVersionSource()
        assert source.get_version() is not None

    @patch("quadkit.cli.registry.version.subprocess.run", side_effect=RuntimeError)
    def test_get_version_error(self, mock_run: MagicMock) -> None:
        source = GitVersionSource()
        assert source.get_version() is None


class TestVersionRegistry:
    def test_register_and_get(self) -> None:
        registry = VersionRegistry()
        source = MagicMock(spec=VersionSource)
        registry.register("test", source)
        assert registry.get("test") is source

    def test_get_nonexistent(self) -> None:
        registry = VersionRegistry()
        assert registry.get("nonexistent") is None

    def test_get_all(self) -> None:
        registry = VersionRegistry()
        source = MagicMock(spec=VersionSource)
        registry.register("a", source)
        all_sources = registry.get_all()
        assert "a" in all_sources

    def test_with_defaults_populates_all_sources(self) -> None:
        registry = VersionRegistry.with_defaults()
        assert registry.get("quadkit") is not None
        assert registry.get("python") is not None

class TestGetVersion:
    @patch("quadkit.cli.registry.version.PyPackageVersionSource.get_version", return_value="1.0")
    def test_get_version_registered(self, mock_get: MagicMock) -> None:
        registry = VersionRegistry()
        source = MagicMock()
        source.get_version.return_value = "2.0"
        registry.register("test", source)
        with patch.object(VersionRegistry, "with_defaults", return_value=registry):
            result = get_version("test")
        assert result == "2.0"

    @patch("quadkit.cli.registry.version.PyPackageVersionSource.get_version", return_value="3.0")
    def test_get_version_unregistered(self, mock_get: MagicMock) -> None:
        registry = VersionRegistry()
        with patch.object(VersionRegistry, "with_defaults", return_value=registry):
            result = get_version("unknown_pkg")
        assert result is not None


class TestGetAllVersions:
    def test_returns_dict(self) -> None:
        registry = VersionRegistry()
        source = MagicMock(spec=VersionSource)
        source.get_version.return_value = "1.0"
        registry.register("pkg", source)
        with patch.object(VersionRegistry, "with_defaults", return_value=registry):
            versions = get_all_versions()
        assert "pkg" in versions
        assert versions["pkg"] == "1.0"
