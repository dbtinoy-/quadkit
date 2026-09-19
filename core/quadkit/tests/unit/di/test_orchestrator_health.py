from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from quadkit.contracts.core.health import (
    AggregateHealthResult,
    HealthCheckCategory,
    HealthCheckResult,
    HealthStatus,
)
from quadkit.di.container import Container
from quadkit.di.module.graph import ProviderEntry
from quadkit.di.orchestrator import ProviderOrchestrator
from quadkit.di.provider import Provider


class DummyProvider(Provider):
    async def register(self, container: Container) -> None:
        pass

    async def boot(self, container: Container) -> None:
        pass

    async def shutdown(self) -> None:
        pass


class HealthyProvider(Provider):
    async def register(self, container: Container) -> None:
        pass

    async def boot(self, container: Container) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(component="healthy", status=HealthStatus.HEALTHY)


class LivenessProvider(Provider):
    async def register(self, container: Container) -> None:
        pass

    async def boot(self, container: Container) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(
            component="live",
            status=HealthStatus.HEALTHY,
            category=HealthCheckCategory.LIVENESS,
        )


class ReadinessProvider(Provider):
    async def register(self, container: Container) -> None:
        pass

    async def boot(self, container: Container) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(
            component="ready",
            status=HealthStatus.DEGRADED,
            category=HealthCheckCategory.READINESS,
        )


class StartupProvider(Provider):
    async def register(self, container: Container) -> None:
        pass

    async def boot(self, container: Container) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(
            component="startup",
            status=HealthStatus.HEALTHY,
            category=HealthCheckCategory.STARTUP,
        )


@pytest.mark.asyncio
async def test_orchestrator_health_checks_protocol():
    container = Container()
    orchestrator = ProviderOrchestrator(container)
    orchestrator.add(DummyProvider(name="dummy"))
    orchestrator.add(HealthyProvider(name="healthy"))

    results = await orchestrator.health_check()
    assert "dummy" in results
    assert results["dummy"].status == HealthStatus.HEALTHY
    assert "healthy" in results
    assert results["healthy"].status == HealthStatus.HEALTHY


@pytest.mark.asyncio
async def test_orchestrator_category_probe_helpers() -> None:
    container = Container()
    orchestrator = ProviderOrchestrator(container)
    orchestrator.add(LivenessProvider(name="live"))
    orchestrator.add(ReadinessProvider(name="ready"))
    orchestrator.add(StartupProvider(name="startup"))

    liveness = await orchestrator.run_liveness()
    assert [component.component for component in liveness.components] == ["live"]
    assert liveness.components[0].category == HealthCheckCategory.LIVENESS

    readiness = await orchestrator.run_readiness()
    assert [component.component for component in readiness.components] == ["ready"]
    assert readiness.components[0].category == HealthCheckCategory.READINESS

    startup = await orchestrator.run_startup()
    assert [component.component for component in startup.components] == ["startup"]
    assert startup.components[0].category == HealthCheckCategory.STARTUP

    filtered = await orchestrator.run_all(category=HealthCheckCategory.READINESS)
    assert [component.component for component in filtered.components] == ["ready"]


@pytest.mark.asyncio
async def test_orchestrator_run_all_returns_aggregate_result() -> None:
    container = Container()
    orchestrator = ProviderOrchestrator(container)
    orchestrator.add(HealthyProvider(name="healthy"))

    result = await orchestrator.run_all()

    assert isinstance(result, AggregateHealthResult)
    assert result.components[0].component == "healthy"


class MockProvider(Provider):
    """Mock provider for testing."""

    def __init__(self, name: str) -> None:
        super().__init__(name=name)


class MockProvider1(Provider):
    """Mock provider 1 for testing."""

    def __init__(self) -> None:
        super().__init__(name="provider1")


class MockProvider2(Provider):
    """Mock provider 2 for testing."""

    def __init__(self) -> None:
        super().__init__(name="provider2")


class MockProvider3(Provider):
    """Mock provider 3 for testing."""

    def __init__(self) -> None:
        super().__init__(name="provider3")


class TestGetModuleHealthProviders:
    """Tests for get_module_health_providers method."""

    def test_raises_before_boot(self) -> None:
        """Should raise RuntimeError when called before compiled graph is set."""
        container = Container()
        orchestrator = ProviderOrchestrator(container)

        # Compiled graph is None (default state)
        assert orchestrator._compiled_graph is None

        # Should raise
        with pytest.raises(RuntimeError, match="Orchestrator has not been booted yet"):
            orchestrator.get_module_health_providers(MagicMock)

    def test_returns_all_providers_when_health_providers_none(self) -> None:
        """Should return all module providers when health_providers=None."""
        container = Container()
        orchestrator = ProviderOrchestrator(container)

        # Create mock providers with different types
        provider1 = MockProvider1()
        provider2 = MockProvider2()
        provider3 = MockProvider3()

        orchestrator._providers.clear()
        orchestrator._providers.update({
            "provider1": provider1,
            "provider2": provider2,
            "provider3": provider3,
        })

        # Mock the compiled graph
        mock_graph = MagicMock()
        orchestrator._compiled_graph = mock_graph

        # Mock module class
        module_cls = MagicMock()

        # Return all provider entries (class-based providers)
        mock_graph.get_health_providers.return_value = [
            ProviderEntry(
                provider=MockProvider1,
                module_class=module_cls,
                module_name="TestModule",
                is_instance=False,
            ),
            ProviderEntry(
                provider=MockProvider2,
                module_class=module_cls,
                module_name="TestModule",
                is_instance=False,
            ),
            ProviderEntry(
                provider=MockProvider3,
                module_class=module_cls,
                module_name="TestModule",
                is_instance=False,
            ),
        ]

        result = orchestrator.get_module_health_providers(module_cls)

        assert len(result) == 3
        assert provider1 in result
        assert provider2 in result
        assert provider3 in result
        mock_graph.get_health_providers.assert_called_once_with(module_cls)

    def test_returns_empty_when_health_providers_empty_list(self) -> None:
        """Should return empty list when health_providers=[]."""
        container = Container()
        orchestrator = ProviderOrchestrator(container)

        # Create mock providers
        provider1 = MockProvider1()
        provider2 = MockProvider2()

        orchestrator._providers.clear()
        orchestrator._providers.update({
            "provider1": provider1,
            "provider2": provider2,
        })

        # Mock the compiled graph
        mock_graph = MagicMock()
        orchestrator._compiled_graph = mock_graph

        # Mock module class
        module_cls = MagicMock()

        # Return empty list (health_providers=[])
        mock_graph.get_health_providers.return_value = []

        result = orchestrator.get_module_health_providers(module_cls)

        assert result == []
        mock_graph.get_health_providers.assert_called_once_with(module_cls)

    def test_returns_specific_providers(self) -> None:
        """Should return only specified providers when health_providers=[X, Y]."""
        container = Container()
        orchestrator = ProviderOrchestrator(container)

        # Create mock providers with different types
        provider1 = MockProvider1()
        provider2 = MockProvider2()
        provider3 = MockProvider3()

        orchestrator._providers.clear()
        orchestrator._providers.update({
            "provider1": provider1,
            "provider2": provider2,
            "provider3": provider3,
        })

        # Mock the compiled graph
        mock_graph = MagicMock()
        orchestrator._compiled_graph = mock_graph

        # Mock module class
        module_cls = MagicMock()

        # Return only provider1 and provider3 (health_providers=[Provider1, Provider3])
        mock_graph.get_health_providers.return_value = [
            ProviderEntry(
                provider=MockProvider1,
                module_class=module_cls,
                module_name="TestModule",
                is_instance=False,
            ),
            ProviderEntry(
                provider=MockProvider3,
                module_class=module_cls,
                module_name="TestModule",
                is_instance=False,
            ),
        ]

        result = orchestrator.get_module_health_providers(module_cls)

        assert len(result) == 2
        assert provider1 in result
        assert provider3 in result
        assert provider2 not in result
        mock_graph.get_health_providers.assert_called_once_with(module_cls)

    def test_handles_instance_providers(self) -> None:
        """Should correctly match pre-instantiated providers (is_instance=True)."""
        container = Container()
        orchestrator = ProviderOrchestrator(container)

        # Create mock providers (simulating pre-instantiated)
        provider1 = MockProvider("provider1")
        provider2 = MockProvider("provider2")

        orchestrator._providers.clear()
        orchestrator._providers.update({
            "provider1": provider1,
            "provider2": provider2,
        })

        # Mock the compiled graph
        mock_graph = MagicMock()
        orchestrator._compiled_graph = mock_graph

        # Mock module class
        module_cls = MagicMock()

        # Return provider entry with is_instance=True (matches by identity)
        mock_graph.get_health_providers.return_value = [
            ProviderEntry(
                provider=provider1,  # The actual instance, not the type
                module_class=module_cls,
                module_name="TestModule",
                is_instance=True,
            ),
        ]

        result = orchestrator.get_module_health_providers(module_cls)

        assert len(result) == 1
        assert result[0] is provider1  # Identity match
        mock_graph.get_health_providers.assert_called_once_with(module_cls)

    def test_mixed_instance_and_class_providers(self) -> None:
        """Should handle both instance and class-based providers in the same module."""
        container = Container()
        orchestrator = ProviderOrchestrator(container)

        # Create mock providers
        provider1 = MockProvider("provider1")  # Will be instance-based
        provider2 = MockProvider2()  # Will be class-based (different type)

        orchestrator._providers.clear()
        orchestrator._providers.update({
            "provider1": provider1,
            "provider2": provider2,
        })

        # Mock the compiled graph
        mock_graph = MagicMock()
        orchestrator._compiled_graph = mock_graph

        # Mock module class
        module_cls = MagicMock()

        # Return mixed entry types
        mock_graph.get_health_providers.return_value = [
            ProviderEntry(
                provider=provider1,  # Instance
                module_class=module_cls,
                module_name="TestModule",
                is_instance=True,
            ),
            ProviderEntry(
                provider=MockProvider2,  # Class
                module_class=module_cls,
                module_name="TestModule",
                is_instance=False,
            ),
        ]

        result = orchestrator.get_module_health_providers(module_cls)

        assert len(result) == 2
        assert provider1 in result
        assert provider2 in result
        mock_graph.get_health_providers.assert_called_once_with(module_cls)
