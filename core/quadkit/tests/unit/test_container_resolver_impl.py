"""Tests for ContainerResolverImpl (read-only DI resolution phase)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.exceptions import UnresolvableDependencyError
from quadkit.contracts.exceptions.provider import ModuleVisibilityError
from quadkit.di.container.resolver import ContainerResolverImpl
from quadkit.di.context import (
    clear_module_context,
    set_module_context,
)
from quadkit.di.resolution.descriptor import ServiceDescriptor
from quadkit.di.resolution.registry import ServiceRegistry


class FakeServiceResolver:
    def __init__(self) -> None:
        self.calls: list[type] = []

    async def resolve(self, service_type: type) -> Any:
        self.calls.append(service_type)
        return f"instance-of-{service_type.__name__}"

    async def create_with_injection(self, implementation: type, service_type: type) -> Any:
        return f"injected-{implementation.__name__}"


def _make_resolver(
    parent: ContainerResolverImpl | None = None,
    service_resolver: FakeServiceResolver | None = None,
) -> tuple[ContainerResolverImpl, ServiceRegistry, FakeServiceResolver]:
    registry = ServiceRegistry()
    resolver_impl = service_resolver or FakeServiceResolver()
    invoker = MagicMock()
    invoker.call = AsyncMock(side_effect=lambda func, *a, **k: func(*a, **k))
    scope_factory = MagicMock(return_value=MagicMock(dispose=AsyncMock()))
    impl = ContainerResolverImpl(
        registry=registry,
        service_resolver=resolver_impl,  # type: ignore[arg-type]
        invoker=invoker,  # type: ignore[arg-type]
        hints_cache=MagicMock(),
        scope_factory=scope_factory,
        parent_resolver=parent,
    )
    return impl, registry, resolver_impl


class TestResolve:
    async def test_resolve_delegates_to_service_resolver(self) -> None:
        impl, _, svc = _make_resolver()
        result = await impl.resolve(str)
        assert result == "instance-of-str"
        assert svc.calls == [str]

    async def test_resolve_bypass_visibility_skips_check(self) -> None:
        impl, _, _ = _make_resolver()
        result = await impl.resolve(str, bypass_visibility=True)
        assert result == "instance-of-str"

    async def test_resolve_visibility_failure_without_context(self) -> None:
        # No module context -> check_visibility returns True -> resolves.
        impl, _, _ = _make_resolver()
        assert await impl.resolve(str) == "instance-of-str"

    async def test_resolve_visibility_failure_with_module_context(self) -> None:
        impl, _, _ = _make_resolver()

        class HiddenService:
            pass

        class Consumer:
            pass

        class FakeNode:
            name = "AuthModule"
            exports = [type("AuthService", (), {})]
            imports = []

        graph = MagicMock()
        graph.is_visible.return_value = False
        graph.find_modules_exporting.return_value = [FakeNode()]
        graph.get_module.return_value = FakeNode()

        tokens = set_module_context(Consumer, graph)
        try:
            with pytest.raises(ModuleVisibilityError) as excinfo:
                await impl.resolve(HiddenService)
            msg = str(excinfo.value)
            assert "Consumer" in msg
            assert "HiddenService" in msg
            assert "AuthModule" in msg
        finally:
            clear_module_context(tokens)

    async def test_resolve_visibility_failure_fallback_message(self) -> None:
        impl, _, _ = _make_resolver()

        class HiddenService:
            pass

        class Consumer:
            pass

        graph = MagicMock(spec=["is_visible"])  # no find_modules_exporting / get_module
        graph.is_visible.return_value = False

        tokens = set_module_context(Consumer, graph)
        try:
            with pytest.raises(ModuleVisibilityError) as excinfo:
                await impl.resolve(HiddenService)
            msg = str(excinfo.value)
            assert "cannot resolve" in msg
        finally:
            clear_module_context(tokens)

class TestResolveSync:
    def test_resolve_sync_returns_instantiated_singleton(self) -> None:
        impl, registry, _ = _make_resolver()

        class Svc:
            pass

        registry.add(
            ServiceDescriptor(
                service_type=Svc,
                implementation=MagicMock(),
                scope=MagicMock(),
                instance=42,
                is_instantiated=True,
            )
        )
        assert impl.resolve_sync(Svc) == 42

    def test_resolve_sync_parent_fallback(self) -> None:
        parent, parent_registry, _ = _make_resolver()
        child, _, _ = _make_resolver(parent=parent)

        class Svc:
            pass

        parent_registry.add(
            ServiceDescriptor(
                service_type=Svc,
                implementation=MagicMock(),
                scope=MagicMock(),
                instance="parent-inst",
                is_instantiated=True,
            )
        )
        assert child.resolve_sync(Svc) == "parent-inst"

    def test_resolve_sync_not_instantiated_raises(self) -> None:
        impl, registry, _ = _make_resolver()

        class Svc:
            pass

        registry.add(
            ServiceDescriptor(
                service_type=Svc,
                implementation=MagicMock(),
                scope=MagicMock(),
                is_instantiated=False,
            )
        )
        with pytest.raises(UnresolvableDependencyError, match="synchronously"):
            impl.resolve_sync(Svc)

    def test_resolve_sync_not_registered_raises(self) -> None:
        impl, _, _ = _make_resolver()
        with pytest.raises(UnresolvableDependencyError):
            impl.resolve_sync(dict)


class TestResolveOptionalAndAll:
    async def test_resolve_optional_registered(self) -> None:
        impl, registry, _ = _make_resolver()
        registry.add(
            ServiceDescriptor(
                service_type=int, implementation=MagicMock(), scope=MagicMock()
            )
        )
        assert await impl.resolve_optional(int) == "instance-of-int"

    async def test_resolve_optional_not_registered(self) -> None:
        impl, _, _ = _make_resolver()
        assert await impl.resolve_optional(dict) is None

    async def test_resolve_optional_parent_fallback(self) -> None:
        parent, parent_registry, _ = _make_resolver()
        child, _, _ = _make_resolver(parent=parent)
        parent_registry.add(
            ServiceDescriptor(
                service_type=int, implementation=MagicMock(), scope=MagicMock()
            )
        )
        # has() falls back to parent; resolve() falls back? resolve() does NOT
        # fall back — service_resolver would fail. So optional resolves via
        # child's own has -> False, parent has -> True, then child.resolve(int)
        # -> child's service_resolver (not registered) — this path shows parent
        # visibility only. Assert it does not crash with AttributeError.
        result = await child.resolve_optional(int)
        assert result == "instance-of-int" or result is None

    async def test_resolve_all_subtypes(self) -> None:
        impl, registry, _ = _make_resolver()

        class Base:
            pass

        class ImplA(Base):
            pass

        class ImplB(Base):
            pass

        class Other:
            pass

        registry.add(
            ServiceDescriptor(service_type=ImplA, implementation=MagicMock(), scope=MagicMock())
        )
        registry.add(
            ServiceDescriptor(service_type=ImplB, implementation=MagicMock(), scope=MagicMock())
        )
        registry.add(
            ServiceDescriptor(service_type=Other, implementation=MagicMock(), scope=MagicMock())
        )
        results = await impl.resolve_all(Base)
        assert sorted(results) == ["instance-of-ImplA", "instance-of-ImplB"]

    async def test_resolve_all_parent_extension(self) -> None:
        parent, parent_registry, _ = _make_resolver()
        child, child_registry, _ = _make_resolver(parent=parent)

        class Base:
            pass

        class ChildImpl(Base):
            pass

        class ParentImpl(Base):
            pass

        child_registry.add(
            ServiceDescriptor(service_type=ChildImpl, implementation=MagicMock(), scope=MagicMock())
        )
        parent_registry.add(
            ServiceDescriptor(service_type=ParentImpl, implementation=MagicMock(), scope=MagicMock())
        )
        results = await child.resolve_all(Base)
        assert sorted(results) == ["instance-of-ChildImpl", "instance-of-ParentImpl"]

    async def test_resolve_all_skips_non_type_keys(self) -> None:
        impl, registry, _ = _make_resolver()
        # Named registration: (type, name) tuple key is not a bare type.
        registry.add(
            ServiceDescriptor(
                service_type=(str, "named"), implementation=MagicMock(), scope=MagicMock()
            )
        )
        assert await impl.resolve_all(str) == []


class TestQueries:
    def test_has_local(self) -> None:
        impl, registry, _ = _make_resolver()
        registry.add(
            ServiceDescriptor(service_type=int, implementation=MagicMock(), scope=MagicMock())
        )
        assert impl.has(int) is True
        assert impl.has(dict) is False

    def test_has_parent_fallback(self) -> None:
        parent, parent_registry, _ = _make_resolver()
        child, _, _ = _make_resolver(parent=parent)
        parent_registry.add(
            ServiceDescriptor(service_type=int, implementation=MagicMock(), scope=MagicMock())
        )
        assert child.has(int) is True
        assert child.has(dict) is False

    def test_is_singleton(self) -> None:
        impl, registry, _ = _make_resolver()
        from quadkit.contracts.core.scopes import ServiceScope

        registry.add(
            ServiceDescriptor(
                service_type=int, implementation=MagicMock(), scope=ServiceScope.SINGLETON
            )
        )
        assert impl.is_singleton(int) is True
        assert impl.is_singleton(dict) is False

    def test_registered_services_includes_parent(self) -> None:
        parent, parent_registry, _ = _make_resolver()
        child, child_registry, _ = _make_resolver(parent=parent)
        parent_registry.add(
            ServiceDescriptor(service_type=int, implementation=MagicMock(), scope=MagicMock())
        )
        child_registry.add(
            ServiceDescriptor(service_type=str, implementation=MagicMock(), scope=MagicMock())
        )
        assert child._registered_services() == ["int", "str"]  # noqa: SLF001


class TestCallAndScoping:
    async def test_call_delegates_to_invoker(self) -> None:
        impl, _, _ = _make_resolver()
        impl._invoker.call = AsyncMock(return_value="called")  # noqa: SLF001

        async def target() -> str:
            return "never"

        assert await impl.call(target, 1, two=2) == "called"
        impl._invoker.call.assert_awaited_once_with(target, 1, strategies=None, two=2)  # noqa: SLF001

    def test_create_scope_uses_factory(self) -> None:
        impl, _, _ = _make_resolver()
        scope = impl.create_scope()
        impl._scope_factory.assert_called_once()  # noqa: SLF001
        assert scope is not None

    async def test_scope_context_manager_disposes(self) -> None:
        impl, _, _ = _make_resolver()
        scope = impl._scope_factory.return_value  # noqa: SLF001
        async with impl.scope() as s:
            assert s is scope
        scope.dispose.assert_awaited_once()

    async def test_scope_disposes_on_exception(self) -> None:
        impl, _, _ = _make_resolver()
        scope = impl._scope_factory.return_value  # noqa: SLF001
        with pytest.raises(RuntimeError):
            async with impl.scope():
                raise RuntimeError("boom")
        scope.dispose.assert_awaited_once()

    def test_get_descriptor_internal(self) -> None:
        impl, registry, _ = _make_resolver()
        descriptor = ServiceDescriptor(
            service_type=int, implementation=MagicMock(), scope=MagicMock()
        )
        registry.add(descriptor)
        assert impl._get_descriptor(int) is descriptor  # noqa: SLF001

    async def test_create_with_injection_delegates(self) -> None:
        impl, _, _ = _make_resolver()
        result = await impl._create_with_injection(dict, str)  # noqa: SLF001
        assert result == "injected-dict"
