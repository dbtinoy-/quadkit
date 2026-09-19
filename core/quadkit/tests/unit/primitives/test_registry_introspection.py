"""Registry introspection utilities: registry_info, introspector, catalog."""

from __future__ import annotations

from typing import Any

from quadkit.primitives.registry.core import (
    BackendRegistry,
    Registry,
    StrategyRegistry,
    on_register,
)
from quadkit.primitives.registry.introspection import (
    RegistryIntrospector,
    entry_point_catalog,
    registry_info,
)


class _HookedRegistry(Registry[str, int]):
    @on_register
    def _on(self, key: str, value: Any) -> None:
        pass


class TestRegistryInfo:
    def test_basic_registry(self) -> None:
        reg = Registry[str, int](name="basic")
        reg.register("a", 1)
        reg.register_factory("b", lambda: 2)
        info = registry_info(reg)
        assert info["name"] == "basic"
        assert info["type"] == "Registry"
        assert info["count"] == 1
        assert info["keys"] == ["a"]
        assert info["factory_count"] == 1
        assert info["hooks"] == 0
        assert info["allow_overwrite"] in (True, False)

    def test_backend_and_strategy_types(self) -> None:
        assert registry_info(BackendRegistry(name="b"))["type"] == "BackendRegistry"
        assert registry_info(StrategyRegistry(name="s"))["type"] == "StrategyRegistry"

    def test_hook_count(self) -> None:
        reg = _HookedRegistry(name="hooked")
        assert registry_info(reg)["hooks"] == 1
        assert registry_info(reg)["class"] == "_HookedRegistry"


class TestEntryPointCatalog:
    def test_returns_group_mapping(self) -> None:
        catalog = entry_point_catalog()
        assert isinstance(catalog, dict)
        for group, entries in catalog.items():
            assert group.startswith("quadkit.")
            for entry in entries:
                assert set(entry) == {"name", "value", "group"}
                assert entry["group"] == group


class _FakeContainer:
    def __init__(self, registries: list[Registry[Any, Any]]) -> None:
        self._regs = registries

    async def resolve_all(self, service_type: Any) -> list:
        return self._regs


class TestRegistryIntrospector:
    async def test_from_container(self) -> None:
        r1 = Registry[str, int](name="r1")
        r1.register("k", 1)
        r2 = BackendRegistry(name="r2")

        introspector = await RegistryIntrospector.from_container(
            _FakeContainer([r1, r2])
        )
        infos = introspector.all_info()
        assert {i["name"] for i in infos} == {"r1", "r2"}

    async def test_from_container_with_bindings_fallback(self) -> None:
        reg = Registry[str, int](name="bound")
        reg.register("x", 1)

        class _Binding:
            instance = reg

        class _BindingsContainer:
            _bindings = {"reg": _Binding()}

        introspector = await RegistryIntrospector.from_container(_BindingsContainer())
        assert [i["name"] for i in introspector.all_info()] == ["bound"]

    async def test_from_container_resolve_all_failure(self) -> None:
        class _BrokenContainer:
            async def resolve_all(self, service_type: Any) -> list:
                raise LookupError("nope")

        introspector = await RegistryIntrospector.from_container(_BrokenContainer())
        assert introspector.all_info() == []

    def test_summary(self) -> None:
        r1 = Registry[str, int](name="r1")
        r1.register("a", 1)
        r1.register("b", 2)

        summary = RegistryIntrospector([r1]).summary()
        assert summary["total_registries"] == 1
        assert summary["total_items"] == 2
        assert isinstance(summary["entry_points"], dict)
        assert summary["registries"][0]["name"] == "r1"
