"""DI Container: scoping, parent chains, strict mode, freeze, invoker."""

from __future__ import annotations

import pytest

from quadkit.contracts.exceptions import UnresolvableDependencyError
from quadkit.contracts.exceptions.container import (
    ContainerError,
    ContainerValidationError,
)
from quadkit.di.container.container import Container


class Repo:
    def __init__(self) -> None:
        self.id = object()


class Service:
    def __init__(self, repo: Repo) -> None:
        self.repo = repo


class A:
    pass


class A1(A):
    pass


class A2(A):
    pass


class TestBasics:
    def test_singleton_instance_identity(self) -> None:
        c = Container()
        c.singleton(Repo, Repo())
        assert c.resolve_sync(Repo) is c.resolve_sync(Repo)
        assert c.is_singleton(Repo)
        assert c.has(Repo)

    async def test_singleton_factory_is_lazy(self) -> None:
        built: list[int] = []

        def factory() -> Repo:
            built.append(1)
            return Repo()

        c = Container()
        c.singleton(Repo, factory=factory)
        assert built == []
        first = await c.resolve(Repo)
        second = await c.resolve(Repo)
        assert built == [1]
        assert first is second

    async def test_transient_new_instance_each_resolution(self) -> None:
        c = Container()
        c.transient(Repo, Repo)
        assert not c.is_singleton(Repo)
        assert await c.resolve(Repo) is not await c.resolve(Repo)

    async def test_transient_resolves_dependency_injection(self) -> None:
        c = Container()
        c.singleton(Repo, Repo())
        c.transient(Service, Service)
        svc = await c.resolve(Service)
        assert isinstance(svc, Service)
        assert svc.repo is c.resolve_sync(Repo)

    async def test_scoped_shares_within_scope(self) -> None:
        c = Container()
        c.scoped(Repo, Repo)
        async with c.create_scope() as s1:
            r1 = await s1.resolve(Repo)
            r2 = await s1.resolve(Repo)
            assert r1 is r2
        async with c.create_scope() as s2:
            r3 = await s2.resolve(Repo)
            assert r3 is not r1


class TestParentChain:
    def test_has_and_resolve_fall_through_parent(self) -> None:
        parent = Container()
        parent.singleton(Repo, Repo())
        child = Container(parent=parent)

        assert not child.has(Service)
        assert child.has(Repo)
        assert child.resolve_sync(Repo) is parent.resolve_sync(Repo)

    async def test_child_shadows_parent(self) -> None:
        parent = Container()
        parent.singleton(Repo, Repo())
        child = Container(parent=parent)
        child.singleton(Repo, Repo())
        assert child.resolve_sync(Repo) is not parent.resolve_sync(Repo)

    async def test_resolve_all_includes_parent(self) -> None:
        parent = Container()
        parent.singleton(A1, A1)
        child = Container(parent=parent)
        child.singleton(A2, A2)

        all_from_child = await child.resolve_all(A)
        assert len(all_from_child) == 2

        all_from_parent = await parent.resolve_all(A)
        assert len(all_from_parent) == 1

    def test_has_returns_false_when_unregistered(self) -> None:
        assert not Container().has(Service)


class TestResolveOptional:
    async def test_returns_none_when_unregistered(self) -> None:
        c = Container()
        assert await c.resolve_optional(Service) is None

    async def test_resolves_when_registered(self) -> None:
        c = Container()
        c.singleton(Repo, Repo())
        assert await c.resolve_optional(Repo) is c.resolve_sync(Repo)

    async def test_strict_mode_raises(self) -> None:
        c = Container(strict_mode=True)
        with pytest.raises(UnresolvableDependencyError, match="strict_mode"):
            await c.resolve_optional(Service)

    async def test_strict_mode_still_resolves_registered(self) -> None:
        c = Container(strict_mode=True)
        c.singleton(Repo, Repo())
        assert await c.resolve_optional(Repo) is not None


class TestResolveSync:
    def test_factory_singleton_not_sync_resolvable(self) -> None:
        # factory singletons are not instantiated yet — async resolve required
        c = Container()

        def _factory() -> Repo:
            return Repo()

        c.singleton(Repo, factory=_factory)
        with pytest.raises(
            UnresolvableDependencyError, match="not an instantiated singleton"
        ):
            c.resolve_sync(Repo)

    def test_transient_unsupported(self) -> None:
        c = Container()
        c.transient(Repo, Repo)
        with pytest.raises(UnresolvableDependencyError):
            c.resolve_sync(Repo)

    def test_unregistered_raises(self) -> None:
        with pytest.raises(UnresolvableDependencyError):
            Container().resolve_sync(Service)

    def test_parent_chain(self) -> None:
        parent = Container()
        parent.singleton(Repo, Repo())
        child = Container(parent=parent)
        assert child.resolve_sync(Repo) is parent.resolve_sync(Repo)


class TestFreezeAndValidate:
    def test_freeze_blocks_registration(self) -> None:
        c = Container()
        c.singleton(Repo, Repo())
        c.freeze()
        assert c.is_frozen
        with pytest.raises(ContainerError, match="frozen"):
            c.transient(Service, Service)
        with pytest.raises(ContainerError, match="frozen"):
            c.clear()

    def test_frozen_still_resolves(self) -> None:
        c = Container()
        c.singleton(Repo, Repo())
        c.freeze()
        assert c.resolve_sync(Repo) is c.resolve_sync(Repo)

    def test_validate_clean_container(self) -> None:
        c = Container()
        c.singleton(Repo, Repo())
        c.freeze(validate=True)
        assert c.validate() == []

    def test_scope_violation_detected_on_freeze(self) -> None:
        c = Container()
        c.transient(Repo, Repo)
        c.singleton(Service, factory=Service)  # singleton -> transient dep
        with pytest.raises(ContainerValidationError):
            c.freeze(validate=True)
        issues = c.validate()
        assert any("Scope violation" in i for i in issues)

    def test_freeze_skip_validation(self) -> None:
        c = Container()
        c.transient(Repo, Repo)
        c.singleton(Service, factory=Service)
        c.freeze(validate=False)  # must not raise
        assert c.is_frozen


class TestMisc:
    def test_clear(self) -> None:
        c = Container()
        c.singleton(Repo, Repo())
        c.clear()
        assert not c.has(Repo)

    def test_create_invoker_returns_bound_invoker(self) -> None:
        from quadkit.di.resolution.invoker import FunctionInvoker

        c = Container()
        assert isinstance(c.create_invoker(), FunctionInvoker)

    def test_testing_mode_flag(self) -> None:
        c = Container(testing_mode=True)
        c.singleton(Repo, Repo())
        assert c.resolve_sync(Repo) is c.resolve_sync(Repo)

    async def test_invoker_call_resolves_dependencies(self) -> None:
        c = Container()
        c.singleton(Repo, Repo())
        c.transient(Service, Service)

        invoker = c.create_invoker()

        def make_service(repo: Repo) -> Service:
            return Service(repo)

        svc = await invoker.call(make_service)
        assert isinstance(svc, Service)
        assert svc.repo is c.resolve_sync(Repo)
