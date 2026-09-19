"""Tests for get_importing_modules reflection method."""

from __future__ import annotations

import pytest

from _fixtures import CoreModule, CacheModule, WebModule


class TestGetImportingModulesIntegration:
    """Test querying which modules import a given module."""

    def test_core_module_imported_by_cache(self, graph) -> None:
        importers = graph.get_importing_modules(CoreModule)
        assert CacheModule in importers

    def test_core_module_imported_by_web(self, graph) -> None:
        importers = graph.get_importing_modules(CoreModule)
        assert WebModule in importers

    def test_core_module_imported_by_both_cache_and_web(self, graph) -> None:
        importers = graph.get_importing_modules(CoreModule)
        assert CacheModule in importers
        assert WebModule in importers
        assert len(importers) == 2

    def test_cache_module_imported_by_web(self, graph) -> None:
        importers = graph.get_importing_modules(CacheModule)
        assert WebModule in importers

    def test_cache_module_not_imported_by_core(self, graph) -> None:
        importers = graph.get_importing_modules(CacheModule)
        assert CoreModule not in importers

    def test_web_module_not_imported_by_anyone(self, graph) -> None:
        importers = graph.get_importing_modules(WebModule)
        assert len(importers) == 0

    def test_importing_modules_returns_frozenset(self, graph) -> None:
        importers = graph.get_importing_modules(CoreModule)
        assert isinstance(importers, frozenset)

    def test_importing_modules_is_immutable(self, graph) -> None:
        importers = graph.get_importing_modules(CoreModule)
        with pytest.raises(AttributeError):
            importers.add(WebModule)

    def test_unknown_module_returns_empty(self, graph) -> None:
        class UnknownModule:
            pass

        importers = graph.get_importing_modules(UnknownModule)
        assert len(importers) == 0
        assert isinstance(importers, frozenset)
