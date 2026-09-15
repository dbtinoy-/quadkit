"""Tests for get_exports_for_module reflection method."""

from __future__ import annotations

import pytest

from _fixtures import CoreModule, CacheModule, WebModule, CoreService, CacheService, WebHandler


class TestGetExportsForModuleIntegration:
    """Test querying module exports in a realistic graph."""

    def test_core_exports_core_service(self, graph) -> None:
        exports = graph.get_exports_for_module(CoreModule)
        assert CoreService in exports

    def test_cache_exports_cache_service(self, graph) -> None:
        exports = graph.get_exports_for_module(CacheModule)
        assert CacheService in exports

    def test_web_exports_web_handler(self, graph) -> None:
        exports = graph.get_exports_for_module(WebModule)
        assert WebHandler in exports

    def test_exports_returns_frozenset(self, graph) -> None:
        exports = graph.get_exports_for_module(CoreModule)
        assert isinstance(exports, frozenset)

    def test_exports_are_immutable(self, graph) -> None:
        exports = graph.get_exports_for_module(WebModule)
        with pytest.raises(AttributeError):
            exports.add(CoreService)

    def test_unknown_module_returns_empty(self, graph) -> None:
        class UnknownModule:
            pass

        exports = graph.get_exports_for_module(UnknownModule)
        assert len(exports) == 0
        assert isinstance(exports, frozenset)

    def test_exports_count_matches_declaration(self, graph) -> None:
        core_exports = graph.get_exports_for_module(CoreModule)
        cache_exports = graph.get_exports_for_module(CacheModule)
        web_exports = graph.get_exports_for_module(WebModule)

        assert len(core_exports) == 1
        assert len(cache_exports) == 1
        assert len(web_exports) == 1
