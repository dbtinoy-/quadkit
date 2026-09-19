"""Tests for get_module_by_name reflection method."""

from __future__ import annotations

from _fixtures import CoreModule, CacheModule, WebModule


class TestGetModuleByNameIntegration:
    """Test finding modules by name in a realistic multi-module graph."""

    def test_finds_core_module(self, graph) -> None:
        result = graph.get_module_by_name("CoreModule")
        assert result is CoreModule

    def test_finds_cache_module(self, graph) -> None:
        result = graph.get_module_by_name("CacheModule")
        assert result is CacheModule

    def test_finds_web_module(self, graph) -> None:
        result = graph.get_module_by_name("WebModule")
        assert result is WebModule

    def test_returns_none_for_missing(self, graph) -> None:
        result = graph.get_module_by_name("DoesNotExist")
        assert result is None

    def test_name_matching_is_exact(self, graph) -> None:
        result = graph.get_module_by_name("Core")
        assert result is None

    def test_case_sensitive_matching(self, graph) -> None:
        result = graph.get_module_by_name("coremodule")
        assert result is None
