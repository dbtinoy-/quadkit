"""Tests for get_boot_level reflection method."""

from __future__ import annotations

from _fixtures import CoreModule, CacheModule, WebModule


class TestGetBootLevelIntegration:
    """Test boot level ordering in the multi-module graph."""

    def test_core_module_has_boot_level(self, graph) -> None:
        level = graph.get_boot_level(CoreModule)
        assert level is not None
        assert isinstance(level, int)

    def test_cache_module_has_boot_level(self, graph) -> None:
        level = graph.get_boot_level(CacheModule)
        assert level is not None
        assert isinstance(level, int)

    def test_web_module_has_boot_level(self, graph) -> None:
        level = graph.get_boot_level(WebModule)
        assert level is not None
        assert isinstance(level, int)

    def test_core_boots_first(self, graph) -> None:
        core_level = graph.get_boot_level(CoreModule)
        cache_level = graph.get_boot_level(CacheModule)
        web_level = graph.get_boot_level(WebModule)

        assert core_level is not None
        assert cache_level is not None
        assert web_level is not None

        assert core_level <= cache_level
        assert core_level <= web_level

    def test_cache_boots_before_or_with_web(self, graph) -> None:
        cache_level = graph.get_boot_level(CacheModule)
        web_level = graph.get_boot_level(WebModule)

        assert cache_level is not None
        assert web_level is not None
        assert cache_level <= web_level

    def test_boot_levels_are_non_negative(self, graph) -> None:
        core_level = graph.get_boot_level(CoreModule)
        cache_level = graph.get_boot_level(CacheModule)
        web_level = graph.get_boot_level(WebModule)

        assert core_level is not None
        assert core_level >= 0
        assert cache_level is not None
        assert cache_level >= 0
        assert web_level is not None
        assert web_level >= 0

    def test_unknown_module_returns_none(self, graph) -> None:
        class UnknownModule:
            pass

        level = graph.get_boot_level(UnknownModule)
        assert level is None

    def test_boot_levels_reflect_dependency_order(self, graph) -> None:
        core_level = graph.get_boot_level(CoreModule)
        cache_level = graph.get_boot_level(CacheModule)

        assert core_level is not None
        assert cache_level is not None
        assert core_level <= cache_level
