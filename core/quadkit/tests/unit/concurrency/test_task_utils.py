# quadkit/tests/unit/concurrency/test_task_utils.py
from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from quadkit.concurrency.task_utils import create_tracked_task


class TestCreateTrackedTask:
    @pytest.mark.asyncio
    async def test_task_added_to_set(self) -> None:
        task_set: set[asyncio.Task] = set()

        async def noop() -> None:
            pass

        task = create_tracked_task(noop(), task_set, name="test_task")
        assert task in task_set
        await task

    @pytest.mark.asyncio
    async def test_task_removed_from_set_after_completion(self) -> None:
        task_set: set[asyncio.Task] = set()

        async def noop() -> None:
            pass

        task = create_tracked_task(noop(), task_set, name="test_task")
        await asyncio.gather(task, return_exceptions=True)
        assert task not in task_set

    @pytest.mark.asyncio
    async def test_exception_in_task_is_logged(self) -> None:
        task_set: set[asyncio.Task] = set()

        async def failing() -> None:
            raise ValueError("test_error")

        with patch("quadkit.concurrency.task_utils.logger") as mock_logger:
            task = create_tracked_task(failing(), task_set, name="failing_task")
            await asyncio.gather(task, return_exceptions=True)
            # Done-callbacks are scheduled via loop.call_soon; yield once
            # so the exception-logging callback actually runs.
            await asyncio.sleep(0)
            mock_logger.error.assert_called_once()
            call_kwargs = mock_logger.error.call_args
            assert call_kwargs[0][0] == "background_task_failed"

    @pytest.mark.asyncio
    async def test_cancelled_task_does_not_log(self) -> None:
        task_set: set[asyncio.Task] = set()

        async def slow() -> None:
            await asyncio.sleep(10)

        with patch("quadkit.concurrency.task_utils.logger") as mock_logger:
            task = create_tracked_task(slow(), task_set, name="cancelled_task")
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            mock_logger.exception.assert_not_called()

    @pytest.mark.asyncio
    async def test_task_name_is_set(self) -> None:
        task_set: set[asyncio.Task] = set()

        async def noop() -> None:
            pass

        task = create_tracked_task(noop(), task_set, name="my_custom_task")
        assert task.get_name() == "my_custom_task"
        await task
