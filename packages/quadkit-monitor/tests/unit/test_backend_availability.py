import importlib.util
import pathlib
import types

import pytest


def _load_module_from_path(path: pathlib.Path, name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _load_exceptions(monkeypatch):
    # Load exceptions module directly to avoid importing the full package
    path = (
        pathlib.Path(__file__).resolve().parents[2]
        / "src"
        / "quadkit"
        / "monitor"
        / "exceptions.py"
    )
    mod = _load_module_from_path(path, "_test_exceptions")
    # Install the exceptions module in sys.modules under the package path so
    # relative imports performed by backend modules succeed.
    import sys

    sys.modules.setdefault("quadkit.monitor.exceptions", mod)
    return getattr(mod, "BackendNotAvailableError")


def test_opentelemetry_backend_raises_when_missing(monkeypatch):
    BackendNotAvailableError = _load_exceptions(monkeypatch)

    path = (
        pathlib.Path(__file__).resolve().parents[2]
        / "src"
        / "quadkit"
        / "monitor"
        / "backends"
        / "opentelemetry.py"
    )

    # Prepare minimal package context so relative imports in the backend module work
    import sys
    import types

    sys.modules.setdefault("quadkit", types.ModuleType("quadkit"))
    sys.modules.setdefault("quadkit.monitor", types.ModuleType("quadkit.monitor"))

    # Minimal placeholder for monitor.protocols
    protocols_mod = sys.modules.setdefault(
        "quadkit.monitor.protocols", types.ModuleType("quadkit.monitor.protocols"),
    )
    protocols_mod.MonitoringBackend = object

    # Minimal placeholder for monitor.types (Span, SpanContext)
    types_mod = sys.modules.setdefault(
        "quadkit.monitor.types", types.ModuleType("quadkit.monitor.types"),
    )

    class SpanContext:
        def __init__(self, trace_id: str, span_id: str):
            self.trace_id = trace_id
            self.span_id = span_id

    class Span:
        def __init__(self, name: str, context: SpanContext, start_time: float):
            self.name = name
            self.context = context
            self.start_time = start_time

    types_mod.Span = Span
    types_mod.SpanContext = SpanContext

    mod = _load_module_from_path(path, "quadkit.monitor.backends._test_opentelemetry")
    # Ensure we have the expected exception symbol
    assert hasattr(mod, "OpenTelemetryBackend")

    # Simulate missing dependency
    monkeypatch.setattr(mod, "HAS_OPENTELEMETRY", False)

    with pytest.raises(Exception) as exc:
        mod.OpenTelemetryBackend()

    assert "Install with: pip install quadkit-monitor[otel]" in str(exc.value)


def test_prometheus_backend_raises_when_missing(monkeypatch):
    BackendNotAvailableError = _load_exceptions(monkeypatch)

    path = (
        pathlib.Path(__file__).resolve().parents[2]
        / "src"
        / "quadkit"
        / "monitor"
        / "backends"
        / "prometheus.py"
    )

    # Prepare minimal package context so relative imports in the backend module work
    import sys
    import types

    sys.modules.setdefault("quadkit", types.ModuleType("quadkit"))
    sys.modules.setdefault("quadkit.monitor", types.ModuleType("quadkit.monitor"))

    # Minimal placeholder for monitor.protocols
    protocols_mod = sys.modules.setdefault(
        "quadkit.monitor.protocols", types.ModuleType("quadkit.monitor.protocols"),
    )
    protocols_mod.MonitoringBackend = object

    # Minimal placeholder for monitor.types (Span, SpanContext)
    types_mod = sys.modules.setdefault(
        "quadkit.monitor.types", types.ModuleType("quadkit.monitor.types"),
    )

    class SpanContext:
        def __init__(self, trace_id: str, span_id: str):
            self.trace_id = trace_id
            self.span_id = span_id

    class Span:
        def __init__(self, name: str, context: SpanContext, start_time: float):
            self.name = name
            self.context = context
            self.start_time = start_time

    types_mod.Span = Span
    types_mod.SpanContext = SpanContext

    mod = _load_module_from_path(path, "quadkit.monitor.backends._test_prometheus")
    assert hasattr(mod, "PrometheusBackend")

    monkeypatch.setattr(mod, "HAS_PROMETHEUS", False)

    with pytest.raises(Exception) as exc:
        mod.PrometheusBackend()

    assert "Install with: pip install quadkit-monitor[prometheus]" in str(exc.value)
