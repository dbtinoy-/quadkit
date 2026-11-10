"""Nested constructor injection belongs to the request scope, not root DI."""

import asyncio
from typing import Annotated

import pytest

from quadkit.contracts.exceptions import CircularDependencyError
from quadkit.contracts.exceptions.container import ScopedResolutionError
from quadkit.di.container import Container
from quadkit.di.markers import Named
from quadkit.di.resolution.resolver import ServiceResolver


class Session:
    def __init__(self):
        self.closed = False

    async def aclose(self):
        self.closed = True


class Repository:
    def __init__(self, session: Session):
        self.session = session


class Controller:
    def __init__(self, repository: Repository):
        self.repository = repository


class CycleA:
    def __init__(self, other: "CycleB"):
        self.other = other


class CycleB:
    def __init__(self, other: CycleA):
        self.other = other


@pytest.mark.parametrize("transient", [False, True])
async def test_nested_constructor_uses_active_scope_and_disposes_dependency(transient):
    container = Container()
    container.scoped(Session, Session)
    container.scoped(Repository, Repository)
    (container.transient if transient else container.scoped)(Controller, Controller)
    async with container.create_scope() as scope:
        first, second = await asyncio.gather(
            scope.resolve(Controller), scope.resolve(Controller)
        )
        assert (first is second) is not transient
        session = await scope.resolve(Session)
        assert first.repository.session is second.repository.session is session
        assert not session.closed
    assert session.closed
    assert not scope._cache
    async with container.create_scope() as next_scope:
        other = await next_scope.resolve(Controller)
        assert other.repository.session is not session


async def test_sibling_scopes_do_not_replace_root_or_each_other_injector():
    container = Container()
    container.scoped(Session, Session)
    container.scoped(Repository, Repository)
    container.scoped(Controller, Controller)
    async with container.create_scope() as first, container.create_scope() as second:
        a, b = await asyncio.gather(
            first.resolve(Controller), second.resolve(Controller)
        )
        assert a is not b
        assert a.repository is not b.repository
        assert a.repository.session is not b.repository.session
        with pytest.raises(ScopedResolutionError, match="outside of an active scope"):
            await container.resolve(Session)


@pytest.mark.parametrize("transient", [False, True])
async def test_scoped_constructor_cycle_fails_before_waiting_on_own_inflight(transient):
    container = Container()
    register = container.transient if transient else container.scoped
    register(CycleA, CycleA, validate=False)
    register(CycleB, CycleB, validate=False)
    async with container.create_scope() as scope:
        with pytest.raises(CircularDependencyError, match=r"CycleA.*CycleB.*CycleA"):
            async with asyncio.timeout(2):
                await scope.resolve(CycleA)
        assert not scope._inflight
        assert not scope._construction_path.get()


async def test_scope_constructor_depth_limit_and_path_reset(monkeypatch):
    container = Container()
    container.scoped(Session, Session)
    container.scoped(Repository, Repository)
    container.scoped(Controller, Controller)
    monkeypatch.setattr(ServiceResolver, "_max_resolution_depth", 2)
    async with container.create_scope() as scope:
        with pytest.raises(CircularDependencyError, match="depth exceeded 2"):
            await scope.resolve(Controller)
        assert not scope._inflight
        assert not scope._construction_path.get()
        assert not (await scope.resolve(Session)).closed


class QualifiedChain:
    def __init__(self, child: Annotated["QualifiedChain", Named("leaf")]):
        self.child = child


class QualifiedLeaf(QualifiedChain):
    def __init__(self):
        self.child = None


async def test_qualified_constructor_keys_do_not_create_false_cycles():
    container = Container()
    register = container.scoped
    register(QualifiedChain, QualifiedChain, name="head", validate=False)
    register(QualifiedChain, QualifiedLeaf, name="leaf", validate=False)
    async with container.create_scope() as scope:
        # The injector resolves Named annotations using these actual registry keys.
        head = await scope.resolve((QualifiedChain, "head"))
        leaf = await scope.resolve((QualifiedChain, "leaf"))
        assert isinstance(head.child, QualifiedLeaf)
        assert head.child is leaf
        assert not scope._construction_path.get()
        assert not scope._inflight


async def test_qualified_constructor_cycle_cleans_up_and_can_retry():
    container = Container()
    register = container.scoped
    register(QualifiedChain, QualifiedChain, name="head", validate=False)
    register(QualifiedChain, QualifiedChain, name="leaf", validate=False)
    async with container.create_scope() as scope:
        for _ in range(2):
            with pytest.raises(CircularDependencyError, match="leaf"):
                async with asyncio.timeout(2):
                    await scope.resolve((QualifiedChain, "head"))
            assert not scope._construction_path.get()
            assert not scope._inflight
