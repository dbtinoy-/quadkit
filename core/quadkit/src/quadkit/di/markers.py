"""Dependency injection markers and metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Inject:
    """Marker for named dependency injection.

    Can be used with Annotated to specify a specific service name.

    Example:
        def __init__(self, db: Annotated[DatabaseService, Inject("main-db")]):
            ...
    """

    name: str | None = None
    default: Any = None


@dataclass(frozen=True)
class OptionalDep:
    """Marker for optional dependency injection.

    Indicates that a dependency is optional and may be None if not available.

    Example:
        def __init__(self, cache: Annotated[CacheService | None, OptionalDep()]):
            ...
    """

    default: Any = None


@dataclass(frozen=True)
class Named:
    """Marker for named service injection.

    Specifies a particular named instance of a service type.

    Example:
        def __init__(self, primary_db: Annotated[Database, Named("primary")]):
            ...
    """

    name: str


def named(name: str) -> Named:
    """Create a named DI sentinel for constructor defaults.

    Example:
        class Service:
            def __init__(self, cache: CacheBackend = named("primary")) -> None:
                self.cache = cache
    """

    return Named(name)


@dataclass(frozen=True)
class Qualifier:
    """Marker for qualifier-based injection.

    Used to disambiguate multiple implementations of the same interface.

    Example:
        def __init__(self, handler: Annotated[Handler, Qualifier("pdf")]):
            ...
    """

    value: str


__all__ = ["Inject", "Named", "OptionalDep", "Qualifier", "named"]
