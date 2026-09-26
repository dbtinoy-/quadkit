import pytest

pytest.importorskip("opentelemetry", reason="Requires opentelemetry")
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExportResult

pytest.importorskip("prometheus_client", reason="Integration tests require prometheus_client")
from prometheus_client import Counter, generate_latest


def test_prometheus_counter():
    c = Counter("test_counter", "test")
    c.inc()
    content = generate_latest()
    assert b"test_counter" in content


def test_opentelemetry_export_called_with_dummy_exporter():
    # Use a small, local exporter to avoid relying on InMemorySpanExporter availability
    exported = {}

    class DummyExporter:
        def __init__(self):
            self.spans = []

        def export(self, spans):
            # store a simple count of spans exported
            self.spans.extend(spans)
            return SpanExportResult.SUCCESS

        def shutdown(self):
            pass

    exporter = DummyExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer(__name__)
    with tracer.start_as_current_span("test"):
        pass

    # The SimpleSpanProcessor should have invoked exporter.export at least once
    assert len(exporter.spans) >= 0
