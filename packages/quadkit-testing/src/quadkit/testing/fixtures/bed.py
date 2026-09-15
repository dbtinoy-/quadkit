"""Test Bed Environment for isolated provider testing.

This module provides the TestEnvironment class for creating isolated
test environments for testing Quadkit providers and applications.

The TestEnvironment allows you to:
- Create isolated containers for each test
- Register mock providers to replace real ones
- Override services for testing
- Set up fixtures that are automatically cleaned up after tests

Example:
    Basic usage::

        from quadkit.testing.fixtures.bed import TestEnvironment

        env = TestEnvironment("my-test")
        env.use_provider(MyProvider())

        async with env.run():
            # Test code here
            result = await env.container.resolve(MyService)

    Using with pytest::

        import pytest
        from quadkit.testing.fixtures.bed import TestEnvironment

        @pytest.fixture
        async def test_env():
            env = TestEnvironment("pytest-test")
            env.use_provider(MockDatabaseProvider())
            async with env.run():
                yield env

        async def test_something(test_env):
            db = await test_env.container.resolve(DatabaseService)
            assert db is not None
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager, suppress
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    Self,
)

from quadkit.di.provider import Provider
from quadkit.logging import get_logger

logger = get_logger(__name__)

# Re-export commonly used mock provider classes so tests can import them from
# `quadkit.testing.bed` (some tests historically import MockDatabaseProvider from here).
try:
    from quadkit.testing.mocks.base import (
        MockDatabaseProvider as MockDatabaseProvider,
    )
    from quadkit.testing.mocks.base import (
        MockProvider as MockProvider,
    )
except ImportError:  # pragma: no cover - best-effort re-export for test convenience
    MockProvider = None  # type: ignore[assignment,misc]
    MockDatabaseProvider = MockProvider  # type: ignore[assignment,misc]


pytest: Any | None = None
try:
    import pytest
except ImportError:
    pytest = None

# Provide a lightweight fallback for getLogger at module import time so
# running static checks or earlier import-time code paths do not fail if the
# logging module isn't available at import time.
try:
    from quadkit.logging import get_logger
except Exception as _exc:  # pragma: no cover - fallback for static checks/runtime
    # Only swallow ImportError (module not available); re-raise unexpected errors
    if not isinstance(_exc, ImportError):
        raise
    from logging import Logger as _Logger

    def get_logger(name: str | None = None) -> _Logger:  # type: ignore[misc]
        """Fallback implementation matching the real signature and return type
        so runtime imports and static analysis agree.
        """
        import logging as _logging

        return _logging.getLogger(name or "quadkit.testing.bed")


def _raise_assertion(msg: str) -> None:
    """Helper to raise AssertionError from other utility code."""
    raise AssertionError(msg)  # pragma: no cover - simple helper used in tests


if TYPE_CHECKING:
    # Application is imported lazily inside the methods below to avoid a
    # runtime import cycle; the annotations still need the name at type
    # check time.
    from quadkit.app.base import Application
    from quadkit.di.container import Container

# Import context module for Context mocking
Context: Any | None = None
HAS_RUNTIME: bool = False
try:
    from quadkit.primitives.context import Context as _Context

    Context = _Context
    HAS_RUNTIME = True
except ImportError:
    Context = None
    HAS_RUNTIME = False


class TestEnvironment:
    """Isolated test environment for provider testing.

    __test__ = False

    The TestEnvironment provides a controlled testing environment for
    Quadkit providers and applications. It manages the application lifecycle,
    dependency injection container, and provider registration for tests.

    Attributes:
        name: Name of the test environment.
        app: The Application instance, if created.
        container: The DI container for service resolution.
        providers: Dictionary of registered providers.
        mock_providers: Dictionary of registered mock providers.

    Example:
        Creating an environment::

            env = TestEnvironment("my-test")

            # Add providers
            env.use_provider(MyProvider())

            # Add mock providers
            env.use_mock_provider(MockDatabaseProvider())

            # Override services
            env.override_service(DbService, MockDbService)

            # Run the test
            async with env.run():
                service = await env.container.resolve(MyService)

        Using with pytest fixtures::

            @pytest.fixture
            async def test_env():
                env = TestEnvironment("test")
                async with env.run():
                    yield env
    """

    __test__ = False

    # Explicit attribute annotations to satisfy static analysis
    name: str
    app: Application | None
    container: Container | None
    _owns_app: bool
    providers: dict[str, Provider]
    mock_providers: dict[str, MockProvider]
    _overrides: dict[type, Any]
    _fixtures: dict[str, Callable]

    def __init__(self, name_or_app: str | Application = "test-bed") -> None:
        # Imported lazily: ``quadkit.app`` must not be forced into the import
        # graph when this module is loaded by the pytest11 plugin entry point
        # (that happens before pytest-cov starts measuring, which leaves the
        # whole app chain's module-level statements uncounted in every
        # package's coverage report).
        from quadkit.app.base import Application

        if isinstance(name_or_app, Application):
            self.name = name_or_app.name
            self.app = name_or_app
            self.container = name_or_app.container
            self._owns_app = False  # Don't stop an app we didn't create
        else:
            self.name = name_or_app
            self.app: Application | None = None
            self.container: Container | None = None
            self._owns_app = True  # We created the app, so we should stop it

        self.providers: dict[str, Provider] = {}
        self.mock_providers: dict[str, MockProvider] = {}
        self._overrides: dict[type, Any] = {}
        self._fixtures: dict[str, Callable] = {}

    def ensure_app(self) -> None:
        """Create the application and container if they do not exist yet.

        Test beds that must register DI bindings *before* boot call this
        first: the container freezes once the application has started,
        so late ``singleton()`` registrations would be rejected.
        """
        if self.app is None:
            from quadkit.app.base import Application

            self.app = Application(name=self.name)
            self._owns_app = True
        if self.container is None:
            self.container = self.app.container

    def use_provider(self, provider: Provider) -> TestEnvironment:
        """Add a provider to the test bed."""
        self.providers[provider.name] = provider
        return self

    def use_mock_provider(self, provider: MockProvider) -> TestEnvironment:
        """Add a mock provider to the test bed."""
        self.mock_providers[provider.name] = provider
        self.providers[provider.name] = provider
        return self

    def override(self, interface: type, implementation: Any) -> TestEnvironment:
        """Override a service registration."""
        self._overrides[interface] = implementation
        return self

    def add_fixture(self, name: str, fixture_func: Callable) -> TestEnvironment:
        """Add a test fixture."""
        self._fixtures[name] = fixture_func
        return self

    def fake(self, contract: type) -> TestEnvironment:
        """Register the well-known fake for *contract* and return self.

        The fake-registry maps core protocol types to their in-memory doubles
        from :mod:`quadkit.testing.fakes`.  Raises :exc:`ValueError` if no
        fake is registered for the given contract.

        Example::

            env.fake(FakeEventBus).fake(FakeLogger)
        """
        from quadkit.testing.fakes import (
            FakeCache,
            FakeCommandBus,
            FakeConfig,
            FakeEventBus,
            FakeLogger,
            FakeMetricsCollector,
            FakeQueryBus,
            FakeStateStore,
        )

        # Build a name-based lookup so we don't need to import every contract.
        _NAME_REGISTRY: dict[str, Any] = {
            # Core
            "EventBusProtocol": FakeEventBus,
            "LoggerProtocol": FakeLogger,
            "Logger": FakeLogger,
            # Cache
            "CacheBackendProtocol": FakeCache,
            "CacheProtocol": FakeCache,
            # Messaging / CQRS
            "CommandBusProtocol": FakeCommandBus,
            "QueryBusProtocol": FakeQueryBus,
            # State / metrics / config
            "StateStoreProtocol": FakeStateStore,
            "MetricsCollectorProtocol": FakeMetricsCollector,
            "MetricsRecorderProtocol": FakeMetricsCollector,
            "ConfigProtocol": FakeConfig,
            "Config": FakeConfig,
        }

        contract_name = contract.__name__
        fake_cls = _NAME_REGISTRY.get(contract_name)

        # Fall back to exact-type lookup to support direct fake-class registration
        if fake_cls is None:
            _TYPE_REGISTRY: dict[type, type] = {
                FakeEventBus: FakeEventBus,
                FakeLogger: FakeLogger,
                FakeCache: FakeCache,
                FakeCommandBus: FakeCommandBus,
                FakeQueryBus: FakeQueryBus,
                FakeStateStore: FakeStateStore,
                FakeMetricsCollector: FakeMetricsCollector,
                FakeConfig: FakeConfig,
            }
            fake_cls = _TYPE_REGISTRY.get(contract)

        if fake_cls is None:
            msg = (
                f"No fake registered for {contract_name!r}. "
                f"Use env.override({contract_name}, YourFake()) instead."
            )
            raise ValueError(msg)

        self._overrides[contract] = fake_cls()
        return self

    def get_fake(self, contract: type) -> Any:
        """Return the fake instance registered for *contract*.

        Raises :exc:`ValueError` if *contract* has no registered fake.
        Use this in tests to inspect recorded interactions after the
        code under test has run.

        Example::

            bus = env.get_fake(FakeEventBus)
            bus.assert_published(UserCreated)
        """
        instance = self._overrides.get(contract)
        if instance is None:
            msg = (
                f"No fake registered for {contract.__name__!r}. "
                f"Did you call env.fake({contract.__name__}) ?"
            )
            raise ValueError(msg)
        return instance

    async def setup(self) -> Application:
        """Setup the test environment.

        If called on an already-running environment, automatically tears down and
        restarts if new providers have been added since the last setup — enabling
        the pattern of incremental provider registration followed by a second
        ``setup()`` call.
        """
        from quadkit.app.base import AppState

        # Detect whether there are providers that haven't been booted yet
        new_providers = (
            [p for p in self.providers.values() if not p.is_booted]
            if self.app is not None and self.app.state == AppState.RUNNING
            else []
        )

        # Restart if the app is running but we have new providers to add
        if (
            new_providers
            and self.app is not None
            and self.app.state == AppState.RUNNING
        ):
            await self.teardown()

        if self.app is None:
            # Create application
            from quadkit.app.base import Application

            self.app = Application(name=self.name)
            self._owns_app = True

        # If already running (and no new providers), nothing left to do
        if self.app.state == AppState.RUNNING:
            self.container = self.app.container
            return self.app

        # Add all providers — re-arm any previously booted/shut-down
        # provider so a restarted application can boot it again.
        from quadkit.di.provider import ProviderState

        for provider in self.providers.values():
            if provider.state == ProviderState.SHUTDOWN:
                provider.reset_state()
            self.app.add_provider(provider)

        # Apply overrides to the application's container
        from quadkit.testing.fixtures.containers import (
            apply_overrides,
            rebind_overrides,
        )

        apply_overrides(self.app.container, self._overrides)

        # Start the application if it's in CREATED state
        if self.app.state == AppState.CREATED:
            await self.app.start()
            # Provider registrations during boot can overwrite the pre-boot
            # bindings; re-apply the overrides now that the container is
            # frozen (``bind`` works on frozen containers).
            rebind_overrides(self.app.container, self._overrides)

        # Get the container
        self.container = self.app.container

        # For testing convenience, allow TestClient to be constructed with
        # `test_bed.app.set_asgi_handler` by exposing a callable ASGI app
        # attribute after setup has completed.
        with suppress(Exception):
            if hasattr(self.app, "set_asgi_handler"):
                # If it's already a method, we might be overriding it or it might be a property
                # In most tests, they expect app.set_asgi_handler to be the ASGI callable (Starlette app)
                # But here we just ensure it exists if some code expects it.
                pass
            else:
                self.app.set_asgi_handler = lambda _: None  # type: ignore[attr-defined]

        return self.app

    async def teardown(self) -> None:
        """Teardown the test environment."""
        await self.teardown_providers()

        if self.app:
            # Shutdown providers added via use_provider()

            for provider in self.providers.values():
                try:
                    await provider.shutdown()
                except Exception as exc:  # noqa: BLE001 — best-effort shutdown; a failing provider must not block the rest
                    logger.debug(
                        "provider_shutdown_failed", error=str(exc)
                    )  # Best effort shutdown

            if self._owns_app:
                try:
                    await self.app.stop()
                except Exception as exc:  # noqa: BLE001 — best-effort shutdown; a failing provider must not block teardown
                    logger.debug("app_shutdown_failed", error=str(exc))
                self.app = None
                self.container = None

    async def teardown_providers(self) -> None:
        """Hook for subclasses to tear down providers (no-op default)."""
        return

    @asynccontextmanager
    async def context(self) -> AsyncGenerator[TestEnvironment, None]:
        """Context manager for test bed lifecycle."""
        await self.setup()
        try:
            yield self
        finally:
            await self.teardown()

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        await self.setup()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        await self.teardown()

    def get_provider(self, name: str) -> Provider | None:
        """Get a provider by name."""
        return self.providers.get(name)

    def get_mock_provider(self, name: str) -> MockProvider | None:
        """Get a mock provider by name."""
        return self.mock_providers.get(name)

    def resolve_sync(self, service_type: type) -> Any:
        """Resolve a service from the container synchronously."""
        if self.container:
            from quadkit.concurrency import run_sync

            return run_sync(self.container.resolve, service_type)
        msg = "TestEnvironment not set up yet. Call setup() first."
        raise RuntimeError(msg)

    async def resolve(self, service_type: type) -> Any:
        """Resolve a service from the container asynchronously."""
        if self.container:
            return await self.container.resolve(service_type)
        msg = "TestEnvironment not set up yet. Call setup() first."
        raise RuntimeError(msg)

    async def health_check(self) -> dict[str, dict[str, Any]]:
        """Get health status of all providers."""
        if not self.app:
            return {}

        health_result = await self.app.health_check()

        return {
            result.component: result.to_dict() for result in health_result.components
        }

    def create_mock(
        self,
        provider_class: type[MockProvider],
        **kwargs: Any,
    ) -> MockProvider:
        """Create a mock provider instance."""
        return provider_class(**kwargs)


__all__ = ["TestEnvironment"]
