import os
import sys
from pathlib import Path

# Ensure local package src is importable for these unit tests
root = Path(__file__).parent.parent.resolve()
src = root / "src"

from quadkit.monitor.tracing import Tracer


class DummyExporter:
    def __init__(self):
        self.exported = []

    def export(self, spans):
        # store a shallow copy so we can assert after flush
        self.exported.append(list(spans))


def test_tracer_auto_flush():
    exporter = DummyExporter()
    # small cap to trigger auto-flush in test
    tracer = Tracer("test-service", exporter, max_spans=5)

    # Create spans exceeding the max_spans threshold
    for i in range(6):
        tracer.start_span(f"s{i}")

    # Auto-flush should have occurred at least once
    assert len(exporter.exported) >= 1

    # After auto-flush, internal buffer should be below capacity
    assert len(tracer.get_all_spans()) < tracer._max_spans
