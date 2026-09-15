"""Registry protocol for the Quadkit Framework.

The concrete implementation lives in ``quadkit.core.registry``.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol, TypeVar, runtime_checkable

K = TypeVar("K")
V = TypeVar("V")


@runtime_checkable
class RegistryProtocol(Protocol[K, V]):
    """Structural protocol for registry-like containers.

    Any class that exposes the core registry interface (register, get,
    resolve, has, unregister, keys, clear) satisfies this protocol without
    explicit inheritance.
    """

    def register(
        self,
        key: K,
        value: V | None = None,
        *,
        allow_overwrite: bool | None = None,
    ) -> Any:
        """Register an item or use as a decorator."""
        ...

    def get(self, key: K, default: V | None = None) -> V | None:
        """Retrieve an item by key, returning *default* if absent."""
        ...

    def resolve(self, key: K) -> V:
        """Resolve an item, raising ``RegistryKeyError`` if not found."""
        ...

    def has(self, key: K) -> bool:
        """Return ``True`` if *key* is registered."""
        ...

    def unregister(self, key: K) -> V | None:
        """Remove and return the item registered under *key*."""
        ...

    def keys(self) -> Iterable[K]:
        """Return all registered keys."""
        ...

    def values(self) -> Iterable[V]:
        """Return all registered values."""
        ...

    def items(self) -> Iterable[tuple[K, V]]:
        """Return all registered key-value pairs."""
        ...

    def all_keys(self) -> set[K]:
        """Return all keys, including those with pending factories."""
        ...

    def clear(self) -> None:
        """Remove all registered items and factories."""
        ...


@runtime_checkable
class BackendRegistryProtocol(Protocol[V]):
    """Structural protocol for factory-chain backend registries.

    A backend registry holds factory classes each capable of answering
    ``can_create(config)`` and constructing an instance.  The first matching
    factory is selected at runtime.

    Example::

        class CacheBackendRegistry(BackendRegistryProtocol[CacheBackendProtocol]):
            def select(self, config: dict) -> CacheBackendProtocol: ...
    """

    def select(self, config: dict[str, Any]) -> V:
        """Return the first backend whose ``can_create`` accepts *config*.

        Args:
            config: Backend configuration dictionary.

        Returns:
            A backend instance matching the config.

        Raises:
            ValueError: When no registered backend can handle *config*.
        """
        ...

    def register_backend(self, key: str, backend_cls: type[V]) -> None:
        """Register a backend factory class under *key*.

        Args:
            key: Unique backend identifier.
            backend_cls: Backend class implementing the backend protocol.
        """
        ...


@runtime_checkable
class StrategyRegistryProtocol(Protocol[K, V]):  # type: ignore[misc]
    """Structural protocol for pluggable strategy registries.

    A strategy registry maps named keys to algorithm implementations and
    instantiates them on demand.

    Example::

        class ChunkingStrategyRegistry(
            StrategyRegistryProtocol[str, ChunkerProtocol]
        ):
            def instantiate(self, key: str, **kwargs) -> ChunkerProtocol: ...
    """

    def register_strategy(self, key: K, strategy_cls: type[V]) -> None:
        """Register a strategy class.

        Args:
            key: Strategy name or enum key.
            strategy_cls: Class implementing the strategy protocol.
        """
        ...

    def instantiate(self, key: K, **kwargs: Any) -> V:
        """Instantiate and return a strategy for *key*.

        Args:
            key: Strategy identifier.
            **kwargs: Constructor arguments forwarded to the strategy class.

        Returns:
            An instance of the strategy.

        Raises:
            RegistryKeyError: When *key* is not registered.
        """
        ...


__all__ = [
    "BackendRegistryProtocol",
    "RegistryProtocol",
    "StrategyRegistryProtocol",
]
