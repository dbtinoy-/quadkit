"""Tests for app discovery utilities (providers, injectables, modules)."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock

from quadkit.app import discovery
from quadkit.contracts.core.scopes import ServiceScope

# ── discover_providers ────────────────────────────────────────────────────


class TestDiscoverProviders:
    def test_finds_and_instantiates_providers(self, tmp_path: Path, monkeypatch) -> None:
        pkg_dir = tmp_path / "prov_pkg"
        (pkg_dir / "sub").mkdir(parents=True)
        (pkg_dir / "__init__.py").write_text("")
        (pkg_dir / "sub" / "__init__.py").write_text("")
        (pkg_dir / "sub" / "mods.py").write_text(
            dedent(
                """
                from quadkit.di.provider import Provider

                class AlphaProvider(Provider):
                    def __init__(self) -> None:
                        super().__init__()
                """
            )
        )
        self._install(tmp_path, "prov_pkg", monkeypatch)

        found = discovery.discover_providers(("prov_pkg",))
        names = [type(p).__name__ for p in found]
        assert names == ["AlphaProvider"]

    def test_skips_providers_requiring_args(self, tmp_path: Path, monkeypatch) -> None:
        pkg_dir = tmp_path / "arg_pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            dedent(
                """
                from quadkit.di.provider import Provider

                class NeedsArgs(Provider):
                    def __init__(self, url: str) -> None:
                        super().__init__()

                class NoArgs(Provider):
                    pass
                """
            )
        )
        self._install(tmp_path, "arg_pkg", monkeypatch)

        found = discovery.discover_providers(("arg_pkg",))
        assert [type(p).__name__ for p in found] == ["NoArgs"]

    def test_dedupes_across_packages(self, tmp_path: Path, monkeypatch) -> None:
        pkg_a = tmp_path / "dup_a"
        pkg_b = tmp_path / "dup_b"
        pkg_a.mkdir()
        pkg_b.mkdir()
        (pkg_a / "__init__.py").write_text("from dup_b.shared import SharedProvider")
        (pkg_b / "__init__.py").write_text("")
        (pkg_b / "shared.py").write_text(
            dedent(
                """
                from quadkit.di.provider import Provider

                class SharedProvider(Provider):
                    pass
                """
            )
        )
        self._install(tmp_path, "dup_a", monkeypatch)
        self._install(tmp_path, "dup_b", monkeypatch)

        found = discovery.discover_providers(("dup_a", "dup_b"))
        # SharedProvider is defined in dup_b.shared, only collected there.
        assert [type(p).__name__ for p in found] == ["SharedProvider"]

    def test_missing_package_returns_empty(self) -> None:
        assert discovery.discover_providers(("no_such_pkg_zz",)) == []

    @staticmethod
    def _install(root: Path, name: str, monkeypatch) -> None:
        monkeypatch.syspath_prepend(str(root))
        for mod_name in list(__import__("sys").modules):
            if mod_name == name or mod_name.startswith(name + "."):
                del __import__("sys").modules[mod_name]


# ── discover_injectables ──────────────────────────────────────────────────


class TestDiscoverInjectables:
    def test_finds_decorated_classes(self, tmp_path: Path, monkeypatch) -> None:
        pkg_dir = tmp_path / "inj_pkg"
        (pkg_dir / "sub").mkdir(parents=True)
        (pkg_dir / "__init__.py").write_text("")
        (pkg_dir / "sub" / "__init__.py").write_text("")
        (pkg_dir / "sub" / "svc.py").write_text(
            dedent(
                """
                from quadkit.di.decorators import singleton, transient

                @singleton
                class Repo:
                    pass

                @transient
                class Service:
                    pass
                """
            )
        )
        TestDiscoverProviders._install(tmp_path, "inj_pkg", monkeypatch)

        results = discovery.discover_injectables(("inj_pkg",))
        by_name = {cls.__name__: scope for cls, scope in results}
        assert by_name["Repo"] is ServiceScope.SINGLETON
        assert by_name["Service"] is ServiceScope.TRANSIENT

    def test_ignores_undecorated_and_foreign_classes(self, tmp_path: Path, monkeypatch) -> None:
        pkg_dir = tmp_path / "plain_pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("class Plain: pass\n")
        (pkg_dir / "ext.py").write_text("class External: pass\n")
        TestDiscoverProviders._install(tmp_path, "plain_pkg", monkeypatch)

        results = discovery.discover_injectables(("plain_pkg",))
        assert results == []

    def test_missing_package_skipped(self) -> None:
        assert discovery.discover_injectables(("no_such_pkg_zz",)) == []

    def test_module_with_getattr_errors(self, tmp_path: Path, monkeypatch) -> None:
        pkg_dir = tmp_path / "err_pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")
        (pkg_dir / "bad.py").write_text(
            "class BadAttr:\n    @property\n    def boom(self):\n        raise AttributeError('x')\n"
        )
        TestDiscoverProviders._install(tmp_path, "err_pkg", monkeypatch)
        # Must not raise — getattr failures are logged and skipped.
        results = discovery.discover_injectables(("err_pkg",))
        assert results == []


# ── discover_modules_from_entry_points ────────────────────────────────────


class TestEntryPointDiscovery:
    def test_loads_module_subclasses(self, monkeypatch) -> None:
        from quadkit.di.module import Module

        class MyModule(Module):
            name = "entry-point-module"

        class NotAModule:
            pass

        def fake_entry_points(group: str | None = None, name: str | None = None):
            assert group == "quadkit.modules"
            ok = MagicMock(name="ok")
            ok.name = "good"
            ok.load.return_value = MyModule

            bad = MagicMock(name="bad")
            bad.name = "bad-type"
            bad.load.return_value = NotAModule

            broken = MagicMock(name="broken")
            broken.name = "broken"
            broken.load.side_effect = RuntimeError("cannot load")

            return [ok, bad, broken]

        monkeypatch.setattr(importlib.metadata, "entry_points", fake_entry_points)
        result = discovery.discover_modules_from_entry_points()
        assert result == {"good": MyModule}

    def test_default_group_constant(self) -> None:
        import inspect

        sig = inspect.signature(discovery.discover_modules_from_entry_points)
        assert sig.parameters["group"].default == "quadkit.modules"


# ── discover_modules_from_directories ─────────────────────────────────────


class TestDirectoryDiscovery:
    def test_discovers_plugin_py(self, tmp_path: Path) -> None:
        from quadkit.di.module import Module

        plugin_dir = tmp_path / "pluggable"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.py").write_text(
            dedent(
                """
                from quadkit.di.module import Module

                class DirectoryModule(Module):
                    name = "directory-module"
                """
            )
        )
        result = discovery.discover_modules_from_directories([plugin_dir])
        assert set(result) == {"DirectoryModule"}
        assert issubclass(result["DirectoryModule"], Module)

    def test_init_py_used_when_no_plugin(self, tmp_path: Path) -> None:

        plugin_dir = tmp_path / "initpkg"
        plugin_dir.mkdir()
        (plugin_dir / "__init__.py").write_text(
            dedent(
                """
                from quadkit.di.module import Module

                class InitModule(Module):
                    name = "init-module"
                """
            )
        )
        result = discovery.discover_modules_from_directories([plugin_dir])
        assert set(result) == {"InitModule"}

    def test_plugin_py_takes_precedence(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "both"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.py").write_text(
            "from quadkit.di.module import Module\n"
            "class FromPlugin(Module):\n    name = 'p'\n"
        )
        (plugin_dir / "__init__.py").write_text(
            "from quadkit.di.module import Module\n"
            "class FromInit(Module):\n    name = 'i'\n"
        )
        result = discovery.discover_modules_from_directories([plugin_dir])
        assert set(result) == {"FromPlugin"}

    def test_nonexistent_and_file_paths_skipped(self, tmp_path: Path) -> None:
        a_file = tmp_path / "afile.py"
        a_file.write_text("x = 1")
        result = discovery.discover_modules_from_directories(
            [tmp_path / "missing", a_file]
        )
        assert result == {}

    def test_broken_plugin_skipped_with_warning(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "broken"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.py").write_text("raise ImportError('kaboom')")
        result = discovery.discover_modules_from_directories([plugin_dir])
        assert result == {}

    def test_empty_dir_without_candidates(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        assert discovery.discover_modules_from_directories([empty]) == {}
