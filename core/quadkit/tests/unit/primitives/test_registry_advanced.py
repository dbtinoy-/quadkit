"""Advanced Registry behaviour: factories, hooks, freeze, priority, subclasses."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.exceptions.infra import (
    RegistryAlreadyExistsError,
    RegistryKeyError,
)
from quadkit.primitives.registry.core import (
    BackendRegistry,
    Registry,
    StrategyRegistry,
    on_register,
    on_unregister,
)


class TestRegistryFactories:
    def test_factory_resolves_and_caches(self) -> None:
        reg = Registry[str, int](name="r")
        calls: list[str] = []

        def factory() -> int:
            calls.append("built")
            return 42

        reg.register_factory("n", factory)
        assert reg.factories() == ["n"]
        assert reg.get("n") == 42
        # Cached: factory removed, item present, no second build
        assert reg.get("n") == 42
        assert calls == ["built"]
        assert reg.factories() == []
        assert reg.has("n")

    def test_resolve_factory(self) -> None:
        reg = Registry[str, str](name="r")
        reg.register_factory("k", lambda: "v")
        assert reg.resolve("k") == "v"
        assert reg.resolve("k") == "v"  # cached

    def test_get_default_and_missing(self) -> None:
        reg = Registry[str, int](name="r")
        assert reg.get("missing") is None
        assert reg.get("missing", -1) == -1
        with pytest.raises(RegistryKeyError):
            reg.resolve("missing")
        with pytest.raises(RegistryKeyError):
            reg.get_or_raise("missing")


class TestRegistryOverwrite:
    def test_duplicate_raises_by_default(self) -> None:
        reg = Registry[str, int](name="r")
        reg.register("k", 1)
        with pytest.raises(RegistryAlreadyExistsError):
            reg.register("k", 2)

    def test_duplicate_allowed_with_flag(self) -> None:
        reg = Registry[str, int](name="r")
        reg.register("k", 1)
        reg.register("k", 2, allow_overwrite=True)
        assert reg.get("k") == 2

    def test_constructor_allow_overwrite(self) -> None:
        reg = Registry[str, int](name="r", allow_overwrite=True)
        reg.register("k", 1)
        reg.register("k", 2)
        assert reg.get("k") == 2

    def test_item_and_factory_cross_conflict(self) -> None:
        reg = Registry[str, int](name="r")
        reg.register_factory("k", lambda: 1)
        with pytest.raises(RegistryAlreadyExistsError):
            reg.register("k", 2)
        reg.register("k", 2, allow_overwrite=True)
        # item wins on lookup
        assert reg.get("k") == 2


class TestRegistryFreeze:
    @pytest.mark.parametrize(
        ("op", "call"),
        [
            ("register", lambda r: r.register("x", 1)),
            ("register_factory", lambda r: r.register_factory("x", lambda: 1)),
            ("unregister", lambda r: r.unregister("k")),
            ("clear", lambda r: r.clear()),
        ],
    )
    def test_frozen_blocks_mutations(self, op: str, call) -> None:
        reg = Registry[str, int](name="r")
        reg.register("k", 1)
        reg.freeze()
        assert reg.is_frozen
        with pytest.raises(RegistryAlreadyExistsError):
            call(reg)

    def test_frozen_reads_still_work(self) -> None:
        reg = Registry[str, int](name="r")
        reg.register("k", 1)
        reg.freeze()
        assert reg.get("k") == 1
        assert reg.resolve("k") == 1
        assert reg.has("k")
        assert len(reg) == 1
        assert "k" in reg
        assert list(reg) == ["k"]
        assert reg.items() == [("k", 1)]
        assert reg.keys() == ["k"]
        assert reg.values() == [1]
        assert reg.all_keys() == {"k"}
        assert "Registry" in repr(reg)

    def test_register_many(self) -> None:
        reg = Registry[str, int](name="r")
        reg.register_many([("a", 1), ("b", 2)])
        assert reg.items() == [("a", 1), ("b", 2)]
        with pytest.raises(RegistryAlreadyExistsError):
            reg.register_many([("a", 9)])


class TestRegistryHooks:
    def test_decorator_hooks_fire(self) -> None:
        events: list[tuple[str, Any]] = []

        class HookedRegistry(Registry[str, int]):
            @on_register
            def _on_reg(self, key: str, value: Any) -> None:
                events.append(("reg", key))

            @on_unregister
            def _on_unreg(self, key: str, value: Any) -> None:
                events.append(("unreg", key))

        reg = HookedRegistry(name="r")
        reg.register("k", 1)
        reg.register_factory("f", lambda: 2)
        reg.resolve("f")  # materialization re-triggers on_register
        reg.unregister("k")
        assert ("reg", "k") in events
        assert ("reg", "f") in events
        assert ("unreg", "k") in events

    def test_hook_errors_do_not_crash(self) -> None:
        class BadHookRegistry(Registry[str, int]):
            @on_register
            def _boom(self, key: str, value: Any) -> None:
                raise RuntimeError("hook failure")

        reg = BadHookRegistry(name="r")
        reg.register("k", 1)  # must not raise
        assert reg.get("k") == 1


class TestRegistryDecorator:
    def test_register_as_decorator_returns_object(self) -> None:
        reg = Registry[str, Any](name="r")

        @reg.register("cls")
        class Thing:
            pass

        assert reg.get("cls") is Thing

    def test_register_requires_key(self) -> None:
        reg = Registry[str, Any](name="r")
        with pytest.raises(TypeError):
            reg.register()  # key is always required

    def test_register_decorator_infers_key_from_name(self) -> None:
        reg = Registry[str, Any](name="r")

        @reg.register_decorator()
        def standalone() -> None:
            pass

        assert reg.get("standalone") is standalone

    def test_register_decorator_infers_key_from_name_attr(self) -> None:
        reg = Registry[str, Any](name="r")

        class Holder:
            def __init__(self) -> None:
                self.name = "by_name"

        obj = Holder()
        reg.register_decorator()(obj)
        # Instances have no __name__, so the .name attribute is used
        assert reg.get("by_name") is obj

    def test_register_decorator_falls_back_to_str(self) -> None:
        reg = Registry[str, Any](name="r")

        class Unnamed:
            pass

        obj = Unnamed()
        reg.register_decorator()(obj)
        assert reg.get(str(obj)) is obj


class TestRegistryPriority:
    def test_values_ordered_by_priority_key(self) -> None:
        reg = Registry[str, int](name="r", priority_key=lambda v: -v)
        reg.register("a", 1)
        reg.register("b", 3)
        reg.register("c", 2)
        # ascending by priority key: v=3 (-3) first
        assert reg.values_ordered() == [3, 2, 1]

    def test_values_ordered_without_key_is_insertion(self) -> None:
        reg = Registry[str, int](name="r")
        reg.register("a", 1)
        reg.register("b", 2)
        assert reg.values_ordered() == [1, 2]


class TestBackendRegistry:
    def _backend(self, accepts: set[str], priority: int = 0) -> type:
        class Backend:
            pass

        Backend.can_create = staticmethod(
            lambda config: config.get("type") in accepts,
        )
        Backend.priority = priority
        return Backend

    def test_select_returns_first_capable(self) -> None:
        reg = BackendRegistry(name="backends")
        redis_cls = self._backend({"redis"})
        memory_cls = self._backend({"memory"})
        reg.register("redis", redis_cls)
        reg.register("memory", memory_cls)

        assert reg.select({"type": "memory"}) is memory_cls
        assert reg.select({"type": "redis"}) is redis_cls
        assert reg.all_backends() == [redis_cls, memory_cls]

    def test_select_raises_when_none_capable(self) -> None:
        reg = BackendRegistry(name="backends")
        reg.register("redis", self._backend({"redis"}))
        with pytest.raises(ValueError, match="No backend"):
            reg.select({"type": "cassandra"})

    def test_register_backend_alias(self) -> None:
        reg = BackendRegistry(name="backends")
        cls = self._backend({"x"})
        reg.register_backend("x", cls)
        assert reg.get("x") is cls


class TestStrategyRegistry:
    def test_instantiate_forwards_kwargs(self) -> None:
        class Dummy:
            def __init__(self, size: int = 0) -> None:
                self.size = size

        reg = StrategyRegistry(name="strategies")
        reg.register_strategy("dummy", Dummy)
        instance = reg.instantiate("dummy", size=7)
        assert isinstance(instance, Dummy)
        assert instance.size == 7

    def test_instantiate_missing_raises(self) -> None:
        reg = StrategyRegistry(name="strategies")
        with pytest.raises(RegistryKeyError):
            reg.instantiate("nope")

    def test_with_defaults_uses_default_strategies(self) -> None:
        class A:
            pass

        class B:
            pass

        class MyRegistry(StrategyRegistry):
            def __init__(self) -> None:
                super().__init__(name="mine")

            @classmethod
            def default_strategies(cls) -> dict[str, type]:
                return {"a": A, "b": B}

        reg = MyRegistry.with_defaults()
        assert reg.get("a") is A
        assert reg.get("b") is B

    def test_with_defaults_without_strategies_raises(self) -> None:
        with pytest.raises(NotImplementedError, match="built-in strategies"):
            StrategyRegistry().with_defaults()
        with pytest.raises(NotImplementedError, match="built-in default set"):
            Registry[str, int]().with_defaults()
