
import pytest

from quadkit.di.container import Container
from quadkit.di.orchestrator import ProviderOrchestrator
from quadkit.di.provider import Provider
from quadkit.di.types import ProviderPriority, ProviderState


class MockProvider(Provider):
    def __init__(self, name, priority=ProviderPriority.NORMAL, dependencies=()):
        super().__init__(name=name, priority=priority, dependencies=dependencies)
        self.boot_called = False
        self.shutdown_called = False
        self._sub_providers = []

    @property
    def sub_providers(self):
        return self._sub_providers

    async def boot(self, container):
        self.boot_called = True

    async def shutdown(self):
        self.shutdown_called = True

class FailingProvider(MockProvider):
    async def boot(self, container):
        raise RuntimeError("Boot failed")

@pytest.mark.asyncio
async def test_recursive_discovery():
    container = Container()
    orchestrator = ProviderOrchestrator(container)

    root = MockProvider("root")
    sub1 = MockProvider("sub1")
    sub2 = MockProvider("sub2")

    root._sub_providers = [sub1, sub2]

    orchestrator.add(root)

    assert "root" in orchestrator._providers
    assert "sub1" in orchestrator._providers
    assert "sub2" in orchestrator._providers

@pytest.mark.asyncio
async def test_rollback_on_failure():
    container = Container()
    orchestrator = ProviderOrchestrator(container)

    p1 = MockProvider("p1")
    p2 = FailingProvider("p2", dependencies=("p1",))

    orchestrator.add(p1)
    orchestrator.add(p2)

    with pytest.raises(RuntimeError, match="Boot failed"):
        await orchestrator.boot_all(container)

    assert p1.boot_called is True
    assert p1.shutdown_called is True
    assert p1.state == ProviderState.REGISTERED
    assert p2.state == ProviderState.REGISTERED

@pytest.mark.asyncio
async def test_boot_levels():
    container = Container()
    orchestrator = ProviderOrchestrator(container)

    # Layer 0
    p1 = MockProvider("p1", priority=ProviderPriority.INFRASTRUCTURE)
    # Layer 1 (depends on p1)
    p2 = MockProvider("p2", dependencies=("p1",))
    # Layer 1 (depends on p1)
    p3 = MockProvider("p3", dependencies=("p1",))

    orchestrator.add(p1)
    orchestrator.add(p2)
    orchestrator.add(p3)

    ordered = orchestrator._graph.topological_sort()
    levels = orchestrator._graph.compute_boot_levels(ordered)

    assert len(levels) == 2
    assert levels[0] == [p1]
    assert set(levels[1]) == {p2, p3}


@pytest.mark.asyncio
async def test_boot_levels_split_ready_providers_by_priority():
    container = Container()
    orchestrator = ProviderOrchestrator(container)

    application_provider = MockProvider(
        "application",
        priority=ProviderPriority.APPLICATION,
    )
    presentation_provider = MockProvider(
        "presentation",
        priority=ProviderPriority.PRESENTATION,
    )

    orchestrator.add(application_provider)
    orchestrator.add(presentation_provider)

    ordered = orchestrator._graph.topological_sort()
    levels = orchestrator._graph.compute_boot_levels(ordered)

    assert levels == [[application_provider], [presentation_provider]]


@pytest.mark.asyncio
async def test_boot_all_raises_on_container_validation_issues():
    """boot_all must raise ContainerValidationError when validate() reports issues."""
    from unittest.mock import patch

    from quadkit.contracts.exceptions.container import ContainerValidationError

    container = Container()
    orchestrator = ProviderOrchestrator(container)
    orchestrator.add(MockProvider("p1"))

    # Simulate container.validate() returning a problem
    with patch.object(container, "validate", return_value=["Scope violation: Singleton 'A' depends on scoped 'B'"]), pytest.raises(ContainerValidationError) as exc_info:
        await orchestrator.boot_all(container)

    assert "Scope violation" in str(exc_info.value)
    assert exc_info.value.issues == ["Scope violation: Singleton 'A' depends on scoped 'B'"]
