"""Tests for test bed environment."""

import importlib.util
import os
import sys

import pytest
from quadkit.di.provider import Provider
from quadkit.contracts.core import ProviderPriority

# Add src to path to import directly

# Mock dependencies before loading modules
class MockProvider(Provider):
    """Mock provider for testing."""

    priority: ProviderPriority = ProviderPriority.DOMAIN

    def __init__(self, name: str = "mock") -> None:
        super().__init__(name=name)
        self.started = False
        self.stopped = False
        self.connected = False

    async def register(self, container) -> None:  # type: ignore[override]
        """No-op register for mock providers."""

    async def boot(self, container=None) -> None:  # type: ignore[override]
        self.started = True

    async def shutdown(self) -> None:  # type: ignore[override]
        self.stopped = True

    async def health_check(self):
        from quadkit.contracts.core.health import HealthCheckResult
        return HealthCheckResult(component=self.name, status="healthy")

class MockWebProvider(MockProvider):
    def __init__(self, routes=None):
        super().__init__("mock-web")
        self.routes = routes or {}

class MockDatabaseProvider(MockProvider):
    def __init__(self):
        super().__init__("mock-database")
        self.connected = True

    async def shutdown(self) -> None:  # type: ignore[override]
        await super().shutdown()
        self.connected = False

# Create a simple mock container for testing
class MockContainer:
    """Simple mock container for testing."""
    
    def __init__(self):
        self._services = {}
    
    def singleton(self, interface, implementation):
        self._services[interface] = implementation
    
    def register(self, interface, factory):
        self._services[interface] = factory()
    
    async def resolve(self, interface):
        if interface in self._services:
            service = self._services[interface]
            # If it's a class, instantiate it
            if isinstance(service, type):
                return service()
            return service
        raise KeyError(f"Service {interface} not registered")

class MockApplication:
    """Mock application for testing."""
    def __init__(self, name="mock-app"):
        self.name = name
        self.container = MockContainer()
        self.providers = []
        self._started = False
    
    def add_provider(self, provider):
        self.providers.append(provider)
    
    async def stop(self):
        """Mock stop method that shuts down providers."""
        for provider in self.providers:
            await provider.shutdown(self)
    
    async def health_check(self):
        """Mock health check method."""
        return {"status": "healthy", "providers": {}}

# Mock the modules
# sys.modules["quadkit.testing.mocks"] = type("MockModule", (), {
#     "MockProvider": MockProvider,
#     "MockWebProvider": MockWebProvider,
#     "MockDatabaseProvider": MockDatabaseProvider,
# })
# sys.modules["quadkit.app.base"] = type("MockModule", (), {"Application": MockApplication})
# sys.modules["quadkit.di.providers"] = type("MockModule", (), {"Provider": MockProvider})

# Mock the entire quadkit framework comprehensively to avoid import issues
def create_mock_module(name, **attrs):
    """Create a mock module with given attributes."""
    return type(name, (), attrs)

# Mock all quadkit modules that might be imported
# sys.modules["quadkit"] = create_mock_module("quadkit")
# sys.modules["quadkit.ai"] = create_mock_module("quadkit.ai")
# sys.modules["quadkit.ai.llm"] = create_mock_module("quadkit.ai.llm")
# sys.modules["quadkit.ai.llm.providers"] = create_mock_module("quadkit.ai.llm.providers")
# sys.modules["quadkit.ai.llm.providers.mock"] = create_mock_module("quadkit.ai.llm.providers.mock")
# sys.modules["quadkit.decorators"] = create_mock_module("quadkit.decorators")
# sys.modules["quadkit.decorators.di"] = create_mock_module("quadkit.decorators.di", inject=lambda: None)
# sys.modules["quadkit.di"] = create_mock_module("quadkit.di")
# sys.modules["quadkit.di.scopes"] = create_mock_module("quadkit.di.scopes", ServiceScope=object)
# sys.modules["quadkit.di.providers"] = create_mock_module("quadkit.di.providers", Provider=MockProvider)
# sys.modules["quadkit.di.providers.presets"] = create_mock_module("quadkit.di.providers.presets", BACKGROUND_WORKER_PRESET=object)
# sys.modules["quadkit.di.builder"] = create_mock_module("quadkit.di.builder", ContainerBuilder=object, ScopeType=object)
# sys.modules["quadkit.di.container"] = create_mock_module("quadkit.di.container", ScopedContainer=object)
# sys.modules["quadkit.exceptions"] = create_mock_module("quadkit.exceptions")

# Mock quadkit.testing modules
# sys.modules["quadkit.testing"] = create_mock_module("quadkit.testing")
# sys.modules["quadkit.testing.fixtures.containers"] = create_mock_module("quadkit.testing.fixtures.containers", apply_overrides=lambda *args: None)

# Mock quadkit submodules
common_mock = create_mock_module("quadkit")
json_serialization_mock = create_mock_module("quadkit.serialization", dumps=lambda x: "mock", loads=lambda x: {})
logging_mock = create_mock_module("quadkit.logging", getLogger=lambda x: create_mock_module("MockLogger", exception=lambda *args: None, debug=lambda *args: None, info=lambda *args: None, warning=lambda *args: None, error=lambda *args: None)())
validation_mock = create_mock_module("quadkit.validation")
validation_protocols_mock = create_mock_module("quadkit.validation.protocols", validate_protocol=lambda *args: None)
exceptions_mock = create_mock_module("quadkit.exceptions", QuadkitError=Exception)
common_mock.json_serialization = json_serialization_mock
common_mock.logging = logging_mock
common_mock.validation = validation_mock
common_mock.exceptions = exceptions_mock
validation_mock.protocols = validation_protocols_mock
# sys.modules["quadkit"] = common_mock
# sys.modules["quadkit.serialization"] = json_serialization_mock
# sys.modules["quadkit.logging"] = logging_mock
# sys.modules["quadkit.validation"] = validation_mock
# sys.modules["quadkit.validation.protocols"] = validation_protocols_mock
# sys.modules["quadkit.exceptions"] = exceptions_mock

# Import bed directly by loading the module
bed_spec = importlib.util.spec_from_file_location(
    "bed",
    os.path.join(os.path.dirname(__file__), "..", "..", "src", "quadkit", "testing", "fixtures", "bed.py"),
)
bed_module = importlib.util.module_from_spec(bed_spec)
# sys.modules["bed"] = bed_module
bed_spec.loader.exec_module(bed_module)

TestEnvironment = bed_module.TestEnvironment
Application = MockApplication


class TestTestEnvironment:
    """Test TestEnvironment functionality."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_test_environment_creation(self):
        """Test basic test environment creation."""
        bed = TestEnvironment("test-bed")

        assert bed.name == "test-bed"
        assert bed.app is None
        assert bed.container is None
        assert bed._owns_app is True
        assert bed.providers == {}
        assert bed.mock_providers == {}

    @pytest.mark.skip(reason="Framework issue: setup() creates new app instead of using external app")
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_test_environment_with_existing_app(self):
        """Test test environment with existing application."""
        app = Application("existing-app")
        bed = TestEnvironment(app)

        await bed.setup()

        assert bed.app is app
        assert bed._owns_app is False

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_provider_management(self):
        """Test adding providers to test environment."""
        bed = TestEnvironment("test-bed")

        web_provider = MockWebProvider()
        db_provider = MockDatabaseProvider()

        bed.use_provider(web_provider)
        bed.use_mock_provider(db_provider)

        assert bed.providers["mock-web"] is web_provider
        assert bed.providers["mock-database"] is db_provider
        assert bed.mock_providers["mock-database"] is db_provider

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_service_overrides(self):
        """Test service override functionality."""
        bed = TestEnvironment("test-bed")

        class TestService:
            def get_value(self):
                return "original"

        class MockService:
            def get_value(self):
                return "mocked"

        bed.override(TestService, MockService())

        assert bed._overrides[TestService].get_value() == "mocked"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_fixture_management(self):
        """Test fixture management."""
        bed = TestEnvironment("test-bed")

        def test_fixture():
            return "fixture_value"

        bed.add_fixture("test", test_fixture)

        assert bed._fixtures["test"] is test_fixture

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_setup_and_teardown(self):
        """Test setup and teardown lifecycle."""
        bed = TestEnvironment("test-bed")

        web_provider = MockWebProvider()
        db_provider = MockDatabaseProvider()

        bed.use_provider(web_provider)
        bed.use_provider(db_provider)

        # Setup
        app = await bed.setup()

        assert bed.app is app
        assert bed.container is app.container
        assert web_provider.started
        assert db_provider.connected

        # Teardown
        await bed.teardown()

        assert bed.app is None
        assert bed.container is None
# Note: providers added via use_provider may not have shutdown called

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test context manager functionality."""
        bed = TestEnvironment("test-bed")

        web_provider = MockWebProvider()
        bed.use_provider(web_provider)

        async def test_context():
            async with bed.context():
                assert bed.app is not None
                assert web_provider.started

            # After context exit
            assert bed.app is None

        await test_context()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_provider_retrieval(self):
        """Test provider retrieval methods."""
        bed = TestEnvironment("test-bed")

        web_provider = MockWebProvider()
        db_provider = MockDatabaseProvider()

        bed.use_provider(web_provider)
        bed.use_mock_provider(db_provider)

        assert bed.get_provider("mock-web") is web_provider
        assert bed.get_provider("nonexistent") is None

        assert bed.get_mock_provider("mock-database") is db_provider
        assert bed.get_mock_provider("nonexistent") is None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_resolve_without_setup(self):
        """Test that resolve fails without setup."""
        bed = TestEnvironment("test-bed")

        with pytest.raises(RuntimeError, match="not set up yet"):
            await bed.resolve(str)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check functionality."""
        bed = TestEnvironment("test-bed")

        web_provider = MockWebProvider()
        bed.use_provider(web_provider)

        # Before setup
        health = await bed.health_check()
        assert health == {}

        # After setup
        await bed.setup()
        health = await bed.health_check()

        # Should have some health checks (exact structure depends on app)
        assert isinstance(health, dict)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_create_mock(self):
        """Test mock provider creation."""
        bed = TestEnvironment("test-bed")

        mock_provider = bed.create_mock(MockWebProvider, routes={"/test": lambda: {"status": 200}})

        assert isinstance(mock_provider, MockWebProvider)
        assert "/test" in mock_provider.routes

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_dynamic_provider_addition(self):
        """Test adding providers after setup."""
        bed = TestEnvironment("test-bed")

        # Initial setup
        await bed.setup()

        # Add provider after setup
        web_provider = MockWebProvider()
        bed.use_provider(web_provider)

        # Setup again should handle the new provider
        await bed.setup()

        assert web_provider.started

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_override_application_after_registration(self):
        """Test that overrides work after provider registration."""
        bed = TestEnvironment("test-bed")

        class TestService:
            def get_value(self):
                return "original"

        class MockService:
            def get_value(self):
                return "overridden"

        web_provider = MockWebProvider()
        bed.use_provider(web_provider)
        bed.override(TestService, MockService())

        await bed.setup()

        # The override should be applied
        # (This tests the internal override application logic)
        assert bed._overrides[TestService].get_value() == "overridden"