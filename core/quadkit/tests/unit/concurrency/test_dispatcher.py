"""
Tests for Dispatcher - Critical thread pool and context propagation validation.
"""

import asyncio
import os
import threading
import time

import pytest

from quadkit.concurrency.executors.dispatcher import DispatcherImpl, dispatch
from quadkit.primitives.context import (
    Context,
    ContextKey,
    REQUEST_ID,
    TENANT_ID,
    USER_ID,
    create_default_context,
)

# Custom context keys used only in tests
_TEST_KEY: ContextKey[str] = ContextKey("test_key")
_TASK_ID: ContextKey[int] = ContextKey("task_id")
_TENANT: ContextKey[str] = ContextKey("tenant")


@pytest.fixture
def ctx() -> Context:
    """Injectable Context instance with all test keys registered."""
    context = create_default_context()
    context.register_key(_TEST_KEY)
    context.register_key(_TASK_ID)
    context.register_key(_TENANT)
    return context


@pytest.fixture
def dispatcher():
    """Create a fresh DispatcherImpl instance for each test."""
    d = DispatcherImpl()
    yield d
    # Tear down pools after each test
    if d._cpu_pool is not None or d._io_pool is not None:
        try:
            loop = asyncio.get_event_loop()
            is_running = loop.is_running()
        except RuntimeError:
            is_running = False

        if is_running:
            d._cpu_pool and d._cpu_pool.shutdown(wait=False)
            d._io_pool and d._io_pool.shutdown(wait=False)
        else:
            # If no loop is running, we can still shutdown the pools
            d._cpu_pool and d._cpu_pool.shutdown(wait=False)
            d._io_pool and d._io_pool.shutdown(wait=False)

        d._cpu_pool = None
        d._io_pool = None


class TestDispatcherThreadPools:
    """Test dispatcher thread pool management."""

    def test_cpu_pool_size(self, dispatcher):
        """Test CPU pool has correct number of workers."""
        cpu_workers = os.cpu_count()
        assert dispatcher.cpu_pool._max_workers == cpu_workers

    def test_io_pool_size(self, dispatcher):
        """Test I/O pool has correct number of workers."""
        expected_io_workers = (os.cpu_count() or 1) * 4
        assert dispatcher.io_pool._max_workers == expected_io_workers

    def test_separate_pools(self, dispatcher):
        """Test CPU and I/O pools are separate instances."""
        cpu_pool = dispatcher.cpu_pool
        io_pool = dispatcher.io_pool
        assert cpu_pool is not io_pool

    @pytest.mark.asyncio
    async def test_cpu_pool_execution(self, dispatcher):
        """Test CPU-bound task uses CPU pool."""

        def cpu_bound_task():
            # Simulate CPU-bound work
            result = 0
            for i in range(100000):
                result += i * i
            return result

        result = await dispatcher.run(
            cpu_bound_task,
            executor=dispatcher.cpu_pool,
        )
        assert isinstance(result, int)
        assert result > 0

    @pytest.mark.asyncio
    async def test_io_pool_execution(self, dispatcher):
        """Test I/O-bound task uses I/O pool."""

        def io_bound_task():
            # Simulate I/O-bound work
            time.sleep(0.01)  # Small delay to simulate I/O
            return "io_result"

        result = await dispatcher.run(io_bound_task, executor=dispatcher.io_pool)
        assert result == "io_result"

    @pytest.mark.asyncio
    async def test_default_executor_selection(self, dispatcher):
        """Test default executor selection for sync functions."""

        def sync_task():
            return threading.current_thread().name

        thread_name = await dispatcher.run(sync_task)
        # Should use I/O pool by default
        assert "quadkit-dispatcher-io" in thread_name


class TestDispatcherContextPropagation:
    """Test context propagation across thread boundaries."""

    @pytest.mark.asyncio
    async def test_context_propagation_basic(self, dispatcher, ctx):
        """Test basic context propagation to thread pool."""
        # Set context in main thread
        ctx.set(REQUEST_ID, "test-123")
        ctx.set(USER_ID, 456)

        def check_context():
            # This runs in thread pool — ContextVars are copied into thread
            return {
                "request_id": ctx.get(REQUEST_ID),
                "user_id": ctx.get(USER_ID),
            }

        result = await dispatcher.run(check_context)
        assert result["request_id"] == "test-123"
        assert result["user_id"] == 456

    @pytest.mark.asyncio
    async def test_context_propagation_with_async(self, dispatcher, ctx):
        """Test context propagation with async functions (should be zero overhead)."""
        ctx.set(_TEST_KEY, "async_value")

        async def async_task():
            return ctx.get(_TEST_KEY)

        result = await dispatcher.run(async_task)
        assert result == "async_value"

    @pytest.mark.asyncio
    async def test_context_isolation(self, dispatcher, ctx):
        """Test context isolation between concurrent operations."""

        async def task_with_context(task_id):
            ctx.set(_TASK_ID, task_id)
            await asyncio.sleep(0.01)  # Simulate async work

            def sync_work():
                return ctx.get(_TASK_ID)

            return await dispatcher.run(sync_work)

        # Run multiple tasks concurrently
        tasks = list(map(task_with_context, range(5)))
        results = await asyncio.gather(*tasks)

        # Each task should see its own context value
        for i, result in enumerate(results):
            assert result == i

    @pytest.mark.asyncio
    async def test_context_preservation_complex(self, dispatcher, ctx):
        """Test complex context preservation with nested operations."""
        ctx.set(REQUEST_ID, "req-12345")
        ctx.set(USER_ID, 999)
        ctx.set(_TENANT, "enterprise")

        def complex_sync_operation():
            # Simulate complex business logic that needs context
            request_id = ctx.get(REQUEST_ID)
            user_id = ctx.get(USER_ID)
            tenant = ctx.get(_TENANT)

            # Simulate database call or external service
            time.sleep(0.01)

            return {
                "request_id": request_id,
                "user_id": user_id,
                "tenant": tenant,
                "processed_by": threading.current_thread().name,
            }

        result = await dispatcher.run(complex_sync_operation)

        assert result["request_id"] == "req-12345"
        assert result["user_id"] == 999
        assert result["tenant"] == "enterprise"
        assert "quadkit-dispatcher-io" in result["processed_by"]


class TestDispatcherAsyncDetection:
    """Test automatic sync/async function detection."""

    @pytest.mark.asyncio
    async def test_async_function_detection(self, dispatcher):
        """Test async function runs natively."""

        async def async_func():
            await asyncio.sleep(0.001)
            return "async_result"

        result = await dispatcher.run(async_func)
        assert result == "async_result"

    @pytest.mark.asyncio
    async def test_sync_function_detection(self, dispatcher):
        """Test sync function runs in thread pool."""

        def sync_func():
            return f"sync_result_from_{threading.current_thread().name}"

        result = await dispatcher.run(sync_func)
        assert "sync_result_from_" in result
        assert "quadkit-dispatcher-io" in result

    @pytest.mark.asyncio
    async def test_mixed_operations(self, dispatcher):
        """Test mixing sync and async operations."""

        async def async_op():
            return "async"

        def sync_op():
            return "sync"

        async_result = await dispatcher.run(async_op)
        sync_result = await dispatcher.run(sync_op)

        assert async_result == "async"
        assert sync_result == "sync"


class TestDispatcherShutdown:
    """Test dispatcher shutdown functionality."""

    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test graceful shutdown of executors."""
        dispatcher = DispatcherImpl()

        # Run some operations first
        def dummy_task():
            return "done"

        result = await dispatcher.run(dummy_task)
        assert result == "done"

        # Get pools before shutdown

        # Shutdown
        await dispatcher.shutdown()

        # Verify pools were shutdown (they should be None now)
        assert dispatcher._cpu_pool is None
        assert dispatcher._io_pool is None

    @pytest.mark.asyncio
    async def test_instance_isolation(self):
        """Test that separate DispatcherImpl instances are independent."""
        d1 = DispatcherImpl()
        d2 = DispatcherImpl()

        result1 = await d1.run(lambda: "from_d1")
        result2 = await d2.run(lambda: "from_d2")

        assert result1 == "from_d1"
        assert result2 == "from_d2"

        # Shutting down d1 should not affect d2
        await d1.shutdown()
        assert d1._cpu_pool is None

        result3 = await d2.run(lambda: "still_works")
        assert result3 == "still_works"

        await d2.shutdown()


class TestDispatcherPerformance:
    """Test dispatcher performance characteristics."""

    @pytest.mark.asyncio
    async def test_async_overhead(self, dispatcher):
        """Test async function overhead is minimal."""

        async def simple_async():
            return 42

        start = time.perf_counter()
        result = await dispatcher.run(simple_async)
        end = time.perf_counter()

        overhead = (end - start) * 1_000_000  # microseconds
        assert result == 42
        import sys

        # Relax threshold to avoid flaky failures on loaded systems
        threshold = 150 if sys.platform.startswith("win") else 100
        assert overhead < threshold  # Use relaxed threshold on Windows

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, dispatcher):
        """Test handling multiple concurrent operations."""

        def concurrent_task(task_id):
            time.sleep(0.01)  # Simulate work
            return f"task_{task_id}"

        # Launch 20 concurrent operations
        tasks = [dispatcher.run(concurrent_task, i) for i in range(20)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 20
        for i, result in enumerate(results):
            assert result == f"task_{i}"


class TestModuleFacade:
    """Test module-level dispatch() and shutdown_dispatcher() functions."""

    @pytest.mark.asyncio
    async def test_dispatch_async(self):
        """Test module-level dispatch with async function."""
        dispatcher = DispatcherImpl()

        async def async_func():
            return "dispatched_async"

        result = await dispatch(async_func, dispatcher=dispatcher)
        assert result == "dispatched_async"

    @pytest.mark.asyncio
    async def test_dispatch_sync(self):
        """Test module-level dispatch with sync function."""
        dispatcher = DispatcherImpl()

        def sync_func():
            return "dispatched_sync"

        result = await dispatch(sync_func, dispatcher=dispatcher)
        assert result == "dispatched_sync"
