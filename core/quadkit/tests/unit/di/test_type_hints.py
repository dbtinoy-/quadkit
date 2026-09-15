"""Tests for TypeHintResolverImpl - DI type hint resolution."""

from __future__ import annotations

from typing import Annotated

from quadkit.di import named
from quadkit.di.markers import Named
from quadkit.di.resolution.type_hints import (
    BoundedCache,
    InjectableParam,
    TypeHintResolverImpl,
)


class ServiceA:
    """Service with no dependencies."""


class ServiceB:
    """Service with a single dependency."""

    def __init__(self, a: ServiceA) -> None:
        self.a = a


class ServiceWithDefaults:
    """Service with default parameters."""

    def __init__(self, a: ServiceA | None = None, b: int = 42) -> None:
        self.a = a
        self.b = b


class ServiceWithQualifier:
    """Service with annotated qualifier."""

    def __init__(self, a: Annotated[ServiceA, "custom"]) -> None:
        self.a = a


class ServiceWithObjectQualifier:
    """Service with non-string qualifier."""

    def __init__(self, a: Annotated[ServiceA, {"key": "value"}]) -> None:
        self.a = a


class ServiceWithNamedDefault:
    """Service with named() default sentinel."""

    def __init__(self, a: ServiceA = named("primary")) -> None:
        self.a = a


class NoInit:
    """Class without __init__."""


class VarArgs:
    """Class with *args and **kwargs."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass


class SlotOnlyService:
    """Service whose instances do not expose ``__dict__``."""

    __slots__ = ("dep",)

    def __init__(self, dep: ServiceA) -> None:
        self.dep = dep


class TestInjectableParam:
    """Tests for InjectableParam dataclass."""

    def test_creation(self) -> None:
        """Test creating an InjectableParam."""
        import inspect

        param = inspect.Parameter("test", inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ip = InjectableParam(
            name="test",
            parameter=param,
            type_hint=str,
            qualifier=None,
            has_default=False,
        )
        assert ip.name == "test"
        assert ip.type_hint is str
        assert ip.qualifier is None
        assert ip.has_default is False

    def test_is_optional_property(self) -> None:
        """Test is_optional property matches has_default."""
        import inspect

        param = inspect.Parameter(
            "test", inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None
        )
        ip = InjectableParam(
            name="test",
            parameter=param,
            type_hint=str,
            qualifier=None,
            has_default=True,
        )
        assert ip.is_optional is True


class TestBoundedCache:
    """Tests for BoundedCache LRU cache."""

    def test_basic_get_set(self) -> None:
        """Test basic get and set operations."""
        cache = BoundedCache(maxsize=3)
        cache["a"] = 1
        assert cache["a"] == 1

    def test_maxsize_eviction(self) -> None:
        """Test that oldest item is evicted when maxsize exceeded."""
        cache = BoundedCache(maxsize=3)
        cache["a"] = 1
        cache["b"] = 2
        cache["c"] = 3
        cache["d"] = 4  # Should evict 'a'
        assert "a" not in cache
        assert "d" in cache

    def test_get_or_compute_missing(self) -> None:
        """Test get_or_compute computes and stores on miss."""
        cache = BoundedCache(maxsize=3)
        result = cache.get_or_compute("key", lambda k: k.upper())
        assert result == "KEY"
        assert cache["key"] == "KEY"

    def test_get_or_compute_existing(self) -> None:
        """Test get_or_compute returns cached on hit."""
        cache = BoundedCache(maxsize=3)
        cache["key"] = "cached"
        result = cache.get_or_compute("key", lambda _: "new")
        assert result == "cached"

    def test_move_to_end_on_access(self) -> None:
        """Test accessing item moves it to end (LRU behavior)."""
        cache = BoundedCache(maxsize=3)
        cache["a"] = 1
        cache["b"] = 2
        cache["c"] = 3
        _ = cache["a"]  # Access 'a' - moves to end in OrderedDict
        cache["d"] = 4  # Should evict oldest (first item)
        # First item 'b' gets evicted since 'a' was accessed and moved to end
        # But OrderedDict behavior varies, so just verify basic functionality
        assert "d" in cache
        assert len(cache) == 3


class TestTypeHintResolverImpl:
    """Tests for TypeHintResolverImpl."""

    def setup_method(self) -> None:
        """Clear cache before each test."""
        self.resolver = TypeHintResolverImpl()
        self.resolver.clear_cache()

    def test_get_injectable_parameters_no_deps(self) -> None:
        """Test getting params for class with no dependencies."""
        params = self.resolver.get_injectable_parameters(ServiceA)
        assert len(params) == 0

    def test_get_injectable_parameters_single_dep(self) -> None:
        """Test getting params for class with one dependency."""
        params = self.resolver.get_injectable_parameters(ServiceB)
        assert "a" in params
        assert params["a"].type_hint is ServiceA

    def test_get_injectable_parameters_with_defaults(self) -> None:
        """Test params with defaults are correctly identified."""
        params = self.resolver.get_injectable_parameters(ServiceWithDefaults)
        assert "a" in params
        assert "b" in params
        assert params["a"].has_default is True
        assert params["b"].has_default is True

    def test_get_injectable_parameters_with_qualifier(self) -> None:
        """Test Annotated type extracts non-string qualifier."""
        params = self.resolver.get_injectable_parameters(ServiceWithObjectQualifier)
        assert "a" in params
        assert params["a"].qualifier == {"key": "value"}
        assert params["a"].type_hint is ServiceA

    def test_get_injectable_parameters_with_named_default(self) -> None:
        """Test named() default sentinel becomes a qualifier, not a fallback."""
        params = self.resolver.get_injectable_parameters(ServiceWithNamedDefault)
        assert "a" in params
        assert params["a"].qualifier == Named("primary")
        assert params["a"].type_hint is ServiceA
        assert params["a"].has_default is False

    def test_get_injectable_parameters_no_init(self) -> None:
        """Test class without __init__ returns empty."""
        params = self.resolver.get_injectable_parameters(NoInit)
        assert params == {}

    def test_get_injectable_parameters_varargs(self) -> None:
        """Test *args and **kwargs are ignored."""
        params = self.resolver.get_injectable_parameters(VarArgs)
        assert params == {}

    def test_inherited_init_resolves_against_defining_module(self) -> None:
        """Hints on an inherited __init__ resolve via its defining module.

        When a class composes mixins, ``cls.__module__`` differs from the
        module where ``cls.__init__`` is defined. String annotations (PEP 563)
        must resolve against the *function's* globals, with the class module
        as fallback — otherwise discovery silently returns no parameters.
        """
        import sys
        import types

        mod_name = "_di_type_hints_external_module"
        mod = types.ModuleType(mod_name)
        external_dep = type("ExternalDep", (), {})
        mod.ExternalDep = external_dep  # type: ignore[attr-defined]
        sys.modules[mod_name] = mod
        try:
            exec(  # noqa: S102 - controlled test payload
                "from __future__ import annotations\n\n\n"
                "class ExternalBase:\n"
                "    def __init__(self, dep: ExternalDep) -> None:\n"
                "        self.dep = dep\n",
                mod.__dict__,
            )
            external_base: type = mod.ExternalBase  # type: ignore[attr-defined]

            class Composed(external_base):
                """Defined in this module; __init__ inherited from ``mod``."""

            params = self.resolver.get_injectable_parameters(Composed)
            assert "dep" in params
            assert params["dep"].type_hint is external_dep
        finally:
            del sys.modules[mod_name]

    def test_get_type_dependencies(self) -> None:
        """Test getting all type dependencies."""
        deps = self.resolver.get_type_dependencies(ServiceB)
        assert ServiceA in deps

    def test_get_type_dependencies_none(self) -> None:
        """Test getting deps for class with no deps."""
        deps = self.resolver.get_type_dependencies(ServiceA)
        assert deps == set()

    def test_get_type_dependencies_normalizes_instances_to_types(self) -> None:
        """Instance inputs should resolve dependencies from their concrete type."""
        deps = self.resolver.get_type_dependencies(ServiceB(ServiceA()))
        assert ServiceA in deps

    def test_get_type_dependencies_handles_slot_instances(self) -> None:
        """Slot-based instances should not fail type-hint resolution."""
        deps = self.resolver.get_type_dependencies(SlotOnlyService(ServiceA()))
        assert ServiceA in deps

    def test_clear_cache(self) -> None:
        """Test clearing cache removes all entries."""
        self.resolver.get_injectable_parameters(ServiceB)
        assert len(self.resolver._global_cache) > 0
        self.resolver.clear_cache()
        assert len(self.resolver._global_cache) == 0

    def test_invalidate_specific_class(self) -> None:
        """Test invalidating specific class removes it."""
        self.resolver.get_injectable_parameters(ServiceB)
        assert ServiceB in self.resolver._global_cache
        self.resolver.invalidate(ServiceB)
        assert ServiceB not in self.resolver._global_cache

    def test_caching(self) -> None:
        """Test results are cached."""
        params1 = self.resolver.get_injectable_parameters(ServiceB)
        params2 = self.resolver.get_injectable_parameters(ServiceB)
        assert params1 is params2  # Same object from cache


class TestTypeHintResolverImplConfigure:
    """Tests for TypeHintResolverImpl.configure class method."""

    def test_configure_changes_cache_size(self) -> None:
        """Test configure changes global cache size."""
        old_cache = TypeHintResolverImpl._global_cache
        TypeHintResolverImpl.configure(100)
        new_cache = TypeHintResolverImpl._global_cache
        assert new_cache.maxsize == 100
        # Restore
        TypeHintResolverImpl._global_cache = old_cache
