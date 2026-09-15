from __future__ import annotations

from quadkit.testing.fakes import FakeTracer


def test_fake_tracer_injects_and_extracts_traceparent() -> None:
    tracer = FakeTracer()
    headers: dict[str, str] = {}

    span = tracer.start_span("queue.publish jobs")
    tracer.inject_context(headers, span.context)
    extracted = tracer.extract_context(headers)

    assert extracted is not None
    assert headers["traceparent"].startswith("00-")
