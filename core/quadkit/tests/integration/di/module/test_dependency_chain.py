"""Tests for get_dependency_chain reflection method."""

from __future__ import annotations

from _fixtures import CoreModule, CacheModule, WebModule


class TestGetDependencyChainIntegration:
    """Test querying dependency chains in the multi-module graph."""

    def test_core_module_has_no_dependencies(self, graph) -> None:
        chain = graph.get_dependency_chain(CoreModule)
        assert chain == []

    def test_cache_module_depends_on_core(self, graph) -> None:
        chain = graph.get_dependency_chain(CacheModule)
        assert len(chain) == 1
        assert CoreModule in chain

    def test_web_module_dependency_chain_includes_cache_and_core(self, graph) -> None:
        chain = graph.get_dependency_chain(WebModule)
        assert CacheModule in chain
        assert CoreModule in chain
        assert WebModule not in chain

    def test_dependency_chain_bfs_order(self, graph) -> None:
        chain = graph.get_dependency_chain(WebModule)
        assert CoreModule in chain
        assert CacheModule in chain
        assert chain.index(CoreModule) == 0

    def test_dependency_chain_does_not_include_root(self, graph) -> None:
        chain = graph.get_dependency_chain(WebModule)
        assert WebModule not in chain

    def test_unknown_module_returns_empty_list(self, graph) -> None:
        class UnknownModule:
            pass

        chain = graph.get_dependency_chain(UnknownModule)
        assert chain == []
        assert isinstance(chain, list)

    def test_dependency_chain_returns_list_type(self, graph) -> None:
        chain = graph.get_dependency_chain(WebModule)
        assert isinstance(chain, list)
