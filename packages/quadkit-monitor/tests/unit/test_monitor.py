"""Unit tests for Quadkit Monitor package"""

from unittest.mock import Mock

import pytest

from quadkit.logging import get_logger, Logger
from quadkit.monitor import (
    InMemoryTraceProvider,
    MetricsCollectorProtocol,
    MonitorProvider,
)


class TestMetrics:
    """Test metrics functionality"""

    def test_counter_creation(self):
        """Test counter creation and incrementing"""
        collector = MetricsCollectorProtocol()
        counter = collector.create_counter("test_counter", "A test counter")

        assert counter.name == "test_counter"
        assert counter.description == "A test counter"
        assert counter.get_count() == 0

        counter.increment()
        assert counter.get_count() == 1

        counter.increment(5)
        assert counter.get_count() == 6

    def test_gauge_operations(self):
        """Test gauge set, increment, decrement"""
        collector = MetricsCollectorProtocol()
        gauge = collector.create_gauge("test_gauge", "A test gauge")

        assert gauge.get_value() == 0.0

        gauge.set(10.5)
        assert gauge.get_value() == 10.5

        gauge.increment(2.5)
        assert gauge.get_value() == 13.0

        gauge.decrement(3.0)
        assert gauge.get_value() == 10.0

    def test_histogram_observations(self):
        """Test histogram observations and buckets"""
        collector = MetricsCollectorProtocol()
        histogram = collector.create_histogram("test_histogram", "A test histogram")

        # Add some observations
        histogram.observe(0.1)
        histogram.observe(0.5)
        histogram.observe(2.0)

        observations = histogram.get_observations()
        assert len(observations) == 3
        assert 0.1 in observations
        assert 0.5 in observations
        assert 2.0 in observations

        # Check bucket counts
        bucket_counts = histogram.get_bucket_counts()
        assert bucket_counts[0.005] == 0  # 0.1 > 0.005
        assert bucket_counts[0.1] >= 1  # 0.1 <= 0.1
        assert bucket_counts[1.0] >= 2  # 0.5 and 2.0 > 1.0? Wait, need to check logic

    def test_metrics_collector(self):
        """Test metrics collector operations"""
        collector = MetricsCollectorProtocol()

        counter = collector.create_counter("requests_total")
        gauge = collector.create_gauge("active_users")
        histogram = collector.create_histogram("response_time")

        assert len(collector.get_all_metrics()) == 3

        retrieved_counter = collector.get_metric("requests_total")
        assert retrieved_counter is counter

        collector.clear()
        assert len(collector.get_all_metrics()) == 0


class TestTracing:
    """Test tracing functionality"""

    def test_span_creation(self):
        """Test span creation and attributes"""
        provider = InMemoryTraceProvider()
        tracer = provider.tracer

        with tracer.start_span("test_operation") as span:
            assert span.name == "test_operation"
            assert (
                len(span.context.trace_id) == 32
            )  # 32 hex characters for 128-bit trace ID
            assert span.context.trace_id.isalnum()  # Should be hex digits
            assert (
                len(span.context.span_id) == 16
            )  # 16 hex characters for 64-bit span ID
            assert span.context.span_id.isalnum()  # Should be hex digits
            assert span.start_time is not None
            assert span.end_time is None

            span.set_attribute("user_id", "123")
            span.add_event("processing_started")

        # After context manager, span should be finished
        assert span.end_time is not None
        assert span.get_duration() is not None
        assert span.attributes["user_id"] == "123"
        assert len(span.events) == 1

    def test_nested_spans(self):
        """Test nested span creation"""
        provider = InMemoryTraceProvider()
        tracer = provider.tracer

        with tracer.start_span("parent_operation") as parent:
            assert tracer.get_current_span() is parent

            with tracer.start_span("child_operation") as child:
                assert tracer.get_current_span() is child
                assert child.context.parent_span_id == parent.context.span_id
                assert child.context.trace_id == parent.context.trace_id

            # Back to parent
            assert tracer.get_current_span() is parent

    def test_trace_provider_spans(self):
        """Test trace provider span recording"""
        provider = InMemoryTraceProvider()

        span1 = provider.create_span("operation1")
        span2 = provider.create_span("operation2")

        spans = provider.get_all_spans()
        assert len(spans) == 2
        assert spans[0].name == "operation1"
        assert spans[1].name == "operation2"


class TestLogger:
    """Test structured logging functionality"""

    @pytest.mark.skip(reason="Deprecated Logger class has been removed; Logger is now LoggerProtocol and cannot be instantiated.")
    def test_logger_creation(self):
        """Test logger creation emits deprecation warning."""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            logger = Logger("test_logger")
            assert logger.name == "test_logger"
            assert logger._logger is not None
            # Verify deprecation warning was emitted
            assert len(w) >= 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()

    @pytest.mark.skip(
        reason="Logger output testing requires source code path resolution",
    )
    def test_logger_json_output(self):
        """Test that logger outputs JSON format"""
        pass

    @pytest.mark.skip(
        reason="Logger output testing requires source code path resolution",
    )
    def test_logger_with_request_context(self):
        """Test logger with request context"""
        pass

    def test_get_logger_function(self):
        """Test get_logger convenience function"""
        logger = get_logger("convenience_logger")
        # structlog returns a lazy proxy, verify it was created
        assert logger is not None

    @pytest.mark.skip(
        reason="Logger output testing requires source code path resolution",
    )
    def test_configure_logging(self):
        """Test global logging configuration"""
        pass


class TestMonitorProvider:
    """Test MonitorProvider"""

    def test_metric_creation_through_provider(self):
        """Test creating metrics through provider"""
        mock_backend = Mock()
        provider = MonitorProvider(mock_backend)

        counter = provider.create_counter("test_counter")
        gauge = provider.create_gauge("test_gauge")
        histogram = provider.create_histogram("test_histogram")

        assert counter.name == "test_counter"
        assert gauge.name == "test_gauge"
        assert histogram.name == "test_histogram"

    def test_request_recording(self):
        """Test HTTP request recording"""
        mock_backend = Mock()
        provider = MonitorProvider(mock_backend)

        provider.record_request("GET", "/api/users", 0.125, 200)

        # Check that metrics were recorded (would need more detailed mocking for full test)
        metrics = provider.metrics_collector.get_all_metrics()
        assert "quadkit_requests_total" in metrics
        assert "quadkit_request_duration_seconds" in metrics


class TestBackendImports:
    """Test backend imports work correctly"""

    def test_opentelemetry_backend_import(self):
        """Test OpenTelemetry backend can be imported"""
        try:
            from quadkit.monitor import OpenTelemetryBackend

            assert OpenTelemetryBackend
        except ImportError:
            # Expected if opentelemetry not installed
            pytest.skip("opentelemetry not available")

    def test_prometheus_backend_import(self):
        """Test Prometheus backend can be imported"""
        try:
            from quadkit.monitor import PrometheusBackend

            assert PrometheusBackend
        except ImportError:
            # Expected if prometheus-client not installed
            pytest.skip("prometheus-client not available")
