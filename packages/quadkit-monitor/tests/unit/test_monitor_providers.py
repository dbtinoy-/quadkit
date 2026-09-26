from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.contracts.core import HealthStatus
from quadkit.contracts.core.health import HealthCheckProtocol
from quadkit.contracts.observability.metrics import (
    HealthCheckRegistryProtocol,
    MetricsCollectorProtocol,
    MetricsFactoryProtocol,
    MetricsRecorderProtocol,
)
from quadkit.contracts.observability.tracing import TracerProtocol
from quadkit.monitor.di.provider import MonitorProvider
from quadkit.monitor.di.sub_providers.observability import ObservabilityProvider


class TestObservabilityProvider:
    """Tests for ObservabilityProvider (no-op fallback provider)."""

    @pytest.mark.asyncio
    async def test_register_binds_noop_collector(self) -> None:
        container = MagicMock()
        container.singleton = MagicMock()

        provider = ObservabilityProvider()
        await provider.register(container)

        calls = container.singleton.call_args_list
        types = [call[0][0] for call in calls]
        assert MetricsCollectorProtocol in types

    @pytest.mark.asyncio
    async def test_register_binds_noop_recorder(self) -> None:
        container = MagicMock()
        container.singleton = MagicMock()

        provider = ObservabilityProvider()
        await provider.register(container)

        calls = container.singleton.call_args_list
        types = [call[0][0] for call in calls]
        assert MetricsRecorderProtocol in types

    @pytest.mark.asyncio
    async def test_register_binds_noop_factory(self) -> None:
        container = MagicMock()
        container.singleton = MagicMock()

        provider = ObservabilityProvider()
        await provider.register(container)

        calls = container.singleton.call_args_list
        types = [call[0][0] for call in calls]
        assert MetricsFactoryProtocol in types

    @pytest.mark.asyncio
    async def test_register_binds_noop_tracer(self) -> None:
        container = MagicMock()
        container.singleton = MagicMock()

        provider = ObservabilityProvider()
        await provider.register(container)

        calls = container.singleton.call_args_list
        types = [call[0][0] for call in calls]
        assert TracerProtocol in types

    @pytest.mark.asyncio
    async def test_register_binds_noop_health_registry(self) -> None:
        container = MagicMock()
        container.singleton = MagicMock()

        provider = ObservabilityProvider()
        await provider.register(container)

        calls = container.singleton.call_args_list
        types = [call[0][0] for call in calls]
        assert HealthCheckRegistryProtocol in types

    @pytest.mark.asyncio
    async def test_register_binds_health_checker(self) -> None:
        container = MagicMock()
        container.singleton = MagicMock()

        provider = ObservabilityProvider()
        await provider.register(container)

        calls = container.singleton.call_args_list
        types = [call[0][0] for call in calls]
        assert HealthCheckProtocol in types

    @pytest.mark.asyncio
    async def test_register_binds_noop_instances(self) -> None:
        container = MagicMock()
        singleton_results = {}

        def capture_singleton(protocol, factory):
            if callable(factory):
                singleton_results[protocol] = factory()
            else:
                singleton_results[protocol] = factory

        container.singleton = capture_singleton

        provider = ObservabilityProvider()
        await provider.register(container)

        instances = list(singleton_results.values())
        instance_types = [type(i).__name__ for i in instances]
        assert "NoOpMetricsCollector" in instance_types
        assert "NoOpTracer" in instance_types
        assert "NoOpHealthCheckRegistry" in instance_types

    @pytest.mark.asyncio
    async def test_boot_does_nothing(self) -> None:
        container = MagicMock()
        provider = ObservabilityProvider()
        await provider.boot(container)

    @pytest.mark.asyncio
    async def test_shutdown_does_nothing(self) -> None:
        provider = ObservabilityProvider()
        await provider.shutdown()

    @pytest.mark.asyncio
    async def test_provider_priority(self) -> None:
        from quadkit.di.provider import ProviderPriority

        provider = ObservabilityProvider()
        assert provider.priority == ProviderPriority.INFRASTRUCTURE


class TestMonitorProvider:
    """Tests for MonitorProvider (full-featured monitoring provider)."""

    @pytest.fixture
    def mock_backend(self) -> MagicMock:
        backend = MagicMock()
        backend.initialize = AsyncMock()
        backend.shutdown = AsyncMock()
        return backend

    @pytest.fixture
    def provider(self, mock_backend: MagicMock) -> MonitorProvider:
        return MonitorProvider(backend=mock_backend)

    def test_provider_name(self, provider: MonitorProvider) -> None:
        assert provider.name == "monitor"

    def test_provider_priority(self, provider: MonitorProvider) -> None:
        from quadkit.di.provider import ProviderPriority

        assert provider.priority == ProviderPriority.INFRASTRUCTURE

    def test_provider_config_key(self, provider: MonitorProvider) -> None:
        assert provider.config_key == "monitor"

    def test_provider_config_model(self, provider: MonitorProvider) -> None:
        from quadkit.monitor.config import MonitorConfig

        assert provider.config_model == MonitorConfig

    def test_tracer_initialized_with_explicit_config(
        self, mock_backend: MagicMock
    ) -> None:
        from quadkit.monitor.config import MonitorConfig

        provider = MonitorProvider(backend=mock_backend, config=MonitorConfig())
        assert provider.tracer is not None

    def test_tracer_available_without_config(self, provider: MonitorProvider) -> None:
        """A provider always exposes a usable tracer (in-memory default)."""
        assert provider.tracer is not None

    def test_metrics_collector_initialized(
        self, provider: MonitorProvider
    ) -> None:
        assert provider.metrics_collector is not None

    def test_trace_provider_initialized_with_explicit_config(
        self, mock_backend: MagicMock
    ) -> None:
        from quadkit.monitor.config import MonitorConfig

        provider = MonitorProvider(backend=mock_backend, config=MonitorConfig())
        assert provider.trace_provider is not None

    def test_trace_provider_available_without_config(
        self, provider: MonitorProvider
    ) -> None:
        assert provider.trace_provider is not None

    @pytest.mark.asyncio
    async def test_register_binds_provider_singleton(
        self, provider: MonitorProvider
    ) -> None:
        container = MagicMock()
        container.singleton = MagicMock()

        await provider.register(container)

        calls = container.singleton.call_args_list
        types = [call[0][0] for call in calls]
        assert MonitorProvider in types

    @pytest.mark.asyncio
    async def test_register_binds_metrics_collector(
        self, provider: MonitorProvider
    ) -> None:
        from quadkit.monitor.metrics.collector import (
            MetricsCollectorProtocol as MonitorMetricsCollectorProtocol,
        )

        container = MagicMock()
        singleton_results = {}

        def capture_singleton(protocol, factory):
            if callable(factory):
                singleton_results[protocol] = factory
            else:
                singleton_results[protocol] = factory

        container.singleton = capture_singleton

        await provider.register(container)

        assert MonitorMetricsCollectorProtocol in singleton_results

    @pytest.mark.asyncio
    async def test_register_binds_metrics_recorder(
        self, provider: MonitorProvider
    ) -> None:
        container = MagicMock()
        container.singleton = MagicMock()

        await provider.register(container)

        calls = container.singleton.call_args_list
        types = [call[0][0] for call in calls]
        assert MetricsRecorderProtocol in types

    @pytest.mark.asyncio
    async def test_register_binds_metrics_factory(
        self, provider: MonitorProvider
    ) -> None:
        container = MagicMock()
        container.singleton = MagicMock()

        await provider.register(container)

        calls = container.singleton.call_args_list
        types = [call[0][0] for call in calls]
        assert MetricsFactoryProtocol in types

    @pytest.mark.asyncio
    async def test_register_binds_tracer_protocol(
        self, provider: MonitorProvider
    ) -> None:
        container = MagicMock()
        container.singleton = MagicMock()

        await provider.register(container)

        calls = container.singleton.call_args_list
        types = [call[0][0] for call in calls]
        assert TracerProtocol in types

    @pytest.mark.asyncio
    async def test_boot_initializes_backend(
        self, provider: MonitorProvider, mock_backend: MagicMock
    ) -> None:
        container = MagicMock()
        container.resolve_optional = AsyncMock(return_value=None)
        container.resolve = AsyncMock(return_value=None)

        await provider.boot(container)

        mock_backend.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_boot_creates_default_metrics(
        self, provider: MonitorProvider, mock_backend: MagicMock
    ) -> None:
        container = MagicMock()
        container.resolve_optional = AsyncMock(return_value=None)
        container.resolve = AsyncMock(return_value=None)

        await provider.boot(container)

        assert provider.metrics_collector.get_metric(
            "quadkit_requests_total"
        ) is not None
        assert provider.metrics_collector.get_metric(
            "quadkit_active_connections"
        ) is not None
        assert provider.metrics_collector.get_metric(
            "quadkit_request_duration_seconds"
        ) is not None

    @pytest.mark.asyncio
    async def test_shutdown_calls_backend_shutdown(
        self, provider: MonitorProvider, mock_backend: MagicMock
    ) -> None:
        await provider.shutdown()

        mock_backend.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_returns_healthy(
        self, provider: MonitorProvider
    ) -> None:
        result = await provider.health_check()

        assert result.component == "monitor"
        assert result.status == HealthStatus.HEALTHY
        assert "backend_type" in result.details

    @pytest.mark.asyncio
    async def test_health_check_returns_unhealthy_on_backend_error(
        self, provider: MonitorProvider, mocker
    ) -> None:
        class BackendWithHealthCheck:
            async def health_check(self):
                raise OSError("Connection failed")

        from quadkit.monitor.di import provider as provider_module

        mocker.patch.object(provider_module, "logger")
        import quadkit.monitor.di._metrics as _metrics_mod

        warning_spy = mocker.patch.object(_metrics_mod, "logger")
        provider.backend = BackendWithHealthCheck()

        result = await provider.health_check()

        assert result.status == HealthStatus.UNHEALTHY
        assert result.error == "OSError: connection check failed"
        assert "Connection failed" not in result.error
        warning_spy.warning.assert_called_once()
        assert warning_spy.warning.call_args.kwargs["error"] == "Connection failed"

    def test_record_request_increments_counter(
        self, provider: MonitorProvider
    ) -> None:
        provider.record_request("GET", "/test", 0.1, 200)

        counter = provider.metrics_collector.get_metric("quadkit_requests_total")
        assert counter is not None

    def test_record_request_records_histogram(
        self, provider: MonitorProvider
    ) -> None:
        provider.record_request("GET", "/test", 0.5, 200)

        histogram = provider.metrics_collector.get_metric(
            "quadkit_request_duration_seconds"
        )
        assert histogram is not None

    @pytest.mark.asyncio
    async def test_record_connection_change_after_boot(
        self, provider: MonitorProvider, mock_backend: MagicMock
    ) -> None:
        container = MagicMock()
        container.resolve_optional = AsyncMock(return_value=None)
        container.resolve = AsyncMock(return_value=None)

        await provider.boot(container)
        provider.record_connection_change(1)

        gauge = provider.metrics_collector.get_metric("quadkit_active_connections")
        assert gauge is not None

    def test_create_counter_delegates_to_collector(
        self, provider: MonitorProvider
    ) -> None:
        counter = provider.create_counter("test_counter", "Test counter")

        assert counter is not None
        assert provider.metrics_collector.get_metric("test_counter") is not None

    def test_create_gauge_delegates_to_collector(self, provider: MonitorProvider) -> None:
        gauge = provider.create_gauge("test_gauge", "Test gauge")

        assert gauge is not None
        assert provider.metrics_collector.get_metric("test_gauge") is not None

    def test_create_histogram_delegates_to_collector(
        self, provider: MonitorProvider
    ) -> None:
        histogram = provider.create_histogram(
            "test_histogram", "Test histogram", buckets=[0.1, 0.5, 1.0]
        )

        assert histogram is not None
        assert provider.metrics_collector.get_metric("test_histogram") is not None


class TestMonitorProviderFromConfig:
    """Tests for MonitorProvider.from_config factory method."""

    def test_from_config_returns_provider_instance(self) -> None:
        from quadkit.monitor.config import MonitorConfig

        config = MonitorConfig()

        with patch("quadkit.monitor.di.factories.create_provider_from_config") as factory:
            mock_provider = MagicMock(spec=MonitorProvider)
            factory.return_value = mock_provider

            provider = MonitorProvider.from_config(config)

            factory.assert_called_once_with(config)
            assert provider is mock_provider


class TestHookEventHelperFunctions:
    """Tests for helper functions in provider module."""

    def test_is_simple_hook_value(self) -> None:
        from quadkit.monitor.di.provider import _is_simple_hook_value

        assert _is_simple_hook_value(None) is True
        assert _is_simple_hook_value("string") is True
        assert _is_simple_hook_value(True) is True
        assert _is_simple_hook_value(123) is True
        assert _is_simple_hook_value(1.5) is True
        assert _is_simple_hook_value([1, 2, 3]) is False
        assert _is_simple_hook_value({"key": "value"}) is False

    def test_extract_payload_attributes_with_dataclass(self) -> None:
        from dataclasses import dataclass

        from quadkit.monitor.di.provider import _extract_payload_attributes

        @dataclass
        class TestPayload:
            name: str
            value: int

        payload = TestPayload(name="test", value=42)
        result = _extract_payload_attributes(payload)

        assert result == {"payload.name": "test", "payload.value": 42}

    def test_extract_payload_attributes_with_dict(self) -> None:
        from quadkit.monitor.di.provider import _extract_payload_attributes

        payload = {"key": "value", "count": 5}
        result = _extract_payload_attributes(payload)

        assert result == {"payload.key": "value", "payload.count": 5}

    def test_extract_payload_attributes_with_none(self) -> None:
        from quadkit.monitor.di.provider import _extract_payload_attributes

        assert _extract_payload_attributes(None) == {}

    def test_extract_payload_attributes_filters_non_simple(self) -> None:
        from quadkit.monitor.di.provider import _extract_payload_attributes

        payload = {"simple": "value", "complex": [1, 2, 3]}
        result = _extract_payload_attributes(payload)

        assert result == {"payload.simple": "value"}
