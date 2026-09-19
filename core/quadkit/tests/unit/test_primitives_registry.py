"""Tests for primitives/registry/core.py — the base Registry class."""

from __future__ import annotations

import pytest

from quadkit.contracts.exceptions.infra import (
    RegistryAlreadyExistsError,
    RegistryKeyError,
)
from quadkit.primitives.registry.core import Registry


class TestRegistryBasics:
    """Tests for basic Registry operations."""

    def test_registry_initializes_with_name(self) -> None:
        """Registry gets name from class if not provided."""
        registry = Registry[str, str]()
        assert registry.name == "Registry"

    def test_registry_with_custom_name(self) -> None:
        """Registry accepts custom name."""
        registry = Registry[str, str](name="custom")
        assert registry.name == "custom"

    def test_registry_not_frozen_by_default(self) -> None:
        """Registry starts unfrozen."""
        registry = Registry[str, str]()
        assert registry.is_frozen is False

    def test_registry_allow_overwrite_false_by_default(self) -> None:
        """Registry denies overwrites by default."""
        registry = Registry[str, str]()
        assert registry.allow_overwrite is False


class TestRegistryRegister:
    """Tests for register method."""

    def test_register_stores_value(self) -> None:
        """register stores the value."""
        registry = Registry[str, str]()
        registry.register("key", "value")
        assert registry.get("key") == "value"

    def test_register_returns_value(self) -> None:
        """register returns the registered value."""
        registry = Registry[str, str]()
        result = registry.register("key", "value")
        assert result == "value"

    def test_register_duplicate_raises(self) -> None:
        """register raises on duplicate key by default."""
        registry = Registry[str, str]()
        registry.register("key", "value")
        with pytest.raises(RegistryAlreadyExistsError, match="already registered"):
            registry.register("key", "new_value")

    def test_register_with_overwrite_flag(self) -> None:
        """register allows overwrite when explicitly permitted."""
        registry = Registry[str, str](allow_overwrite=True)
        registry.register("key", "value1")
        registry.register("key", "value2")
        assert registry.get("key") == "value2"

    def test_register_on_frozen_raises(self) -> None:
        """register raises on frozen registry."""
        registry = Registry[str, str]()
        registry.freeze()
        with pytest.raises(RegistryAlreadyExistsError, match="frozen"):
            registry.register("key", "value")


class TestRegistryRegisterFactory:
    """Tests for register_factory method."""

    def test_register_factory_stores_factory(self) -> None:
        """register_factory stores the factory."""
        registry = Registry[str, str]()
        registry.register_factory("key", lambda: "value")
        assert "key" in registry.factories()

    def test_register_factory_get_resolves(self) -> None:
        """get resolves factory and caches result."""
        registry = Registry[str, str]()
        call_count = [0]

        def factory() -> str:
            call_count[0] += 1
            return "created"

        registry.register_factory("key", factory)
        assert registry.get("key") == "created"
        assert call_count[0] == 1

    def test_register_factory_caches_on_first_get(self) -> None:
        """Factory is called once and cached."""
        call_count = [0]
        registry = Registry[str, str]()

        def factory() -> str:
            call_count[0] += 1
            return "value"

        registry.register_factory("key", factory)
        registry.get("key")
        registry.get("key")
        assert call_count[0] == 1

    def test_register_factory_duplicate_raises(self) -> None:
        """register_factory raises on duplicate key."""
        registry = Registry[str, str]()
        registry.register_factory("key", lambda: "value")
        with pytest.raises(
            RegistryAlreadyExistsError, match=r"Factory.*already registered"
        ):
            registry.register_factory("key", lambda: "other")

    def test_register_factory_on_frozen_raises(self) -> None:
        """register_factory raises on frozen registry."""
        registry = Registry[str, str]()
        registry.freeze()
        with pytest.raises(RegistryAlreadyExistsError, match="frozen"):
            registry.register_factory("key", lambda: "value")


class TestRegistryDecorator:
    """Tests for decorator-style registration."""

    def test_register_without_value_returns_decorator(self) -> None:
        """register(key) without value returns decorator function."""
        registry = Registry[str, str]()
        decorator = registry.register("my_key")
        assert callable(decorator)

    def test_decorator_registers_value(self) -> None:
        """Using decorator registers the decorated value."""
        registry = Registry[str, str]()

        @registry.register("handler")
        class Handler:
            pass

        assert registry.get("handler") is Handler

    def test_decorator_returns_original_class(self) -> None:
        """Decorator returns the original class unchanged."""
        registry = Registry[str, str]()

        @registry.register("handler")
        class Handler:
            pass

        assert Handler.__name__ == "Handler"


class TestRegistryGet:
    """Tests for get method."""

    def test_get_returns_registered_value(self) -> None:
        """get returns the registered value."""
        registry = Registry[str, str]()
        registry.register("key", "value")
        assert registry.get("key") == "value"

    def test_get_returns_default_for_missing(self) -> None:
        """get returns default when key not found."""
        registry = Registry[str, str]()
        assert registry.get("missing", "default") == "default"

    def test_get_returns_none_by_default(self) -> None:
        """get returns None when no default provided."""
        registry = Registry[str, str]()
        assert registry.get("missing") is None

    def test_get_resolves_factory(self) -> None:
        """get resolves factory if present."""
        registry = Registry[str, str]()
        registry.register_factory("key", lambda: "factory_value")
        assert registry.get("key") == "factory_value"


class TestRegistryResolve:
    """Tests for resolve method."""

    def test_resolve_returns_value(self) -> None:
        """resolve returns registered value."""
        registry = Registry[str, str]()
        registry.register("key", "value")
        assert registry.resolve("key") == "value"

    def test_resolve_raises_on_missing(self) -> None:
        """resolve raises RegistryKeyError when key not found."""
        registry = Registry[str, str]()
        with pytest.raises(RegistryKeyError, match="not found"):
            registry.resolve("missing")

    def test_resolve_is_alias_for_get_or_raise(self) -> None:
        """resolve is alias for get_or_raise."""
        registry = Registry[str, str]()
        registry.register("key", "value")
        assert registry.resolve("key") == registry.get_or_raise("key")


class TestRegistryHas:
    """Tests for has method."""

    def test_has_true_after_register(self) -> None:
        """has returns True for registered key."""
        registry = Registry[str, str]()
        registry.register("key", "value")
        assert registry.has("key") is True

    def test_has_false_for_missing(self) -> None:
        """has returns False for missing key."""
        registry = Registry[str, str]()
        assert registry.has("missing") is False

    def test_has_true_for_factory(self) -> None:
        """has returns True for registered factory."""
        registry = Registry[str, str]()
        registry.register_factory("key", lambda: "value")
        assert registry.has("key") is True


class TestRegistryUnregister:
    """Tests for unregister method."""

    def test_unregister_removes_item(self) -> None:
        """unregister removes the registered item."""
        registry = Registry[str, str]()
        registry.register("key", "value")
        result = registry.unregister("key")
        assert result == "value"
        assert not registry.has("key")

    def test_unregister_returns_none_for_factory(self) -> None:
        """unregister returns None for factory (not the created value)."""
        registry = Registry[str, str]()
        registry.register_factory("key", lambda: "value")
        result = registry.unregister("key")
        assert result is None

    def test_unregister_missing_returns_none(self) -> None:
        """unregister returns None for missing key."""
        registry = Registry[str, str]()
        assert registry.unregister("missing") is None

    def test_unregister_on_frozen_raises(self) -> None:
        """unregister raises on frozen registry."""
        registry = Registry[str, str]()
        registry.register("key", "value")
        registry.freeze()
        with pytest.raises(RegistryAlreadyExistsError, match="frozen"):
            registry.unregister("key")


class TestRegistryKeysValuesItems:
    """Tests for keys/values/items methods."""

    def test_keys_returns_registered_keys(self) -> None:
        """keys returns only item keys, not factory keys."""
        registry = Registry[str, str]()
        registry.register("key1", "value1")
        registry.register_factory("key2", lambda: "value2")
        assert list(registry.keys()) == ["key1"]

    def test_values_returns_values(self) -> None:
        """values returns registered values."""
        registry = Registry[str, str]()
        registry.register("a", "1")
        registry.register("b", "2")
        assert set(registry.values()) == {"1", "2"}

    def test_items_returns_key_value_pairs(self) -> None:
        """items returns (key, value) tuples."""
        registry = Registry[str, str]()
        registry.register("a", "1")
        registry.register("b", "2")
        items = dict(registry.items())
        assert items == {"a": "1", "b": "2"}

    def test_factories_returns_factory_keys(self) -> None:
        """factories returns keys with registered factories."""
        registry = Registry[str, str]()
        registry.register("direct", "value")
        registry.register_factory("lazy", lambda: "value")
        assert list(registry.factories()) == ["lazy"]

    def test_all_keys_returns_both(self) -> None:
        """all_keys returns both item and factory keys."""
        registry = Registry[str, str]()
        registry.register("direct", "value")
        registry.register_factory("lazy", lambda: "value")
        assert set(registry.all_keys()) == {"direct", "lazy"}


class TestRegistryClear:
    """Tests for clear method."""

    def test_clear_removes_all_items(self) -> None:
        """clear removes all registered items."""
        registry = Registry[str, str]()
        registry.register("a", "1")
        registry.register("b", "2")
        registry.clear()
        assert list(registry.keys()) == []

    def test_clear_removes_factories(self) -> None:
        """clear also removes factories."""
        registry = Registry[str, str]()
        registry.register_factory("lazy", lambda: "value")
        registry.clear()
        assert list(registry.factories()) == []

    def test_clear_on_frozen_raises(self) -> None:
        """clear raises on frozen registry."""
        registry = Registry[str, str]()
        registry.register("key", "value")
        registry.freeze()
        with pytest.raises(RegistryAlreadyExistsError, match="frozen"):
            registry.clear()


class TestRegistryFreeze:
    """Tests for freeze functionality."""

    def test_freeze_prevents_registration(self) -> None:
        """After freeze, register raises."""
        registry = Registry[str, str]()
        registry.freeze()
        with pytest.raises(RegistryAlreadyExistsError):
            registry.register("key", "value")

    def test_freeze_prevents_factory_registration(self) -> None:
        """After freeze, register_factory raises."""
        registry = Registry[str, str]()
        registry.freeze()
        with pytest.raises(RegistryAlreadyExistsError):
            registry.register_factory("key", lambda: "value")

    def test_freeze_allows_read_operations(self) -> None:
        """After freeze, get/resolve still work."""
        registry = Registry[str, str]()
        registry.register("key", "value")
        registry.freeze()
        assert registry.get("key") == "value"
        assert registry.has("key") is True


class TestRegistryPriorityOrdering:
    """Tests for priority-based ordering."""

    def test_values_ordered_by_priority_key(self) -> None:
        """values_ordered sorts by priority_key if provided."""
        registry = Registry[str, int](priority_key=lambda x: x)
        registry.register("a", 3)
        registry.register("b", 1)
        registry.register("c", 2)
        assert registry.values_ordered() == [1, 2, 3]

    def test_values_ordered_without_priority_key(self) -> None:
        """values_ordered returns insertion order without priority_key."""
        registry = Registry[str, int]()
        registry.register("a", 1)
        registry.register("b", 2)
        registry.register("c", 3)
        assert registry.values_ordered() == [1, 2, 3]


class TestRegistryIteration:
    """Tests for iteration support."""

    def test_can_iterate_over_keys(self) -> None:
        """Registry keys are iterable."""
        registry = Registry[str, str]()
        registry.register("a", "1")
        registry.register("b", "2")
        keys = list(registry.keys())
        assert set(keys) == {"a", "b"}


class _BuiltinRegistry(Registry[str, str]):
    """Minimal registry declaring a static built-in set."""

    @classmethod
    def _default_entries(cls) -> dict[str, str]:
        return {"alpha": "a", "beta": "b"}


class _PluginRegistry(Registry[str, str]):
    """Minimal registry without a built-in set (plugin-driven)."""


class TestRegistryConstruction:
    """Tests for the two construction idioms (explicit vs. with_defaults)."""

    def test_plain_registry_has_no_default_entries_hook(self) -> None:
        """Registry without _default_entries must not advertise with_defaults."""
        with pytest.raises(NotImplementedError, match="does not declare"):
            Registry[str, str].with_defaults()

    def test_with_defaults_prepopulates_declared_entries(self) -> None:
        """with_defaults() returns exactly the declared built-in set."""
        registry = _BuiltinRegistry.with_defaults()
        assert registry.get("alpha") == "a"
        assert registry.get("beta") == "b"
        assert len(registry) == 2

    def test_with_defaults_returns_fresh_instance(self) -> None:
        """with_defaults() never shares state between instances."""
        first = _BuiltinRegistry.with_defaults()
        second = _BuiltinRegistry.with_defaults()
        first.register("gamma", "c")
        assert second.get("gamma") is None

    def test_init_is_always_empty(self) -> None:
        """A registry constructed directly starts empty, even with defaults."""
        assert len(_BuiltinRegistry()) == 0

    def test_plugin_registry_populated_explicitly(self) -> None:
        """Plugin registries are filled via register()/register_many()."""
        registry = _PluginRegistry()
        registry.register("plugin_a", "1")
        registry.register_many([("plugin_b", "2"), ("plugin_c", "3")])
        assert set(registry.keys()) == {"plugin_a", "plugin_b", "plugin_c"}
        assert registry.get("plugin_c") == "3"

    def test_register_many_duplicate_raises(self) -> None:
        """register_many enforces the same duplicate rules as register()."""
        registry = _PluginRegistry()
        registry.register_many([("k", "1")])
        with pytest.raises(RegistryAlreadyExistsError, match="already registered"):
            registry.register_many([("k", "2")])
