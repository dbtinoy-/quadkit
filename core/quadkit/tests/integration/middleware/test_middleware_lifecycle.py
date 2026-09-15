"""Integration tests for middleware pipeline lifecycle.

Tests the complete end-to-end flow:
1. Create and register (add) middleware to a chain
2. Build the chain into an immutable pipeline
3. Execute the pipeline with a context and handler
4. Verify all middleware execute in correct order with proper context passing

This test demonstrates that the middleware chain lifecycle works end-to-end:
- Mutable MiddlewareChain allows incremental registration
- Build produces immutable MiddlewarePipeline
- Pipeline correctly chains middleware execution
- All middleware see the same context and can transform it
"""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.middleware.builtins import (
    CircuitBreakerMiddleware,
    ConditionalMiddleware,
    LoggingMiddleware,
    TimeoutMiddleware,
    TimingMiddleware,
)
from quadkit.middleware.core.chain import MiddlewareChain
from quadkit.middleware.core.exception_filters import (
    ExceptionFilterChain,
    NotFoundExceptionFilter,
    ValidationExceptionFilter,
)
from quadkit.middleware.core.registry import MiddlewareRegistry


class TestMiddlewareLifecycle:
    """Test complete middleware pipeline lifecycle integration."""

    @pytest.fixture
    def execution_tracker(self) -> dict:
        """Track middleware execution order and state changes."""
        return {"calls": [], "errors": []}

    @pytest.mark.asyncio
    async def test_middleware_chain_lifecycle(self, execution_tracker: dict) -> None:
        """Test complete lifecycle: register → build → execute → verify.

        This integration test validates:
        1. Middleware can be added to a mutable chain
        2. Chain can be built into an immutable pipeline
        3. All middleware are executed in registration order
        4. Context flows through all middleware
        5. Final handler receives the context and produces result
        """
        from quadkit.middleware.core.chain import MiddlewareChain

        # Step 1: Create a middleware chain (register phase)
        chain = MiddlewareChain()
        assert len(chain) == 0, "Empty chain should have 0 middleware"

        # Create middleware that track execution
        async def middleware_1(context, next_handler):
            """First middleware: adds to execution log."""
            execution_tracker["calls"].append("mw1_before")
            context["mw1"] = True
            result = await next_handler(context)
            execution_tracker["calls"].append("mw1_after")
            return result

        async def middleware_2(context, next_handler):
            """Second middleware: adds to execution log."""
            execution_tracker["calls"].append("mw2_before")
            context["mw2"] = True
            result = await next_handler(context)
            execution_tracker["calls"].append("mw2_after")
            return result

        async def middleware_3(context, next_handler):
            """Third middleware: adds to execution log."""
            execution_tracker["calls"].append("mw3_before")
            context["mw3"] = True
            result = await next_handler(context)
            execution_tracker["calls"].append("mw3_after")
            return result

        # Step 2: Register middleware using fluent interface
        chain.add(middleware_1)
        assert len(chain) == 1, "Chain should have 1 middleware after add"

        chain.add(middleware_2).add(middleware_3)
        assert len(chain) == 3, "Chain should have 3 middleware after adds"

        # Step 3: Build immutable pipeline
        pipeline = chain.build()
        assert pipeline is not None, "Build should return a MiddlewarePipeline"
        assert len(chain) == 3, "Original chain should still have 3 middleware after build"

        # Create a final handler that verifies context was populated by all middleware
        async def final_handler(context):
            """Final handler that runs after all middleware."""
            execution_tracker["calls"].append("handler")
            assert context.get("mw1") is True, "Middleware 1 should have set mw1"
            assert context.get("mw2") is True, "Middleware 2 should have set mw2"
            assert context.get("mw3") is True, "Middleware 3 should have set mw3"
            return {"status": "success", "context": context}

        # Step 4: Execute the pipeline (all middleware + final handler)
        initial_context = {"request_id": "test-123"}
        result = await pipeline.execute(initial_context, final_handler)

        # Step 5: Verify execution order and result
        assert result["status"] == "success", "Final handler should return successful result"

        # Verify middleware executed in correct order:
        # mw1_before → mw2_before → mw3_before → handler → mw3_after → mw2_after → mw1_after
        expected_order = [
            "mw1_before",
            "mw2_before",
            "mw3_before",
            "handler",
            "mw3_after",
            "mw2_after",
            "mw1_after",
        ]
        assert execution_tracker["calls"] == expected_order, (
            f"Execution order mismatch. Expected {expected_order}, got {execution_tracker['calls']}"
        )

        # Verify context was properly threaded through all middleware
        assert result["context"]["request_id"] == "test-123", "Original context preserved"
        assert result["context"]["mw1"] is True, "Middleware 1 context visible to handler"
        assert result["context"]["mw2"] is True, "Middleware 2 context visible to handler"
        assert result["context"]["mw3"] is True, "Middleware 3 context visible to handler"

    @pytest.mark.asyncio
    async def test_empty_chain_builds_successfully(self) -> None:
        """Test that an empty chain builds to an empty pipeline."""
        from quadkit.middleware.core.chain import MiddlewareChain

        chain = MiddlewareChain()
        pipeline = chain.build()

        # Execute empty pipeline with a simple handler
        async def handler(context):
            return {"result": "executed"}

        result = await pipeline.execute({}, handler)
        assert result == {"result": "executed"}, "Empty pipeline should execute handler"

    @pytest.mark.asyncio
    async def test_chain_remains_mutable_after_build(self) -> None:
        """Test that a chain can be reused to build multiple pipelines."""
        from quadkit.middleware.core.chain import MiddlewareChain

        chain = MiddlewareChain()

        async def mw1(context, next_handler):
            context["mw1"] = True
            return await next_handler(context)

        async def mw2(context, next_handler):
            context["mw2"] = True
            return await next_handler(context)

        # Build first pipeline
        chain.add(mw1)
        pipeline1 = chain.build()
        assert len(chain) == 1

        # Build second pipeline (chain remains mutable)
        chain.add(mw2)
        pipeline2 = chain.build()
        assert len(chain) == 2

        # Verify pipeline1 only has mw1
        async def handler(context):
            return context

        result1 = await pipeline1.execute({}, handler)
        assert result1.get("mw1") is True, "Pipeline1 should have mw1"
        assert result1.get("mw2") is None, "Pipeline1 should not have mw2"

        # Verify pipeline2 has both mw1 and mw2
        result2 = await pipeline2.execute({}, handler)
        assert result2.get("mw1") is True, "Pipeline2 should have mw1"
        assert result2.get("mw2") is True, "Pipeline2 should have mw2"

    @pytest.mark.asyncio
    async def test_middleware_exception_propagates_correctly(self, execution_tracker: dict) -> None:
        """Test that exceptions in middleware propagate correctly."""
        from quadkit.middleware.core.chain import MiddlewareChain

        chain = MiddlewareChain()

        async def logging_middleware(context, next_handler):
            """Logs before and after."""
            execution_tracker["calls"].append("before")
            try:
                result = await next_handler(context)
                execution_tracker["calls"].append("after_success")
                return result
            except ValueError:
                execution_tracker["calls"].append("after_error")
                raise

        async def failing_middleware(context, next_handler):
            """Raises an error."""
            execution_tracker["calls"].append("failing")
            raise ValueError("Intentional test error")

        chain.add(logging_middleware).add(failing_middleware)
        pipeline = chain.build()

        async def handler(context):
            execution_tracker["calls"].append("handler")
            return {"status": "ok"}

        # Execute and expect the error to propagate
        with pytest.raises(ValueError, match="Intentional test error"):
            await pipeline.execute({}, handler)

        # Verify that logging middleware caught the error
        assert execution_tracker["calls"] == [
            "before",
            "failing",
            "after_error",
        ], "Error should propagate through middleware"


class TestNewMiddlewareIntegration:
    @pytest.mark.asyncio
    async def test_full_chain_with_timeout_and_circuit_breaker(self) -> None:
        chain = MiddlewareChain()
        chain.add(LoggingMiddleware())
        chain.add(TimeoutMiddleware(timeout=5.0))
        chain.add(CircuitBreakerMiddleware(failure_threshold=3))
        chain.add(TimingMiddleware())

        pipeline = chain.build()

        async def handler(ctx: Any) -> dict[str, str]:
            return {"status": "ok"}

        result = await pipeline.execute({}, handler)
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_conditional_middleware_in_chain(self) -> None:
        calls: list[str] = []

        async def tracking_mw(ctx: Any, nxt: Any) -> Any:
            calls.append("tracked")
            return await nxt(ctx)

        chain = MiddlewareChain()
        chain.add(
            ConditionalMiddleware(
                tracking_mw,
                predicate=lambda ctx: ctx.get("track", False),
            )
        )

        pipeline = chain.build()

        async def handler(ctx: Any) -> str:
            return "done"

        await pipeline.execute({"track": False}, handler)
        assert calls == []

        await pipeline.execute({"track": True}, handler)
        assert calls == ["tracked"]

    @pytest.mark.asyncio
    async def test_exception_filter_chain_with_builtins(self) -> None:
        from quadkit.contracts.exceptions.domain import NotFoundError, ValidationError

        chain = ExceptionFilterChain()
        chain = chain.add(ValidationExceptionFilter())
        chain = chain.add(NotFoundExceptionFilter())

        result = await chain.handle(ValidationError("bad email"), {})
        assert result["status"] == 422

        result = await chain.handle(NotFoundError("user 123"), {})
        assert result["status"] == 404

        with pytest.raises(RuntimeError):
            await chain.handle(RuntimeError("unhandled"), {})

    @pytest.mark.asyncio
    async def test_registry_with_defaults_builds_chain(self) -> None:
        registry = MiddlewareRegistry.with_defaults()
        chain = registry.build_chain()
        pipeline = chain.build()

        async def handler(ctx: Any) -> str:
            return "ok"

        result = await pipeline.execute({}, handler)
        assert result == "ok"
