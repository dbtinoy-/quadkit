"""Unified Registry foundation for Quadkit Framework.

Providing a standardized way to manage collections of components,
services, or metadata with type safety and validation.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from threading import Lock
from typing import Any, Generic, Self, TypeVar, overload

from quadkit.contracts.exceptions.infra import (
    RegistryAlreadyExistsError,
    RegistryKeyError,
)
from quadkit.logging import get_logger

K = TypeVar("K")
V = TypeVar("V")
T = TypeVar("T")

logger = get_logger(__name__)


class Registry(Generic[K, V]):
    """Unified Registry for managing collections.

    Features:
    - Generic type support
    - Factory/lazy registration
    - Lifecycle hooks (on_register, on_unregister)
    - Decorator support
    - Thread-safe (using internally managed lock)
    - Iteration support
    - Priority ordering support

    Registration Patterns
    ---------------------
    The Registry supports three distinct registration patterns.  Choose the
    one that best fits your use-case:

    **1. Direct registration** — use when the value already exists::

        registry.register("my_handler", MyHandler())

    **2. Factory (lazy) registration** — use when construction is expensive
    or must be deferred until the first lookup::

        registry.register_factory("my_handler", lambda: MyHandler())

    The factory is called once on the first ``get()`` / ``resolve()`` and the
    result is cached.  Subsequent lookups return the cached instance.

    **3. Decorator registration** — syntactic sugar for direct registration,
    useful when defining a class or function inline::

        @registry.register("my_handler")
        class MyHandler:
            ...

    Calling ``registry.register(key)`` with only the key (no value) activates
    decorator mode, so the decorated object is registered under *key* and
    returned unchanged (enabling chaining with other decorators).

    For most framework-internal use adopt the **decorator pattern** when
    registering at module load time and the **factory pattern** when
    registration must be deferred or is conditional on runtime configuration.

    Construction
    ------------
    A registry instance is **always empty** — ``__init__`` never registers
    anything.  There are exactly two ways to obtain a populated instance:

    **1. Explicit population (plugin/contributor registries)** — entries are
    supplied by outside code through ``register()`` / ``register_many()``::

        registry = MyPluginRegistry()
        registry.register_many(discover_plugins())  # entry points, loaders

    **2. ``with_defaults()`` (in-package built-in registries)** — when every
    entry is a *complete, static set shipped by the same package*::

        registry = MyBuiltinRegistry.with_defaults()

    Both idioms are interpreted as a single rule: ``with_defaults()`` returns
    exactly the complete in-package built-in set declared by
    :meth:`_default_entries`, while plugin registries declare no built-in set
    and are populated by their loader.  Calling ``with_defaults()`` on a
    registry without a built-in set raises ``NotImplementedError`` rather
    than silently returning a partial registry.
    """

    def __init__(
        self,
        name: str | None = None,
        *,
        allow_overwrite: bool = False,
        priority_key: Callable[[V], int] | None = None,
    ) -> None:
        self._name = name or self.__class__.__name__
        self._items: dict[K, V] = {}
        self._factories: dict[K, Callable[[], V]] = {}
        self._allow_overwrite = allow_overwrite
        self._priority_key = priority_key
        self._lock = Lock()
        self._frozen = False
        self._on_register_hooks: list[Callable[[K, V | Callable[[], V]], None]] = []
        self._on_unregister_hooks: list[Callable[[K, V | Callable[[], V]], None]] = []

        # Auto-discover hooks defined as methods (from patterns/registry logic)
        for attr_name in dir(self):
            method = getattr(self, attr_name)
            if getattr(method, "__is_register_hook__", False):
                self._on_register_hooks.append(method)
            if getattr(method, "__is_unregister_hook__", False):
                self._on_unregister_hooks.append(method)

    @classmethod
    def with_defaults(cls) -> Self:
        """Create a registry pre-populated with the class's built-in set.

        Returns exactly what :meth:`_default_entries` declares.  Registries
        whose entries are contributed externally (plugins, entry points) do
        not override :meth:`_default_entries`; calling ``with_defaults()`` on
        them raises ``NotImplementedError`` so the registry is never silently
        partial — populate those explicitly with ``register()``.

        Returns:
            A new, empty-at-init registry containing every declared default.

        Raises:
            NotImplementedError: When the class declares no built-in set.
        """
        registry = cls()
        for key, value in cls._default_entries().items():
            registry.register(key, value)
        return registry

    @classmethod
    def _default_entries(cls) -> dict[K, V]:
        """Declare the complete in-package built-in set.

        Subclasses with a static built-in set override this and return every
        entry the package ships for this registry.  Import built-ins lazily
        inside the method to avoid import cycles.

        Raises:
            NotImplementedError: Base implementation — override to declare
                defaults.
        """
        msg = (
            f"{cls.__name__} does not declare a built-in default set; "
            "populate it explicitly via register()/register_many()."
        )
        raise NotImplementedError(msg)

    @property
    def name(self) -> str:
        """Registry name for identification."""
        return self._name

    @property
    def allow_overwrite(self) -> bool:
        """Whether overwriting existing keys is allowed."""
        return self._allow_overwrite

    def freeze(self) -> None:
        """Prevent further registrations after application boot.

        Once frozen, calls to ``register``, ``register_factory``,
        ``unregister``, and ``clear`` will raise ``RegistryAlreadyExistsError``.
        Read operations (``get``, ``resolve``, ``has``, etc.) are unaffected.

        Call this from ``Provider.boot()`` or ``Application.boot()`` after
        all providers have completed their ``register()`` phase.
        """
        with self._lock:
            self._frozen = True

    @property
    def is_frozen(self) -> bool:
        """Return whether this registry has been frozen."""
        with self._lock:
            return self._frozen

    @overload
    def register(
        self,
        key: K,
        value: V,
        *,
        allow_overwrite: bool | None = None,
    ) -> V: ...

    @overload
    def register(
        self,
        key: K,
        value: None = None,
        *,
        allow_overwrite: bool | None = None,
    ) -> Callable[[V], V]: ...

    def register(
        self,
        key: K,
        value: V | None = None,
        *,
        allow_overwrite: bool | None = None,
    ) -> V | Callable[[V], V] | None:
        """Register an item with the given key or use as decorator."""
        if value is None:
            return self.register_decorator(key, allow_overwrite=allow_overwrite)

        overwrite = (
            allow_overwrite if allow_overwrite is not None else self._allow_overwrite
        )

        with self._lock:
            if self._frozen:
                raise RegistryAlreadyExistsError(
                    f"Registry '{self._name}' is frozen — no further "
                    "registrations allowed.",
                )
            if not overwrite and (key in self._items or key in self._factories):
                raise RegistryAlreadyExistsError(
                    f"Item with key '{key}' already registered in {self._name}",
                )

            self._validate(key, value)
            self._items[key] = value
            # An overwriting item registration must displace any pending
            # factory for the same key — otherwise the zombie factory
            # re-runs on the next get() and clobbers the explicit value.
            self._factories.pop(key, None)
            self._trigger_on_register(key, value)
            return value

    def register_factory(
        self,
        key: K,
        factory: Callable[[], V],
        *,
        allow_overwrite: bool | None = None,
    ) -> None:
        """Register a factory function for lazy instantiation."""
        overwrite = (
            allow_overwrite if allow_overwrite is not None else self._allow_overwrite
        )

        with self._lock:
            if self._frozen:
                raise RegistryAlreadyExistsError(
                    f"Registry '{self._name}' is frozen — no further "
                    "registrations allowed.",
                )
            if not overwrite and (key in self._factories or key in self._items):
                raise RegistryAlreadyExistsError(
                    f"Factory with key '{key}' already registered in {self._name}",
                )

            # Symmetric with register(): an overwriting factory displaces a
            # pending item so lookups resolve exactly one definition.
            self._items.pop(key, None)
            self._factories[key] = factory
            self._trigger_on_register(key, factory)

    def register_many(self, entries: Iterable[tuple[K, V]]) -> None:
        """Register multiple ``(key, value)`` pairs in one call.

        Use for plugin/contributor population: loaders collect entries
        outside the registry and hand them over in bulk.  Duplicate keys
        follow the same rules as :meth:`register` (raises unless
        ``allow_overwrite``).

        Args:
            entries: Iterable of ``(key, value)`` pairs.
        """
        for key, value in entries:
            self.register(key, value)

    def unregister(self, key: K) -> V | None:
        """Unregister and return an item."""
        with self._lock:
            if self._frozen:
                raise RegistryAlreadyExistsError(
                    f"Registry '{self._name}' is frozen — cannot unregister.",
                )
            if key in self._items:
                value = self._items.pop(key)
                self._trigger_on_unregister(key, value)
                return value
            if key in self._factories:
                factory = self._factories.pop(key)
                self._trigger_on_unregister(key, factory)
                return None
            return None

    @overload
    def get(self, key: K) -> V | None: ...
    @overload
    def get(self, key: K, default: V) -> V: ...

    def get(self, key: K, default: V | None = None) -> V | None:
        """Retrieve an item by key."""
        with self._lock:
            # Try factory first
            if key in self._factories:
                factory = self._factories[key]
                value = factory()
                self._items[key] = value  # Cache it
                del self._factories[key]
                self._trigger_on_register(key, value)
                return value

            return self._items.get(key, default)

    def resolve(self, key: K) -> V:
        """Resolve an item, raising if not found."""
        with self._lock:
            # Check items first
            if key in self._items:
                return self._items[key]

            # Try factory
            if key in self._factories:
                factory = self._factories[key]
                value = factory()
                self._items[key] = value
                del self._factories[key]
                self._trigger_on_register(key, value)
                return value

            raise RegistryKeyError(f"Key '{key}' not found in {self._name}")

    def get_or_raise(self, key: K) -> V:
        """Alias for resolve."""
        return self.resolve(key)

    def has(self, key: K) -> bool:
        """Check if key is registered (item or factory)."""
        with self._lock:
            return key in self._items or key in self._factories

    def keys(self) -> Iterable[K]:
        """Return all registered keys (items only)."""
        with self._lock:
            return list(self._items.keys())

    def values(self) -> Iterable[V]:
        """Return all registered values."""
        with self._lock:
            return list(self._items.values())

    def values_ordered(self) -> list[V]:
        """Return all registered values sorted by priority.

        If a priority_key was provided during initialization, values are
        sorted by that key in ascending order (lower values first).
        Otherwise, returns values in insertion order.

        Returns:
            List of values sorted by priority, or insertion order if no
            priority_key is configured.
        """
        with self._lock:
            values_list = list(self._items.values())
            if self._priority_key is not None:
                values_list.sort(key=self._priority_key)
            return values_list

    def items(self) -> Iterable[tuple[K, V]]:
        """Return all registered items."""
        with self._lock:
            return list(self._items.items())

    def factories(self) -> Iterable[K]:
        """Return keys with registered factories."""
        with self._lock:
            return list(self._factories.keys())

    def all_keys(self) -> set[K]:
        """Return all keys (items + factories)."""
        with self._lock:
            return set(self._items.keys()) | set(self._factories.keys())

    def clear(self) -> None:
        """Clear all registered items and factories."""
        with self._lock:
            if self._frozen:
                raise RegistryAlreadyExistsError(
                    f"Registry '{self._name}' is frozen — cannot clear.",
                )
            for key in list(self._items.keys()):
                value = self._items.pop(key)
                self._trigger_on_unregister(key, value)
            for key in list(self._factories.keys()):
                factory = self._factories.pop(key)
                self._trigger_on_unregister(key, factory)

    def _validate(self, key: K, value: V) -> None:
        """Override for custom validation."""

    def _trigger_on_register(self, key: K, value: V | Callable[[], V]) -> None:
        """Internal trigger for registration hooks."""
        for hook in self._on_register_hooks:
            try:
                hook(key, value)
            except Exception as exc:  # noqa: BLE001 — hook errors must not crash registration
                logger.warning(
                    "registry_hook_error", hook=repr(hook), key=key, error=str(exc)
                )

    def _trigger_on_unregister(self, key: K, value: V | Callable[[], V]) -> None:
        """Internal trigger for unregistration hooks."""
        for hook in self._on_unregister_hooks:
            try:
                hook(key, value)
            except Exception as exc:  # noqa: BLE001 — hook errors must not crash unregistration
                logger.warning(
                    "registry_hook_error", hook=repr(hook), key=key, error=str(exc)
                )

    def register_decorator(
        self,
        key: K | None = None,
        *,
        allow_overwrite: bool | None = None,
    ) -> Callable[[V], V]:
        """Decorator for easy registration."""

        def decorator(value: V) -> V:
            inferred_key: K = key  # type: ignore[assignment]
            if inferred_key is None:
                if hasattr(value, "__name__"):
                    inferred_key = value.__name__
                elif hasattr(value, "name"):
                    inferred_key = str(value.name)  # type: ignore[assignment]
                else:
                    inferred_key = str(value)  # type: ignore[assignment]

            self.register(inferred_key, value, allow_overwrite=allow_overwrite)
            return value

        return decorator

    def __contains__(self, key: K) -> bool:
        return self.has(key)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def __iter__(self) -> Iterator[K]:
        with self._lock:
            return iter(list(self._items.keys()))

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} name={self._name!r} "
            f"items={len(self._items)} factories={len(self._factories)}>"
        )


def on_register(func: Callable[[Any, K, V], None]) -> Callable[[Any, K, V], None]:
    """Mark a method as a registration hook."""
    func.__is_register_hook__ = True  # type: ignore[attr-defined]
    return func


def on_unregister(func: Callable[[Any, K, V], None]) -> Callable[[Any, K, V], None]:
    """Mark a method as an unregistration hook."""
    func.__is_unregister_hook__ = True  # type: ignore[attr-defined]
    return func


class BackendRegistry(Registry[str, Any]):
    """Factory-chain registry for swappable backend selection.

    Holds backend factory classes keyed by string identifiers.  At runtime,
    :meth:`select` iterates registered factories (in priority order) and
    returns the first whose ``can_create(config)`` returns ``True``.

    Use for: cache, storage, database, messaging, monitoring backends.

    Subclass with a concrete protocol to get type-safe registrations::

        class CacheBackendRegistry(BackendRegistry):
            def __init__(self) -> None:
                super().__init__(name="cache.backends")

            @classmethod
            def _default_entries(cls) -> dict[str, type]:
                return {
                    "redis": RedisCacheBackend,
                    "memory": MemoryCacheBackend,
                }

        registry = CacheBackendRegistry.with_defaults()
        backend_cls = registry.select({"type": "redis", "url": "redis://..."})
    """

    def select(self, config: dict[str, Any]) -> Any:
        """Return the first backend class whose ``can_create`` accepts *config*.

        Iterates registered backends in priority order (ascending priority value).

        Args:
            config: Backend configuration dictionary passed to ``can_create``.

        Returns:
            The matching backend *class* (not an instance).

        Raises:
            ValueError: When no registered backend can handle *config*.
        """
        for backend_cls in self.values_ordered():
            if callable(getattr(backend_cls, "can_create", None)):
                if backend_cls.can_create(config):
                    return backend_cls
        raise ValueError(f"No backend in '{self._name}' can handle config: {config!r}")

    def register_backend(self, key: str, backend_cls: Any) -> None:
        """Register a backend factory class under *key*.

        Args:
            key: Unique backend identifier (e.g. ``"redis"``, ``"memcached"``).
            backend_cls: Backend class implementing the target protocol.
        """
        self.register(key, backend_cls)

    def all_backends(self) -> list[Any]:
        """Return all registered backend classes in registration order.

        Returns:
            List of backend classes.
        """
        return list(self.values())


class StrategyRegistry(Registry[Any, Any]):
    """Pluggable algorithm strategy registry.

    Maps strategy keys to strategy class implementations and instantiates
    them on demand via :meth:`instantiate`.

    Use for: chunking, retrieval, reranking, agent reasoning strategies.

    Subclass with concrete types to get type-safe behaviour::

        class ChunkingRegistry(StrategyRegistry):
            def __init__(self) -> None:
                super().__init__(name="chunking.strategies")

            @classmethod
            def default_strategies(cls) -> dict[str, type]:
                return {"fixed": FixedSizeChunker, "semantic": SemanticChunker}

        registry = ChunkingRegistry.with_defaults()
        chunker = registry.instantiate("fixed", chunk_size=512)
    """

    def instantiate(self, key: Any, **kwargs: Any) -> Any:
        """Resolve strategy class by *key* and instantiate with *kwargs*.

        Args:
            key: Strategy identifier (string or enum value).
            **kwargs: Constructor arguments forwarded to the strategy class.

        Returns:
            An instance of the resolved strategy class.

        Raises:
            RegistryKeyError: When *key* is not registered.
        """
        strategy_cls = self.resolve(key)
        return strategy_cls(**kwargs)

    def register_strategy(self, key: Any, strategy_cls: Any) -> None:
        """Register a strategy class under *key*.

        Args:
            key: Strategy identifier.
            strategy_cls: Class implementing the strategy protocol.
        """
        self.register(key, strategy_cls)

    @classmethod
    def _default_entries(cls) -> dict[Any, Any]:
        """Delegate the built-in set to the declarative strategy hook."""
        return cls.default_strategies()

    @classmethod
    def default_strategies(cls) -> dict[Any, Any]:
        """Declare the complete in-package built-in strategy set.

        Every concrete strategy registry overrides this with the full set of
        strategies the package ships (lazy-importing the classes inside the
        method).  ``with_defaults()`` builds the pre-populated registry from
        exactly this mapping; an unimplemented hook raises so a registry is
        never silently empty when its defaults are expected.

        Returns:
            Mapping of key → strategy class.

        Raises:
            NotImplementedError: Base implementation — override to declare
                the built-in strategies.
        """
        msg = (
            f"{cls.__name__} does not declare built-in strategies; "
            "override default_strategies() or register strategies explicitly."
        )
        raise NotImplementedError(msg)


__all__ = [
    "BackendRegistry",
    "Registry",
    "StrategyRegistry",
    "on_register",
    "on_unregister",
]
