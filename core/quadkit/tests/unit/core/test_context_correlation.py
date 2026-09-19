"""Tests for RequestContext correlation_id and causation_id propagation."""

from __future__ import annotations

from quadkit.primitives.context import (
    CAUSATION_ID,
    CORRELATION_ID,
    RequestContext,
    create_default_context,
    request_scope,
)


class TestCorrelationIdDefault:
    def test_correlation_id_is_none_outside_context(self) -> None:
        ctx = create_default_context()
        assert ctx.get(CORRELATION_ID) is None

    def test_causation_id_is_none_outside_context(self) -> None:
        ctx = create_default_context()
        assert ctx.get(CAUSATION_ID) is None


class TestRequestContextCorrelationId:
    def test_sets_correlation_id_within_context(self) -> None:
        ctx = create_default_context()
        with RequestContext(ctx.registry, correlation_id="trace-abc"):
            assert ctx.get(CORRELATION_ID) == "trace-abc"

    def test_correlation_id_reset_after_context(self) -> None:
        ctx = create_default_context()
        with RequestContext(ctx.registry, correlation_id="trace-abc"):
            pass
        assert ctx.get(CORRELATION_ID) is None

    def test_sets_causation_id_within_context(self) -> None:
        ctx = create_default_context()
        with RequestContext(ctx.registry, causation_id="cause-xyz"):
            assert ctx.get(CAUSATION_ID) == "cause-xyz"

    def test_causation_id_reset_after_context(self) -> None:
        ctx = create_default_context()
        with RequestContext(ctx.registry, causation_id="cause-xyz"):
            pass
        assert ctx.get(CAUSATION_ID) is None

    def test_sets_both_ids_simultaneously(self) -> None:
        ctx = create_default_context()
        with RequestContext(ctx.registry, correlation_id="corr-1", causation_id="cause-1"):
            assert ctx.get(CORRELATION_ID) == "corr-1"
            assert ctx.get(CAUSATION_ID) == "cause-1"


class TestConvenienceFunctions:
    def test_set_and_get_correlation_id(self) -> None:
        ctx = create_default_context()
        token = ctx.set(CORRELATION_ID, "my-correlation")
        try:
            assert ctx.get(CORRELATION_ID) == "my-correlation"
        finally:
            ctx.registry.resolve_var(CORRELATION_ID).reset(token)

    def test_set_and_get_causation_id(self) -> None:
        ctx = create_default_context()
        token = ctx.set(CAUSATION_ID, "my-causation")
        try:
            assert ctx.get(CAUSATION_ID) == "my-causation"
        finally:
            ctx.registry.resolve_var(CAUSATION_ID).reset(token)


class TestRequestContextFactory:
    def test_request_context_factory_sets_correlation_id(self) -> None:
        ctx = create_default_context()
        with request_scope(ctx.registry, correlation_id="factory-corr"):
            assert ctx.get(CORRELATION_ID) == "factory-corr"

    def test_request_context_factory_correlation_id_cleaned_up(self) -> None:
        ctx = create_default_context()
        with request_scope(ctx.registry, correlation_id="factory-corr"):
            pass
        assert ctx.get(CORRELATION_ID) is None

    def test_request_context_factory_sets_causation_id(self) -> None:
        ctx = create_default_context()
        with request_scope(ctx.registry, causation_id="factory-cause"):
            assert ctx.get(CAUSATION_ID) == "factory-cause"

