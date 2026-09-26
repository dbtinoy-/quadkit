
from quadkit.monitor.config import MonitorConfig
from quadkit.monitor.health import HealthCheckRegistry
from quadkit.monitor.di.factories import create_provider_from_config


class DummyContainer:
    """Minimal container double.

    Mirrors the real Container's lazy-factory semantics: a factory passed
    to ``singleton()`` is stored and only invoked on first ``resolve()``
    (not eagerly at registration time), matching production behavior for
    providers that register a "not ready until boot()" factory (e.g.
    ``VectorProvider._get_store``, ``GraphProvider._resolve_default_graph``,
    ``MonitorProvider._resolve_slo_monitor``).
    """

    def __init__(self):
        self.mapping = {}
        self._factories = {}
        self._resolved = {}

    def singleton(self, key, factory):
        if callable(factory):
            self._factories[key] = factory
        else:
            self.mapping[key] = factory
            self._resolved[key] = factory

    async def resolve(self, cls):
        if cls in self._resolved:
            return self._resolved[cls]
        if cls in self._factories:
            value = self._factories[cls]()
            self._resolved[cls] = value
            self.mapping[cls] = value
            return value
        if cls in self.mapping:
            return self.mapping[cls]
        raise RuntimeError("Not registered")

    def has(self, cls):
        return cls in self.mapping or cls in self._factories


class DummyExporter:
    def __init__(self):
        self.exported = []

    def export(self, spans):
        self.exported.append(list(spans))


def test_provider_tracer_respects_max_spans_config():
    # Small cap to trigger auto-flush
    cfg = MonitorConfig(tracing={"max_spans": 3, "service_name": "svc"})

    provider = create_provider_from_config(cfg)

    # Replace exporter with a test double
    exporter = DummyExporter()
    provider.tracer.exporter = exporter

    # Create spans exceeding the max_spans threshold
    for i in range(4):
        provider.tracer.start_span(f"s{i}")

    assert len(exporter.exported) >= 1


import pytest

@pytest.mark.asyncio
async def test_register_provides_health_check_registry():
    cfg = MonitorConfig()
    provider = create_provider_from_config(cfg)

    container = DummyContainer()
    # Ensure initial absence
    assert not container.has(HealthCheckRegistry)

    await provider.register(container)

    assert container.has(HealthCheckRegistry)
    resolved = await container.resolve(HealthCheckRegistry)
    assert isinstance(resolved, HealthCheckRegistry)


@pytest.mark.asyncio
async def test_tracer_registered_in_di_and_no_global_helpers():
    """Ensure Tracer is registered via DI and no global helpers remain."""
    cfg = MonitorConfig(tracing={"max_spans": 3, "service_name": "svc-di"})
    provider = create_provider_from_config(cfg)

    container = DummyContainer()
    await provider.register(container)

    # Tracer should be registered in the container
    from quadkit.monitor.tracing import Tracer

    assert container.has(Tracer)
    tracer = await container.resolve(Tracer)
    assert tracer.service_name == "svc-di"

    # Replace exporter to observe auto-flush behavior
    exporter = DummyExporter()
    tracer.exporter = exporter
    for i in range(4):
        tracer.start_span(f"s{i}")
    assert len(exporter.exported) >= 1

    # Ensure no module-level global helpers are present
    import importlib

    tracing_mod = importlib.import_module("quadkit.monitor.tracing")
    assert not hasattr(tracing_mod, "get_tracer")
    assert not hasattr(tracing_mod, "set_tracer")
