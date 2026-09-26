# packages/quadkit-sql/tests/unit/test_context_propagation.py

import asyncio
import pytest

from quadkit.sql.context import (
    REQUEST_ID,
    RequestContextManager,
    create_db_context,
    create_task_with_context,
    run_in_threadpool_with_context,
)


@pytest.fixture
def db_ctx():
    """Injectable DbContext for tests."""
    return create_db_context()


@pytest.mark.asyncio
class TestContextPropagation:
    """Test context variable propagation."""

    async def test_context_propagates_to_background_task(self, db_ctx) -> None:
        """Test that context is available in background task."""
        # Arrange
        async with RequestContextManager(db_ctx, request_id="req_test123"):
            captured_request_id: str | None = None

            async def background_task() -> None:
                nonlocal captured_request_id
                captured_request_id = db_ctx.request_id

            # Act - create task with context
            task = create_task_with_context(background_task())
            await task

        # Assert - context was available inside the async with block
        assert captured_request_id == "req_test123"

    async def test_context_without_propagation_is_lost(self, db_ctx) -> None:
        """Test that regular create_task in a fresh context loses context."""
        # Arrange
        async with RequestContextManager(db_ctx, request_id="req_test456"):
            captured_request_id: str | None = "not_set"

            async def background_task() -> None:
                nonlocal captured_request_id
                captured_request_id = db_ctx.request_id

            # Act - run in a fresh context where context vars are not inherited
            import contextvars

            context = contextvars.Context()
            task = context.run(asyncio.create_task, background_task())
            await task

        # Assert - context was lost because we ran in a blank context
        assert captured_request_id is None

    async def test_context_propagates_to_thread_pool(self, db_ctx) -> None:
        """Test that context is available in thread pool."""
        async with RequestContextManager(db_ctx, request_id="req_thread789"):
            def sync_function() -> str | None:
                # This runs in thread pool
                return db_ctx.request_id

            # Act
            result = await run_in_threadpool_with_context(sync_function)

        # Assert - context was available
        assert result == "req_thread789"

    async def test_context_manager_sets_and_cleans_up(self, db_ctx) -> None:
        """Test that RequestContextManager sets up and cleans context."""
        # Arrange - no context initially
        assert db_ctx.request_id is None

        # Act - use context manager
        async with RequestContextManager(db_ctx, request_id="req_ctx"):
            assert db_ctx.request_id == "req_ctx"

        # Assert - cleaned up after exit
        assert db_ctx.request_id is None

    async def test_nested_background_tasks_preserve_context(self, db_ctx) -> None:
        """Test that nested background tasks preserve context."""
        results = []

        async with RequestContextManager(db_ctx, request_id="req_nested"):
            async def level2_task() -> None:
                results.append(("level2", db_ctx.request_id))

            async def level1_task() -> None:
                results.append(("level1", db_ctx.request_id))
                task = create_task_with_context(level2_task())
                await task

            # Act
            task = create_task_with_context(level1_task())
            await task

        # Assert - both levels had context
        assert results == [
            ("level1", "req_nested"),
            ("level2", "req_nested"),
        ]
