"""Tests for the core observability system."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from quadkit.contracts.core.health import HealthStatus
from quadkit.contracts.core.health import HealthCheckProtocol
from quadkit.contracts.observability.metrics import (
    HealthCheckRegistryProtocol,
    MetricProtocol,
    MetricsBackendProtocol,
    MetricsCollectorProtocol,
    MetricsFactoryProtocol,
    MetricsRecorderProtocol,
)
from quadkit.contracts.observability.tracing import SpanProtocol, TracerProtocol
from quadkit.observability.core import (
    NoOpHealthCheckRegistry,
    NoOpMetricsBackend,
    NoOpMetricsCollector,
    NoOpSpan,
    NoOpTracer,
)


class TestNoOpSpan:
    """Verify NoOpSpan satisfies SpanProtocol and stays inert."""

    def test_satisfies_span_protocol(self) -> None:
        span = NoOpSpan()
        assert isinstance(span, SpanProtocol)

    def test_set_attribute_is_noop(self) -> None:
        span = NoOpSpan()
        span.set_attribute("key", "value")
        assert span.attributes["key"] == "value"

    def test_add_event_is_noop(self) -> None:
        span = NoOpSpan()
        span.add_event("event", {"k": "v"})

    def test_record_exception_is_noop(self) -> None:
        span = NoOpSpan()
        span.record_exception(RuntimeError("test"))

    def test_set_status_is_noop(self) -> None:
        span = NoOpSpan()
        span.set_status("OK")


class TestNoOpTracer:
    """Verify NoOpTracer satisfies TracerProtocol and returns NoOpSpan."""

    def test_satisfies_tracer_protocol(self) -> None:
        tracer = NoOpTracer()
        assert isinstance(tracer, TracerProtocol)

    def test_start_span_returns_noop_span(self) -> None:
        tracer = NoOpTracer()
        span = tracer.start_span("test-span")
        assert isinstance(span, NoOpSpan)

    def test_start_span_with_attributes(self) -> None:
        tracer = NoOpTracer()
        span = tracer.start_span("test-span", attributes={"http.method": "GET"})
        assert isinstance(span, NoOpSpan)
        assert span.attributes == {"http.method": "GET"}

    def test_get_current_span_returns_none(self) -> None:
        tracer = NoOpTracer()
        assert tracer.get_current_span() is None

    def test_inject_context_is_noop(self) -> None:
        tracer = NoOpTracer()
        carrier = {"existing": "value"}
        tracer.inject_context(carrier)
        assert carrier == {"existing": "value"}

    def test_extract_context_returns_none(self) -> None:
        tracer = NoOpTracer()
        assert tracer.extract_context({"traceparent": "value"}) is None


class TestNoOpMetricsCollector:
    """Verify NoOpMetricsCollector satisfies all metrics contracts."""

    def test_satisfies_metrics_collector_protocol(self) -> None:
        collector = NoOpMetricsCollector()
        assert isinstance(collector, MetricsCollectorProtocol)

    def test_satisfies_metrics_recorder_protocol(self) -> None:
        collector = NoOpMetricsCollector()
        assert isinstance(collector, MetricsRecorderProtocol)

    def test_satisfies_metrics_factory_protocol(self) -> None:
        collector = NoOpMetricsCollector()
        assert isinstance(collector, MetricsFactoryProtocol)

    def test_satisfies_metric_protocol(self) -> None:
        collector = NoOpMetricsCollector()
        assert isinstance(collector, MetricProtocol)

    def test_increment_is_noop(self) -> None:
        collector = NoOpMetricsCollector()
        collector.increment("requests", 1.0, tags={"method": "GET"})

    def test_gauge_is_noop(self) -> None:
        collector = NoOpMetricsCollector()
        collector.gauge("temperature", 42.0)

    def test_histogram_is_noop(self) -> None:
        collector = NoOpMetricsCollector()
        collector.histogram("latency", 0.123)

    def test_create_counter_returns_self(self) -> None:
        collector = NoOpMetricsCollector()
        assert collector.create_counter("my_counter") is collector

    def test_create_gauge_returns_self(self) -> None:
        collector = NoOpMetricsCollector()
        assert collector.create_gauge("my_gauge") is collector

    def test_create_histogram_returns_self(self) -> None:
        collector = NoOpMetricsCollector()
        assert collector.create_histogram("my_hist") is collector

    def test_register_metric_is_noop(self) -> None:
        collector = NoOpMetricsCollector()
        collector.register_metric(NoOpMetricsCollector())

    def test_name_property(self) -> None:
        collector = NoOpMetricsCollector()
        assert collector.name == "noop"

    def test_record_is_noop(self) -> None:
        collector = NoOpMetricsCollector()
        collector.record(1.0, labels={"env": "test"})


class TestNoOpMetricsBackend:
    """Verify NoOpMetricsBackend satisfies the backend protocol."""

    def test_satisfies_metrics_backend_protocol(self) -> None:
        backend = NoOpMetricsBackend()
        assert isinstance(backend, MetricsBackendProtocol)

    @pytest.mark.asyncio
    async def test_initialize_and_shutdown_are_noops(self) -> None:
        backend = NoOpMetricsBackend()
        await backend.initialize()
        await backend.shutdown()

    def test_record_metric_is_noop(self) -> None:
        backend = NoOpMetricsBackend()
        backend.record_metric("requests", 1, "counter")


class TestNoOpHealthCheckRegistry:
    """Verify NoOpHealthCheckRegistry matches HealthCheckRegistryProtocol."""

    def test_satisfies_protocol(self) -> None:
        registry = NoOpHealthCheckRegistry()
        assert isinstance(registry, HealthCheckRegistryProtocol)

    def test_has_full_protocol_surface(self) -> None:
        registry = NoOpHealthCheckRegistry()
        assert hasattr(registry, "add")
        assert hasattr(registry, "run_all")
        assert hasattr(registry, "run_liveness")
        assert hasattr(registry, "run_readiness")
        assert hasattr(registry, "run_startup")

    @pytest.mark.asyncio
    async def test_run_methods_return_unknown_and_empty_details(self) -> None:
        registry = NoOpHealthCheckRegistry()
        status, details = await registry.run_all()
        assert status == HealthStatus.UNKNOWN
        assert details == {}


class TestObservabilityProvider:
    """Verify the core ObservabilityProvider registers no-op bindings."""

    def test_provider_name(self) -> None:
        from quadkit.observability.di.sub_providers.observability import (
            ObservabilityProvider,
        )

        provider = ObservabilityProvider()
        assert provider.name == "observability"

    @pytest.mark.asyncio
    async def test_registers_noop_bindings(self) -> None:
        from quadkit.observability.di.sub_providers.observability import (
            ObservabilityProvider,
        )

        provider = ObservabilityProvider()
        container = MagicMock()
        container.has.return_value = False
        await provider.register(container)

        bound_abstracts = [c.args[0] for c in container.singleton.call_args_list]
        assert MetricsCollectorProtocol in bound_abstracts
        assert MetricsRecorderProtocol in bound_abstracts
        assert MetricsFactoryProtocol in bound_abstracts
        assert TracerProtocol in bound_abstracts
        assert HealthCheckRegistryProtocol in bound_abstracts
        assert HealthCheckProtocol in bound_abstracts

    @pytest.mark.asyncio
    async def test_registers_noop_instances(self) -> None:
        from quadkit.observability.di.sub_providers.observability import (
            ObservabilityProvider,
        )

        provider = ObservabilityProvider()
        singleton_results = {}

        def capture_singleton(protocol, factory):
            singleton_results[protocol] = factory() if callable(factory) else factory
            return None

        container = MagicMock()
        container.has.return_value = False
        container.singleton = capture_singleton

        await provider.register(container)

        instance_types = {type(instance).__name__ for instance in singleton_results.values()}
        assert "NoOpMetricsCollector" in instance_types
        assert "NoOpTracer" in instance_types
        assert "NoOpHealthCheckRegistry" in instance_types

    @pytest.mark.asyncio
    async def test_boot_does_nothing(self) -> None:
        from quadkit.observability.di.sub_providers.observability import (
            ObservabilityProvider,
        )

        provider = ObservabilityProvider()
        await provider.boot(MagicMock())

    @pytest.mark.asyncio
    async def test_shutdown_does_nothing(self) -> None:
        from quadkit.observability.di.sub_providers.observability import (
            ObservabilityProvider,
        )

        provider = ObservabilityProvider()
        await provider.shutdown()

    @pytest.mark.asyncio
    async def test_provider_priority(self) -> None:
        from quadkit.di.provider import ProviderPriority
        from quadkit.observability.di.sub_providers.observability import (
            ObservabilityProvider,
        )

        provider = ObservabilityProvider()
        assert provider.priority == ProviderPriority.INFRASTRUCTURE

    @pytest.mark.asyncio
    async def test_registers_six_singletons(self) -> None:
        from quadkit.observability.di.sub_providers.observability import (
            ObservabilityProvider,
        )

        provider = ObservabilityProvider()
        container = MagicMock()
        container.has.return_value = False
        await provider.register(container)

        assert container.singleton.call_count == 6

    @pytest.mark.asyncio
    async def test_skips_tokens_a_real_implementation_already_holds(self) -> None:
        """Fallback bindings must not overwrite an already-registered token.

        The container keeps the last registration; an unconditional register
        here let composition order decide the winner, and nested module graphs
        can land the no-op *after* a real implementation.
        """
        from quadkit.observability.di.sub_providers.observability import (
            ObservabilityProvider,
        )

        provider = ObservabilityProvider()
        container = MagicMock()
        container.has.return_value = True
        await provider.register(container)

        assert container.singleton.call_count == 0

    @pytest.mark.asyncio
    async def test_only_missing_tokens_are_filled(self) -> None:
        """A partially populated container gets the remaining five no-ops."""
        from quadkit.observability.di.sub_providers.observability import (
            ObservabilityProvider,
        )

        provider = ObservabilityProvider()
        container = MagicMock()
        container.has.side_effect = (
            lambda service_type: service_type is MetricsCollectorProtocol
        )
        await provider.register(container)

        bound_abstracts = [c.args[0] for c in container.singleton.call_args_list]
        assert bound_abstracts == [
            MetricsRecorderProtocol,
            MetricsFactoryProtocol,
            TracerProtocol,
            HealthCheckRegistryProtocol,
            HealthCheckProtocol,
        ]


class TestPackageExports:
    """Verify the observability package exports the canonical no-op classes."""

    def test_exports_all_noop_classes(self) -> None:
        import quadkit.observability as obs

        assert hasattr(obs, "NoOpSpan")
        assert hasattr(obs, "NoOpTracer")
        assert hasattr(obs, "NoOpMetricsCollector")
        assert hasattr(obs, "NoOpMetricsBackend")
        assert hasattr(obs, "NoOpHealthCheckRegistry")
        assert hasattr(obs, "ObservabilityProvider")
