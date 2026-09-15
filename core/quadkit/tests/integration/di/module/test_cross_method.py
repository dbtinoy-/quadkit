"""Tests for interactions between multiple reflection methods."""

from __future__ import annotations

from _fixtures import CoreModule, CacheModule, WebModule, CoreService, CacheService


class TestCrossMethodIntegration:
    """Test interactions between multiple reflection methods."""

    def test_get_module_by_name_and_get_exports_match(self, graph) -> None:
        module_cls = graph.get_module_by_name("CoreModule")
        assert module_cls is CoreModule

        exports = graph.get_exports_for_module(CoreModule)
        assert CoreService in exports

    def test_importers_and_dependency_chain_are_inverse(self, graph) -> None:
        cache_chain = graph.get_dependency_chain(CacheModule)
        core_importers = graph.get_importing_modules(CoreModule)

        assert CoreModule in cache_chain
        assert CacheModule in core_importers

    def test_boot_level_respects_import_structure(self, graph) -> None:
        core_level = graph.get_boot_level(CoreModule)
        cache_level = graph.get_boot_level(CacheModule)
        web_level = graph.get_boot_level(WebModule)

        assert core_level is not None
        assert core_level >= 0

        assert cache_level is not None
        assert core_level <= cache_level

        assert web_level is not None
        assert core_level <= web_level
        assert cache_level <= web_level

    def test_exports_and_importing_modules_are_consistent(self, graph) -> None:
        cache_importers = graph.get_importing_modules(CacheModule)
        cache_exports = graph.get_exports_for_module(CacheModule)

        assert WebModule in cache_importers
        assert CacheService in cache_exports

        web_node = graph.get_module(WebModule)
        assert web_node is not None

    def test_graph_structure_consistency(self, graph) -> None:
        for module_cls in [CoreModule, CacheModule, WebModule]:
            name = module_cls.__name__
            result = graph.get_module_by_name(name)
            assert result is module_cls

        for module_cls in [CoreModule, CacheModule, WebModule]:
            level = graph.get_boot_level(module_cls)
            assert level is not None, f"{module_cls.__name__} should have a boot level"

    def test_dependency_relationships_form_dag(self, graph) -> None:
        web_deps = set(graph.get_dependency_chain(WebModule))
        cache_deps = set(graph.get_dependency_chain(CacheModule))
        core_deps = set(graph.get_dependency_chain(CoreModule))

        assert WebModule not in cache_deps
        assert WebModule not in core_deps

        assert CacheModule not in core_deps
