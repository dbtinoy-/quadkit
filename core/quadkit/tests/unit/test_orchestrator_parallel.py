import asyncio
import time
import pytest
from quadkit.di.orchestrator import ProviderOrchestrator
from quadkit.di.container import Container
from quadkit.di.provider import Provider

class ParallelProvider(Provider):
    def __init__(self, name: str, delay: float = 0.1, dependencies: list[str] | None = None):
        super().__init__(name=name)
        self.delay = delay
        self._dependencies = dependencies or []
        self.register_time = 0.0
        self.boot_time = 0.0
        self.shutdown_time = 0.0

    @property
    def dependencies(self) -> list[str]:
        return self._dependencies

    async def register(self, container):
        await asyncio.sleep(self.delay)
        self.register_time = time.perf_counter()

    async def boot(self, container):
        await asyncio.sleep(self.delay)
        self.boot_time = time.perf_counter()

    async def shutdown(self):
        await asyncio.sleep(self.delay)
        self.shutdown_time = time.perf_counter()

@pytest.mark.asyncio
async def test_parallel_registration():
    container = Container()
    orchestrator = ProviderOrchestrator(container)
    
    # Three independent providers
    p1 = ParallelProvider("p1", delay=0.2)
    p2 = ParallelProvider("p2", delay=0.2)
    p3 = ParallelProvider("p3", delay=0.2)
    
    orchestrator.add(p1)
    orchestrator.add(p2)
    orchestrator.add(p3)
    
    start = time.perf_counter()
    await orchestrator.register_all()
    end = time.perf_counter()
    
    elapsed = end - start
    # If parallel, total time should be ~0.2s, not ~0.6s
    assert elapsed < 0.4
    assert p1.register_time > 0
    assert p2.register_time > 0
    assert p3.register_time > 0

@pytest.mark.asyncio
async def test_parallel_shutdown():
    container = Container()
    orchestrator = ProviderOrchestrator(container)
    
    # p1 and p2 are independent. p3 depends on BOTH.
    # Shutdown order: p3 first, then (p1, p2) in parallel.
    p1 = ParallelProvider("p1", delay=0.2)
    p2 = ParallelProvider("p2", delay=0.2)
    p3 = ParallelProvider("p3", delay=0.2, dependencies=["p1", "p2"])
    
    orchestrator.add(p1)
    orchestrator.add(p2)
    orchestrator.add(p3)
    
    await orchestrator.register_all()
    await orchestrator.boot_all(container)
    
    start = time.perf_counter()
    await orchestrator.shutdown()
    end = time.perf_counter()
    
    elapsed = end - start
    # Level 2 (p3) takes 0.2s. Level 1 (p1, p2) takes 0.2s parallel.
    # Total should be ~0.4s, not ~0.6s.
    assert 0.35 < elapsed < 0.55
    
    # Verify p3 shut down BEFORE p1 and p2 started shutting down
    assert p3.shutdown_time < p1.shutdown_time
    assert p3.shutdown_time < p2.shutdown_time
    
    # Verify p1 and p2 shut down roughly at the same time (parallel)
    assert abs(p1.shutdown_time - p2.shutdown_time) < 0.1

@pytest.mark.asyncio
async def test_dependency_order_maintained():
    container = Container()
    orchestrator = ProviderOrchestrator(container)
    
    p1 = ParallelProvider("p1", delay=0.1)
    p2 = ParallelProvider("p2", delay=0.1, dependencies=["p1"])
    
    orchestrator.add(p1)
    orchestrator.add(p2)
    
    # Registration
    await orchestrator.register_all()
    assert p1.register_time < p2.register_time
    
    # Booting (already parallelized, but good to check)
    await orchestrator.boot_all(container)
    assert p1.boot_time < p2.boot_time
    
    # Shutdown (reverse order)
    await orchestrator.shutdown()
    assert p2.shutdown_time < p1.shutdown_time
