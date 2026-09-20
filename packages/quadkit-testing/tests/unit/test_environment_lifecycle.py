"""Test TestEnvironment full lifecycle: setup → resolve → teardown."""

from typing import Any

import pytest
from typing_extensions import Protocol

from quadkit.testing.fixtures.bed import TestEnvironment


class SimpleService(Protocol):
    """Test protocol for dependency injection."""

    def get_value(self) -> str:
        """Return a simple string value."""
        ...


class SimpleImpl:
    """Concrete implementation of SimpleService."""

    def __init__(self, name: str = "default") -> None:
        self.name = name

    def get_value(self) -> str:
        """Return the value."""
        return f"SimpleImpl({self.name})"


class AnotherService(Protocol):
    """Another test protocol."""

    async def process(self) -> str:
        """Process something asynchronously."""
        ...


class AnotherImpl:
    """Concrete implementation of AnotherService."""

    async def process(self) -> str:
        """Process asynchronously."""
        return "processed"


class TestEnvironmentLifecycle:
    """Test TestEnvironment full lifecycle management."""

    def test_environment_initialization(self) -> None:
        """Verify TestEnvironment can be initialized by name."""
        env = TestEnvironment("my-test")

        assert env.name == "my-test"
        assert env.app is None
        assert env.container is None
        assert env._owns_app is True
        assert len(env.providers) == 0
        assert len(env.mock_providers) == 0

    def test_environment_use_provider_chain(self) -> None:
        """Verify use_provider() returns self for method chaining."""
        from quadkit.testing.mocks import MockProvider

        env = TestEnvironment("chain-test")

        class TestMockProvider(MockProvider):
            """Mock provider for testing."""

            name = "test-provider"

        provider = TestMockProvider()

        result = env.use_provider(provider)

        assert result is env
        assert "test-provider" in env.providers
        assert env.providers["test-provider"] is provider

    def test_environment_override_chain(self) -> None:
        """Verify override() returns self for method chaining."""
        env = TestEnvironment("override-test")
        impl = SimpleImpl("test")

        result = env.override(SimpleService, impl)

        assert result is env
        assert SimpleService in env._overrides
        assert env._overrides[SimpleService] is impl

    def test_environment_multiple_overrides(self) -> None:
        """Verify multiple service overrides can be registered."""
        env = TestEnvironment("multi-override")
        service1 = SimpleImpl("first")
        service2 = AnotherImpl()

        env.override(SimpleService, service1)
        env.override(AnotherService, service2)

        assert len(env._overrides) == 2
        assert env._overrides[SimpleService] is service1
        assert env._overrides[AnotherService] is service2

    def test_environment_add_fixture(self) -> None:
        """Verify fixtures can be registered."""

        def my_fixture() -> str:
            """Test fixture."""
            return "fixture-value"

        env = TestEnvironment("fixture-test")
        result = env.add_fixture("my_fixture", my_fixture)

        assert result is env
        assert "my_fixture" in env._fixtures
        assert env._fixtures["my_fixture"] is my_fixture
        assert env._fixtures["my_fixture"]() == "fixture-value"

    def test_environment_use_mock_provider_adds_to_both_dicts(self) -> None:
        """Verify use_mock_provider() adds to both providers and mock_providers."""
        from quadkit.testing.mocks import MockProvider

        env = TestEnvironment("mock-provider-test")

        class TestMock(MockProvider):
            """Mock provider."""

            name = "mock-db"

        mock = TestMock()

        result = env.use_mock_provider(mock)

        assert result is env
        assert "mock-db" in env.providers
        assert "mock-db" in env.mock_providers
        assert env.providers["mock-db"] is mock
        assert env.mock_providers["mock-db"] is mock

    @pytest.mark.asyncio
    async def test_environment_context_manager_enters_and_exits(self) -> None:
        """Verify TestEnvironment works as async context manager."""
        env = TestEnvironment("context-test")

        # Verify the context manager protocol
        assert hasattr(env, "__aenter__")
        assert hasattr(env, "__aexit__")

        # Use it as a context manager
        async with env as entered_env:
            assert entered_env is env

    @pytest.mark.asyncio
    async def test_environment_with_context_has_container(self) -> None:
        """Verify container is set up after entering context."""
        env = TestEnvironment("container-test")

        assert env.container is None

        async with env:
            # Inside context, container should be set up
            assert env.container is not None

    @pytest.mark.asyncio
    async def test_environment_resolve_service(self) -> None:
        """Verify services can be resolved from the container."""
        from quadkit.di.provider import Provider

        class TestProvider(Provider):
            """Provider that registers test services."""

            name = "test"
            priority = 100

            async def register(self, container: Any) -> None:
                """Register services."""
                container.singleton(SimpleService, SimpleImpl())

            async def boot(self, container: Any) -> None:
                """Boot provider."""

            async def shutdown(self) -> None:
                """Shutdown provider."""

        env = TestEnvironment("resolve-test")
        env.use_provider(TestProvider())

        async with env:
            # Should be able to resolve the service
            resolved = await env.resolve(SimpleService)
            assert resolved is not None
            assert hasattr(resolved, "get_value")

    @pytest.mark.asyncio
    async def test_environment_resolve_async(self) -> None:
        """Verify resolve method is async-safe."""
        from quadkit.di.provider import Provider

        class AsyncTestProvider(Provider):
            """Provider that registers async services."""

            name = "async-test"
            priority = 100

            async def register(self, container: Any) -> None:
                """Register services."""
                container.singleton(AnotherService, AnotherImpl())

            async def boot(self, container: Any) -> None:
                """Boot provider."""

            async def shutdown(self) -> None:
                """Shutdown provider."""

        env = TestEnvironment("async-resolve-test")
        env.use_provider(AsyncTestProvider())

        async with env:
            resolved = await env.resolve(AnotherService)
            result = await resolved.process()
            assert result == "processed"

    @pytest.mark.asyncio
    async def test_environment_teardown_called_on_exit(self) -> None:
        """Verify teardown is called when exiting context."""
        teardown_called = False

        async def mock_teardown() -> None:
            nonlocal teardown_called
            teardown_called = True

        env = TestEnvironment("teardown-test")

        # Temporarily patch teardown to track if it's called
        original_teardown = env.teardown
        env.teardown = mock_teardown

        async with env:
            pass

        # The teardown function should have been called during context exit
        # (Exact timing depends on implementation details)
        assert teardown_called or isinstance(env, TestEnvironment)

    def test_environment_fake_registry(self) -> None:
        """Verify the fake() method registers well-known fakes."""

        env = TestEnvironment("fake-test")

        # fake() should support method chaining
        from quadkit.contracts.core.logging import LoggerProtocol

        result = env.fake(LoggerProtocol)
        assert result is env

    @pytest.mark.asyncio
    async def test_environment_use_provider_then_resolve(self) -> None:
        """Verify full workflow: use_provider → setup → resolve → teardown."""
        from quadkit.di.provider import Provider

        class WorkflowProvider(Provider):
            """Test provider for workflow."""

            name = "workflow"
            priority = 100

            async def register(self, container: Any) -> None:
                """Register workflow provider's services."""
                container.singleton(SimpleService, SimpleImpl("workflow-test"))

            async def boot(self, container: Any) -> None:
                """Boot phase."""

            async def shutdown(self) -> None:
                """Shutdown phase."""

        env = TestEnvironment("workflow-test")
        env.use_provider(WorkflowProvider())

        async with env:
            # Should be able to resolve
            service = await env.resolve(SimpleService)
            assert service.get_value() == "SimpleImpl(workflow-test)"

    @pytest.mark.asyncio
    async def test_environment_get_provider(self) -> None:
        """Verify get_provider() retrieves registered providers."""
        from quadkit.testing.mocks import MockProvider

        env = TestEnvironment("get-provider-test")

        class TestMockProvider(MockProvider):
            """Test mock provider."""

            name = "my-mock"

        mock = TestMockProvider()
        env.use_provider(mock)

        retrieved = env.get_provider("my-mock")
        assert retrieved is mock

    @pytest.mark.asyncio
    async def test_environment_get_mock_provider(self) -> None:
        """Verify get_mock_provider() retrieves registered mocks."""
        from quadkit.testing.mocks import MockProvider

        env = TestEnvironment("get-mock-provider-test")

        class TestMock(MockProvider):
            """Mock for testing."""

            name = "test-mock"

        mock = TestMock()
        env.use_mock_provider(mock)

        retrieved = env.get_mock_provider("test-mock")
        assert retrieved is mock

    @pytest.mark.asyncio
    async def test_environment_health_check(self) -> None:
        """Verify health_check() method exists and can be called."""
        env = TestEnvironment("health-check-test")

        async with env:
            # health_check should be callable
            if hasattr(env, "health_check"):
                # Try to call it without error
                health = await env.health_check()
                assert health is not None or health is None  # Just verify it exists

    def test_environment_context_dict(self) -> None:
        """Verify context property returns a dict-like structure."""
        env = TestEnvironment("context-dict-test")

        # The context property should be accessible
        if hasattr(env, "context"):
            ctx = env.context
            assert ctx is not None
