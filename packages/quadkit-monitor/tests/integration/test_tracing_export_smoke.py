import pytest


@pytest.mark.asyncio
async def test_opentelemetry_backend_initialize_and_trace():
    try:
        from quadkit.monitor.backends.opentelemetry import (
            HAS_OPENTELEMETRY,
            OpenTelemetryBackend,
        )
    except ImportError:
        pytest.skip("OpenTelemetry backend module not importable")

    if not HAS_OPENTELEMETRY:
        pytest.skip("OpenTelemetry not installed in this environment")

    backend = OpenTelemetryBackend(service_name="quadkit-smoke", endpoint=None)

    # Should initialize without raising (even if OTLP exporters are not available)
    await backend.initialize()

    # After initialize we should have a tracer we can use to start a span
    assert hasattr(backend, "tracer") and backend.tracer is not None

    # Use tracer to create a span - ensure no exceptions are raised
    with backend.tracer.start_as_current_span("smoke-test"):
        pass

    # Shutdown should complete without error
    await backend.shutdown()
