"""Feature tour: dependency injection with real lifetimes.

One container, three lifetimes — `singleton`, `transient`, `scoped` —
registered with a single call each. Classes marked `@inject` auto-wire:
constructor-annotated dependencies resolve recursively, no decorators on
parameters, no factories to write. Request-scoped work lives in an
explicit scope that caches within itself and isolates across itself.
"""

import asyncio

from quadkit import Container, inject


class Settings:
    """Application configuration — one instance for the app lifetime."""


class Cache:
    """Cheap, stateless — a fresh instance per consumer is fine."""


@inject
class Repo:
    """Auto-wired: the container reads the constructor annotation."""

    def __init__(self, cache: Cache) -> None:
        self.cache = cache


class UnitOfWork:
    """Per-request work — shared within a scope, isolated across scopes."""


def _build_uow() -> UnitOfWork:
    return UnitOfWork()


def test_singleton_transient_and_ctor_injection() -> None:
    async def run() -> None:
        container = Container()
        container.singleton(Settings)
        container.transient(Cache, Cache)

        settings_a = await container.resolve(Settings)
        settings_b = await container.resolve(Settings)
        assert settings_a is settings_b              # singleton identity

        repo_a = await container.resolve(Repo)
        repo_b = await container.resolve(Repo)
        assert repo_a is not repo_b                  # transient identity
        assert repo_a.cache is not repo_b.cache      # nested too
        assert isinstance(repo_a.cache, Cache)       # constructor wiring

    asyncio.run(run())


def test_scoped_lifetime_honors_scope_boundaries() -> None:
    async def run() -> None:
        container = Container()
        container.scoped(UnitOfWork, _build_uow)

        async with container.create_scope() as scope_one:
            first = await scope_one.resolve(UnitOfWork)
            second = await scope_one.resolve(UnitOfWork)
            assert first is second                   # cached within the scope

        async with container.create_scope() as scope_two:
            third = await scope_two.resolve(UnitOfWork)
            assert third is not first                # isolated across scopes

    asyncio.run(run())


def test_concurrent_scoped_resolve_yields_one_instance() -> None:
    """Slow factories can't double-create under concurrent resolution."""
    created = 0

    async def slow_factory() -> UnitOfWork:
        nonlocal created
        created += 1
        await asyncio.sleep(0)                      # yield, let others race
        return UnitOfWork()

    async def run() -> None:
        container = Container()
        container.scoped(UnitOfWork, slow_factory)
        async with container.create_scope() as scope:
            a, b = await asyncio.gather(
                scope.resolve(UnitOfWork), scope.resolve(UnitOfWork)
            )
            assert a is b
            assert created == 1

    asyncio.run(run())
