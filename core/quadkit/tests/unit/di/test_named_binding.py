"""Tests for named singleton registration and named DI resolution."""
from __future__ import annotations

from typing import Annotated

import pytest

from quadkit.di import named
from quadkit.di.container import Container
from quadkit.di.markers import Named


class FakeDb:
    def __init__(self, url: str) -> None:
        self.url = url


class FakeCache:
    def __init__(self, backend: str) -> None:
        self.backend = backend


class ServiceWithNamed:
    def __init__(self, db: Annotated[FakeDb, Named("primary")]) -> None:
        self.db = db


class ServiceWithNamedDefault:
    def __init__(self, cache: FakeCache = named("primary")) -> None:
        self.cache = cache


class ServiceWithMixedNamedBindings:
    def __init__(
        self,
        db: Annotated[FakeDb, Named("primary")],
        cache: FakeCache = named("primary"),
    ) -> None:
        self.db = db
        self.cache = cache


@pytest.mark.asyncio
async def test_named_singleton_registration_and_resolution() -> None:
    """Named singleton registered under string key resolves correctly."""
    container = Container()
    primary = FakeDb("primary://")
    maps = FakeDb("maps://")

    container.singleton(FakeDb, name="primary", instance=primary)
    container.singleton(FakeDb, name="maps", instance=maps)

    resolved = await container.resolve(Annotated[FakeDb, Named("maps")])
    assert resolved.url == "maps://"


@pytest.mark.asyncio
async def test_named_singleton_constructor_injection() -> None:
    """Named dependency injected via Annotated[T, Named()] in constructor."""
    container = Container()
    primary = FakeDb("primary://")
    container.singleton(FakeDb, name="primary", instance=primary)
    container.transient(ServiceWithNamed, ServiceWithNamed)

    service = await container.resolve(ServiceWithNamed)
    assert service.db.url == "primary://"


@pytest.mark.asyncio
async def test_named_default_constructor_injection() -> None:
    """Named dependency injected via named() default sentinel in constructor."""
    container = Container()
    primary = FakeCache("redis")
    container.singleton(FakeCache, name="primary", instance=primary)
    container.transient(ServiceWithNamedDefault, ServiceWithNamedDefault)

    service = await container.resolve(ServiceWithNamedDefault)

    assert service.cache.backend == "redis"


@pytest.mark.asyncio
async def test_named_default_and_annotated_coexist_with_same_binding_name() -> None:
    """Named bindings resolve by type plus name for mixed constructor styles."""
    container = Container()
    primary_db = FakeDb("postgres://primary")
    primary_cache = FakeCache("redis")

    container.singleton(FakeDb, name="primary", instance=primary_db)
    container.singleton(FakeCache, name="primary", instance=primary_cache)
    container.transient(ServiceWithMixedNamedBindings, ServiceWithMixedNamedBindings)

    service = await container.resolve(ServiceWithMixedNamedBindings)

    assert service.db is primary_db
    assert service.cache is primary_cache


@pytest.mark.asyncio
async def test_named_and_unnamed_coexist() -> None:
    """Named registration does not overwrite unnamed registration."""
    container = Container()
    unnamed = FakeDb("unnamed://")
    named = FakeDb("named://")

    container.singleton(FakeDb, instance=unnamed)
    container.singleton(FakeDb, name="secondary", instance=named)

    assert (await container.resolve(FakeDb)).url == "unnamed://"
    assert (await container.resolve(Annotated[FakeDb, Named("secondary")])).url == "named://"


@pytest.mark.asyncio
async def test_named_resolution_missing_raises() -> None:
    """Resolving an unregistered named service raises UnresolvableDependencyError."""
    from quadkit.contracts.exceptions import UnresolvableDependencyError

    container = Container()
    with pytest.raises(UnresolvableDependencyError):
        await container.resolve(Annotated[FakeDb, Named("nonexistent")])
