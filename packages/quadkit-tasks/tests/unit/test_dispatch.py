"""Tests for the :func:`~quadkit.tasks.dispatch.delay` decorator.

Coverage targets:
- @delay preserves function metadata (__name__, __doc__, __wrapped__)
- Direct call returns a coroutine and executes correctly
- .delay() returns an asyncio.Task
- .delay() task runs to completion
- Task reference is held in _background_tasks during execution
- Task reference is removed from _background_tasks after completion
- .delay() with positional and keyword arguments
- Multiple independent .delay() calls accumulate independent tasks
"""

from __future__ import annotations

import asyncio

import pytest

from quadkit.tasks.dispatch import _background_tasks, delay


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@delay
async def _add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@delay
async def _slow(duration: float) -> str:
    """Sleep then return 'done'."""
    await asyncio.sleep(duration)
    return "done"


@delay
async def _side_effect(results: list[str], value: str) -> None:
    """Append value to results list."""
    results.append(value)


# ---------------------------------------------------------------------------
# Metadata preservation
# ---------------------------------------------------------------------------


class TestDelayMetadata:
    def test_name_preserved(self) -> None:
        assert _add.__name__ == "_add"

    def test_doc_preserved(self) -> None:
        assert _add.__doc__ == "Add two numbers."

    def test_wrapped_attribute_set(self) -> None:
        # functools.update_wrapper sets __wrapped__ to the original function.
        assert hasattr(_add, "__wrapped__")

    def test_qualname_preserved(self) -> None:
        assert "_add" in _add.__qualname__


# ---------------------------------------------------------------------------
# Direct call behaviour
# ---------------------------------------------------------------------------


class TestDelayDirectCall:
    @pytest.mark.asyncio
    async def test_direct_call_returns_correct_result(self) -> None:
        result = await _add(2, 3)
        assert result == 5

    @pytest.mark.asyncio
    async def test_direct_call_with_keyword_args(self) -> None:
        result = await _add(a=10, b=20)
        assert result == 30

    @pytest.mark.asyncio
    async def test_direct_call_is_coroutine(self) -> None:
        coro = _add(1, 2)
        assert asyncio.iscoroutine(coro)
        result = await coro
        assert result == 3


# ---------------------------------------------------------------------------
# .delay() dispatch behaviour
# ---------------------------------------------------------------------------


class TestDelayMethod:
    @pytest.mark.asyncio
    async def test_delay_returns_task(self) -> None:
        task = _slow.delay(0)
        assert isinstance(task, asyncio.Task)
        await task

    @pytest.mark.asyncio
    async def test_delay_task_runs_to_completion(self) -> None:
        results: list[str] = []
        task = _side_effect.delay(results, "hello")
        await task
        assert results == ["hello"]

    @pytest.mark.asyncio
    async def test_delay_with_positional_args(self) -> None:
        task = _add.delay(4, 5)
        result = await task
        assert result == 9

    @pytest.mark.asyncio
    async def test_delay_with_keyword_args(self) -> None:
        task = _add.delay(a=7, b=3)
        result = await task
        assert result == 10

    @pytest.mark.asyncio
    async def test_delay_task_is_tracked_during_execution(self) -> None:
        """The task reference must be in _background_tasks before it finishes."""
        event = asyncio.Event()

        @delay
        async def _gated() -> None:
            await event.wait()

        task = _gated.delay()
        # Task is now in flight but blocked — it must be tracked.
        assert task in _background_tasks

        # Unblock and wait for completion.
        event.set()
        await task

    @pytest.mark.asyncio
    async def test_delay_task_removed_after_completion(self) -> None:
        task = _slow.delay(0)
        await task
        # Give the done callback a chance to run (it's synchronous, but
        # asyncio schedules callbacks after the current tick).
        await asyncio.sleep(0)
        assert task not in _background_tasks

    @pytest.mark.asyncio
    async def test_multiple_delay_calls_produce_independent_tasks(self) -> None:
        results: list[str] = []
        t1 = _side_effect.delay(results, "first")
        t2 = _side_effect.delay(results, "second")
        assert t1 is not t2
        await asyncio.gather(t1, t2)
        assert sorted(results) == ["first", "second"]

    @pytest.mark.asyncio
    async def test_delay_task_name_contains_function_name(self) -> None:
        task = _add.delay(1, 2)
        assert "_add" in (task.get_name() or "")
        await task
