"""Container helper utilities for tests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def apply_overrides(container: Any, overrides: Mapping[type, Any]) -> None:
    """Register overrides into a container using best available API.

    This centralizes logic so test bed registration behavior is consistent.

    Note:
        Provider ``register()`` calls run during ``Application.start()``
        and can overwrite these pre-boot bindings.  Call
        :func:`rebind_overrides` after boot so the overrides win.
    """
    for interface, implementation in overrides.items():
        # Prefer singleton to ensure overrides replace any existing defaults
        if hasattr(container, "singleton"):
            container.singleton(interface, implementation)
        elif hasattr(container, "transient"):
            container.transient(interface, lambda impl=implementation: impl)
        else:
            # No known registration API - raise so tests fail fast
            raise RuntimeError("Container does not support known registration methods")


def rebind_overrides(container: Any, overrides: Mapping[type, Any]) -> None:
    """Re-apply overrides after boot, when the container is frozen.

    Provider registrations performed during ``Application.start()`` can
    silently overwrite the pre-boot ``singleton`` bindings made by
    :func:`apply_overrides`.  ``Container.bind`` is designed for rebinding
    during boot and remains available after freeze, so the overrides are
    restored here.  Only interfaces already registered (as singletons) are
    rebound; anything else keeps its pre-boot registration.
    """
    rebind = getattr(container, "bind", None)
    has = getattr(container, "has", None)
    if rebind is None:
        return
    for interface, implementation in overrides.items():
        if has is None or has(interface):
            rebind(interface, implementation)


class ContainerFactory:
    """Factory for creating test containers with common provider registrations.

    This factory provides a standardized way to create DI containers for testing
    that automatically register common protocols and mock implementations.

    Example:
        >>> factory = ContainerFactory()
        >>> container = factory.create_test_container()
        >>> # Container has mock providers registered for common protocols
    """

    def __init__(self) -> None:
        self._common_protocols = [
            # Core protocols
            "DatabaseProviderProtocol",
            "CacheProviderProtocol",
            "AuthProviderProtocol",
            "WebProviderProtocol",
            "EventsProviderProtocol",
            "TaskProviderProtocol",
            # Component protocols
            "LockStore",
            "PubSubProtocol",
            "SecretStore",
            "StateStoreProtocol",
        ]

    def create_test_container(self) -> Any:
        """Create a test container with common protocol registrations.

        Returns:
            Configured container with mock implementations for common protocols.
        """
        from quadkit.di.container import Container

        container = Container()

        # Register common protocols with NoOp/mock implementations
        self._register_common_protocols(container)

        return container

    def _register_common_protocols(self, container: Any) -> None:
        """Register common protocols with appropriate test implementations."""
        # Import only the protocols that actually exist in quadkit.contracts.
        # Each import is guarded individually so a missing protocol never
        # prevents the remainder from being registered.
        contracts: dict[str, Any] = {}

        def _try_import(name: str, module: str = "quadkit.contracts") -> None:
            try:
                import importlib

                mod = importlib.import_module(module)
                contracts[name] = getattr(mod, name)
            except (ImportError, AttributeError):
                pass

        _try_import("AuthProviderProtocol")
        _try_import("CacheProviderProtocol")
        _try_import("DatabaseProviderProtocol")
        _try_import("TaskProviderProtocol")
        # EventsProviderProtocol / WebProviderProtocol
        # may live in extension packages — import them only when available.
        _try_import("EventsProviderProtocol")
        _try_import("WebProviderProtocol")
        # Component protocols
        _try_import("StateStoreProtocol")
        _try_import("SecretStoreProtocol")
        _try_import("AsyncLockProtocol")

        # Register mock implementations for provider protocols
        provider_protocols = [
            "AuthProviderProtocol",
            "CacheProviderProtocol",
            "DatabaseProviderProtocol",
            "EventsProviderProtocol",
            "TaskProviderProtocol",
            "WebProviderProtocol",
        ]

        for protocol_name in provider_protocols:
            if protocol_name in contracts:
                try:
                    mock_impl = self._get_mock_implementation(protocol_name)
                    if mock_impl:
                        container.singleton(contracts[protocol_name], mock_impl)
                except Exception:  # noqa: BLE001 — mock wiring is best-effort; skip anything that cannot be registered
                    pass

        # Register component protocols with simple in-memory implementations
        component_map = {
            "StateStoreProtocol": self._create_memory_state_store(),
            "SecretStoreProtocol": self._create_memory_secret_store(),
            "AsyncLockProtocol": self._create_memory_lock_store(),
        }
        for protocol_name, impl in component_map.items():
            if protocol_name in contracts:
                try:
                    container.singleton(contracts[protocol_name], impl)
                except Exception:  # noqa: BLE001 — component wiring is best-effort; skip anything that cannot be registered
                    pass

    def _get_mock_implementation(self, protocol_name: str) -> Any | None:
        """Get mock implementation for provider protocols."""
        try:
            from quadkit.testing.mocks.base import (
                MockAuthProvider,
                MockDatabaseProvider,
                MockProvider,
                MockTaskProvider,
            )

            implementations = {
                "AuthProviderProtocol": MockAuthProvider(),
                "CacheProviderProtocol": MockProvider(),
                "DatabaseProviderProtocol": MockDatabaseProvider(),
                "EventsProviderProtocol": MockProvider(),
                "TaskProviderProtocol": MockTaskProvider(),
                "WebProviderProtocol": MockProvider(),
            }

            return implementations.get(protocol_name)
        except ImportError:
            return None

    def _get_component_implementation(self, protocol_name: str) -> Any | None:
        """Get simple implementation for component protocols."""
        implementations = {
            "LockStore": self._create_memory_lock_store(),
            "PubSubProtocol": self._create_memory_pubsub(),
            "SecretStore": self._create_memory_secret_store(),
            "StateStoreProtocol": self._create_memory_state_store(),
        }

        return implementations.get(protocol_name)

    def _create_memory_lock_store(self) -> Any:
        """Create in-memory lock store implementation."""
        from typing import Self

        class MemoryLockStore:
            def __init__(self) -> None:
                self._held = False

            async def acquire(self) -> bool:
                """Acquire the lock, blocking until it becomes available."""
                while self._held:
                    # In a real implementation, this would await on an event
                    # For now, just return False (non-blocking acquire failed)
                    return False
                self._held = True
                return True

            def release(self) -> None:
                """Release the lock.

                Raises:
                    RuntimeError: If the lock is not currently held.
                """
                if not self._held:
                    raise RuntimeError("Lock is not held")
                self._held = False

            def locked(self) -> bool:
                """Return True if the lock is currently held."""
                return self._held

            async def __aenter__(self) -> Self:
                """Acquire the lock on context entry."""
                await self.acquire()
                return self

            async def __aexit__(
                self,
                exc_type: type[BaseException] | None,
                exc_val: BaseException | None,
                exc_tb: object,
            ) -> None:
                """Release the lock on context exit."""
                self.release()

        return MemoryLockStore()

    def _create_memory_pubsub(self) -> Any:
        """Create in-memory pubsub implementation."""

        class MemoryPubSub:
            def __init__(self) -> None:
                self._subscribers: dict[str, list[Any]] = {}

            async def publish(self, channel: str, message: Any) -> None:
                subscribers = self._subscribers.get(channel, [])
                for callback in subscribers:
                    await callback(message)

            async def subscribe(self, channel: str, callback: Any) -> None:
                if channel not in self._subscribers:
                    self._subscribers[channel] = []
                self._subscribers[channel].append(callback)

            async def unsubscribe(self, channel: str, callback: Any) -> None:
                if channel in self._subscribers:
                    self._subscribers[channel].remove(callback)

        return MemoryPubSub()

    def _create_memory_secret_store(self) -> Any:
        """Create in-memory secret store implementation."""

        class MemorySecretStore:
            def __init__(self) -> None:
                self._secrets: dict[str, str] = {}

            def get_secret(self, name: str) -> str:
                """Return the value of a secret by name."""
                if name not in self._secrets:
                    from quadkit.contracts.exceptions.components import (
                        SecretNotFoundError,
                    )

                    raise SecretNotFoundError(f"Secret '{name}' not found")
                return self._secrets[name]

            def set_secret(self, name: str, value: str) -> None:
                """Write or overwrite a secret."""
                self._secrets[name] = value

            def delete_secret(self, name: str) -> None:
                """Delete a secret by name (idempotent)."""
                self._secrets.pop(name, None)

            def has_secret(self, name: str) -> bool:
                """Return True if a secret with name exists."""
                return name in self._secrets

        return MemorySecretStore()

    def _create_memory_state_store(self) -> Any:
        """Create in-memory state store implementation."""
        import time

        class MemoryStateStore:
            def __init__(self) -> None:
                self._state: dict[str, Any] = {}
                self._ttls: dict[str, float] = {}

            async def get(self, key: str) -> Any:
                if key not in self._state:
                    return None
                # Check if expired
                if key in self._ttls:
                    if time.time() >= self._ttls[key]:
                        del self._state[key]
                        del self._ttls[key]
                        return None
                return self._state.get(key)

            async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
                self._state[key] = value
                if ttl is not None:
                    self._ttls[key] = time.time() + ttl
                elif key in self._ttls:
                    del self._ttls[key]

            async def delete(self, key: str) -> bool:
                if key in self._state:
                    del self._state[key]
                    if key in self._ttls:
                        del self._ttls[key]
                    return True
                return False

            async def exists(self, key: str) -> bool:
                if key not in self._state:
                    return False
                # Check if expired
                if key in self._ttls:
                    if time.time() >= self._ttls[key]:
                        del self._state[key]
                        del self._ttls[key]
                        return False
                return True

            async def expire(self, key: str, ttl: int) -> bool:
                if key not in self._state:
                    return False
                self._ttls[key] = time.time() + ttl
                return True

            async def ttl(self, key: str) -> int:
                if key not in self._state:
                    return -2  # Key doesn't exist
                if key not in self._ttls:
                    return -1  # No expiry set
                remaining = int(self._ttls[key] - time.time())
                if remaining < 0:
                    del self._state[key]
                    del self._ttls[key]
                    return -2  # Expired
                return remaining

            async def get_many(self, keys: list[str]) -> dict[str, Any]:
                return {k: await self.get(k) for k in keys if await self.exists(k)}

            async def set_many(
                self, items: dict[str, Any], ttl: int | None = None
            ) -> None:
                for k, v in items.items():
                    await self.set(k, v, ttl)

        return MemoryStateStore()


__all__ = ["ContainerFactory", "apply_overrides", "rebind_overrides"]
