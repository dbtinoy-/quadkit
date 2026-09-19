"""Tests for DependencyInjector (constructor DI)."""

from __future__ import annotations

from typing import Any, Optional
from unittest.mock import MagicMock

import pytest

from quadkit.contracts.exceptions import (
    CircularDependencyError,
    UnresolvableDependencyError,
)
from quadkit.di.markers import Inject, Named, OptionalDep, Qualifier
from quadkit.di.resolution.injector import DependencyInjector
from quadkit.di.resolution.type_hints import InjectableParam


# Simple marker class used as a resolvable "type".
class _Dep:
    pass


class _DepB:
    pass


def _param(
    name: str,
    type_hint: Any,
    *,
    qualifier: Any = None,
    has_default: bool = False,
    default: Any = None,
) -> InjectableParam:
    # Build a real inspect.Parameter so .default is valid.
    import inspect

    if has_default:
        p = inspect.Parameter(name, inspect.Parameter.POSITIONAL_OR_KEYWORD, default=default)
    else:
        p = inspect.Parameter(name, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    return InjectableParam(
        name=name,
        parameter=p,
        type_hint=type_hint,
        qualifier=qualifier,
        has_default=has_default,
    )


class _FakeResolver:
    """Records requested keys and returns canned instances."""

    def __init__(self, values: dict[Any, Any] | None = None, raises: dict[Any, Exception] | None = None):
        self.values = values or {}
        self.raises = raises or {}
        self.requests: list[Any] = []

    async def resolve(self, key: Any) -> Any:
        self.requests.append(key)
        if key in self.raises:
            raise self.raises[key]
        if key in self.values:
            return self.values[key]
        raise UnresolvableDependencyError(dependency=str(key))


def _injector(
    params: dict[str, InjectableParam],
    resolver: _FakeResolver | None = None,
) -> tuple[DependencyInjector, _FakeResolver]:
    th = MagicMock()
    th.get_injectable_parameters.return_value = params
    inj = DependencyInjector(th, resolver)
    return inj, (resolver or _FakeResolver())


class TestNoInjection:
    async def test_plain_class_returns_bare_instance(self) -> None:
        class Plain:
            def __init__(self) -> None:
                self.x = 1

        th = MagicMock()
        inj = DependencyInjector(th)
        assert isinstance(await inj.instantiate(Plain), Plain)
        th.get_injectable_parameters.assert_not_called()

    async def test_force_inject_uses_hints(self) -> None:
        class Target:
            def __init__(self, dep: _Dep) -> None:
                self.dep = dep

        resolver = _FakeResolver({_Dep: "dep-instance"})
        inj, _ = _injector({"dep": _param("dep", _Dep)}, resolver)
        inst = await inj.instantiate(Target, force_inject=True)
        assert inst.dep == "dep-instance"
        assert resolver.requests == [_Dep]


class TestInjection:
    async def test_resolves_by_type(self) -> None:
        class Target:
            def __init__(self, a: _Dep, b: _DepB) -> None:
                self.a = a
                self.b = b

        resolver = _FakeResolver({_Dep: "A", _DepB: "B"})
        inj, _ = _injector(
            {"a": _param("a", _Dep), "b": _param("b", _DepB)},
            resolver,
        )
        inst = await inj.instantiate(Target, force_inject=True)
        assert (inst.a, inst.b) == ("A", "B")

    async def test_any_annotation_skipped(self) -> None:
        class Target:
            def __init__(self, x: Any = None) -> None:
                self.x = x

        resolver = _FakeResolver()
        inj, _ = _injector({"x": _param("x", Any)}, resolver)
        inst = await inj.instantiate(Target, force_inject=True)
        assert inst.x is None
        assert resolver.requests == []

    async def test_named_qualifier_builds_tuple_key(self) -> None:
        class Target:
            def __init__(self, dep: _Dep) -> None:
                self.dep = dep

        resolver = _FakeResolver({(_Dep, "primary"): "named"})
        inj, _ = _injector(
            {"dep": _param("dep", _Dep, qualifier=Named("primary"))},
            resolver,
        )
        inst = await inj.instantiate(Target, force_inject=True)
        assert inst.dep == "named"
        assert resolver.requests == [(_Dep, "primary")]

    async def test_qualifier_value_used_as_key(self) -> None:
        class Target:
            def __init__(self, dep: _Dep) -> None:
                self.dep = dep

        resolver = _FakeResolver({"q-key": "qv"})
        inj, _ = _injector(
            {"dep": _param("dep", _Dep, qualifier=Qualifier("q-key"))},
            resolver,
        )
        inst = await inj.instantiate(Target, force_inject=True)
        assert inst.dep == "qv"
        assert resolver.requests == ["q-key"]

    async def test_inject_marker_name_used_as_key(self) -> None:
        class Target:
            def __init__(self, dep: _Dep) -> None:
                self.dep = dep

        resolver = _FakeResolver({"named-key": "iv"})
        inj, _ = _injector(
            {"dep": _param("dep", _Dep, qualifier=Inject(name="named-key"))},
            resolver,
        )
        inst = await inj.instantiate(Target, force_inject=True)
        assert inst.dep == "iv"
        assert resolver.requests == ["named-key"]

    async def test_optional_annotation_unwrapped(self) -> None:
        class Target:
            def __init__(self, dep: _Dep | None) -> None:
                self.dep = dep

        resolver = _FakeResolver({_Dep: "opt"})
        inj, _ = _injector({"dep": _param("dep", _Dep | None)}, resolver)
        inst = await inj.instantiate(Target, force_inject=True)
        assert inst.dep == "opt"
        assert resolver.requests == [_Dep]

    async def test_pipe_optional_unwrapped(self) -> None:
        class Target:
            def __init__(self, dep: _Dep | None) -> None:
                self.dep = dep

        resolver = _FakeResolver({_Dep: "pipe"})
        inj, _ = _injector({"dep": _param("dep", _Dep | None)}, resolver)
        inst = await inj.instantiate(Target, force_inject=True)
        assert inst.dep == "pipe"
        assert resolver.requests == [_Dep]


class TestFallbacks:
    async def test_optional_dep_fallback_on_unresolvable(self) -> None:
        class Target:
            def __init__(self, dep: _Dep | None) -> None:
                self.dep = dep

        resolver = _FakeResolver({})
        inj, _ = _injector(
            {"dep": _param("dep", _Dep | None, qualifier=OptionalDep(default="fallback"))},
            resolver,
        )
        inst = await inj.instantiate(Target, force_inject=True)
        assert inst.dep == "fallback"

    async def test_inject_default_fallback_on_unresolvable(self) -> None:
        class Target:
            def __init__(self, dep: _Dep) -> None:
                self.dep = dep

        resolver = _FakeResolver({})
        inj, _ = _injector(
            {"dep": _param("dep", _Dep, qualifier=Inject(default="dflt"))},
            resolver,
        )
        inst = await inj.instantiate(Target, force_inject=True)
        assert inst.dep == "dflt"

    async def test_parameter_default_used_when_unresolvable(self) -> None:
        class Target:
            def __init__(self, dep: _Dep | None = "param-default") -> None:
                self.dep = dep

        resolver = _FakeResolver({})
        inj, _ = _injector(
            {"dep": _param("dep", _Dep | None, has_default=True, default="param-default")},
            resolver,
        )
        inst = await inj.instantiate(Target, force_inject=True)
        assert inst.dep == "param-default"

    async def test_unresolvable_raises(self) -> None:
        class Target:
            def __init__(self, dep: _Dep) -> None:
                self.dep = dep

        resolver = _FakeResolver({})
        inj, _ = _injector({"dep": _param("dep", _Dep)}, resolver)
        with pytest.raises(UnresolvableDependencyError):
            await inj.instantiate(Target, force_inject=True)

    async def test_circular_dependency_propagates(self) -> None:
        class Target:
            def __init__(self, dep: _Dep) -> None:
                self.dep = dep

        resolver = _FakeResolver(raises={_Dep: CircularDependencyError("cycle")})
        inj, _ = _injector({"dep": _param("dep", _Dep)}, resolver)
        with pytest.raises(CircularDependencyError):
            await inj.instantiate(Target, force_inject=True)

    async def test_constructor_type_error_wrapped(self) -> None:
        # Hints promise two params, constructor accepts one → TypeError is
        # wrapped into UnresolvableDependencyError.
        class Target:
            def __init__(self, dep: _Dep) -> None:
                self.dep = dep

        resolver = _FakeResolver({_Dep: "A", _DepB: "B"})
        inj, _ = _injector(
            {"dep": _param("dep", _Dep), "other": _param("other", _DepB)},
            resolver,
        )
        with pytest.raises(UnresolvableDependencyError, match="Cannot instantiate"):
            await inj.instantiate(Target, force_inject=True)


class TestResolverWiring:
    async def test_missing_resolver_raises_runtime_error(self) -> None:
        class Target:
            def __init__(self, dep: _Dep) -> None:
                self.dep = dep

        inj, _ = _injector({"dep": _param("dep", _Dep)}, _FakeResolver())
        inj._resolver = None  # noqa: SLF001
        # The internal RuntimeError is surfaced as the public
        # UnresolvableDependencyError (no fallback available).
        with pytest.raises(UnresolvableDependencyError):
            await inj.instantiate(Target, force_inject=True)

    def test_set_resolver(self) -> None:
        inj, _ = _injector({})
        resolver = _FakeResolver()
        inj.set_resolver(resolver)
        assert inj._resolver is resolver  # noqa: SLF001


class TestUnwrapOptional:
    def test_plain_type_unchanged(self) -> None:
        inj, _ = _injector({})
        assert inj._unwrap_optional(_Dep) is _Dep  # noqa: SLF001

    def test_typing_optional(self) -> None:
        # typing.Optional spelling (Union[T, None]) — distinct from the
        # `T | None` union type tested below.
        opt: type = Optional[_Dep]  # noqa: UP045
        inj, _ = _injector({})
        assert inj._unwrap_optional(opt) is _Dep  # noqa: SLF001

    def test_pipe_optional(self) -> None:
        inj, _ = _injector({})
        assert inj._unwrap_optional(_Dep | None) is _Dep  # noqa: SLF001

    def test_multi_union_unchanged(self) -> None:
        from typing import Union

        combo: type = Union[_Dep, _DepB, None]  # noqa: UP007
        inj, _ = _injector({})
        assert inj._unwrap_optional(combo) is combo  # noqa: SLF001
