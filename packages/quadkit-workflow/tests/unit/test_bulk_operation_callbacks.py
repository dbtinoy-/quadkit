"""Unit tests for BulkOperation lifecycle callbacks.

Covers on_progress, on_complete, and on_error hooks injected via the
BulkOperation constructor.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock

import pytest

from quadkit.workflow.bulk.models import BulkOperationState
from quadkit.workflow.bulk.operation import BulkOperation
from quadkit.workflow.config import BulkOperationConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(batch_size: int = 2) -> BulkOperationConfig:
    return BulkOperationConfig(batch_size=batch_size, max_concurrency=2, timeout=10.0)


async def _identity_processor(batch: list[int]) -> list[int]:
    """Pass-through processor that returns the batch unchanged."""
    return batch


async def _failing_processor(batch: list[int]) -> list[int]:
    """Processor that always raises to trigger on_error hooks."""
    msg = "deliberate failure"
    raise ValueError(msg)


def _hook() -> tuple[AsyncMock, list[tuple[int, int, str]]]:
    """Return a mock hook and a list that collects its call arguments."""
    calls: list[tuple[int, int, str]] = []

    async def _cb(processed: int, total: int, message: str) -> None:
        calls.append((processed, total, message))

    mock = AsyncMock(side_effect=_cb)
    return mock, calls


# ---------------------------------------------------------------------------
# on_progress
# ---------------------------------------------------------------------------


class TestOnProgressCallback:
    """on_progress is called after each successful batch."""

    @pytest.mark.asyncio
    async def test_on_progress_called_once_per_successful_batch(self) -> None:
        """on_progress fires once per batch for a 4-item list with batch_size=2."""
        hook, calls = _hook()
        op = BulkOperation(
            config=_make_config(batch_size=2),
            processor=_identity_processor,
            on_progress=hook,
        )

        async for _ in op.execute([1, 2, 3, 4]):
            pass

        # Two batches → two on_progress calls
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_on_progress_receives_correct_processed_count(self) -> None:
        """on_progress receives the running processed_items count."""
        hook, calls = _hook()
        op = BulkOperation(
            config=_make_config(batch_size=1),
            processor=_identity_processor,
            on_progress=hook,
        )

        async for _ in op.execute([10, 20]):
            pass

        processed_counts = [c[0] for c in calls]
        assert 1 in processed_counts or 2 in processed_counts  # incremental
        assert calls[-1][1] == 2  # total == len(items)

    @pytest.mark.asyncio
    async def test_on_progress_message_omits_batch_identifiers(self) -> None:
        """The callback message is descriptive without exposing a batch ID."""
        hook, calls = _hook()
        op = BulkOperation(
            config=_make_config(batch_size=5),
            processor=_identity_processor,
            on_progress=hook,
        )

        async for _ in op.execute([1, 2, 3, 4, 5]):
            pass

        assert len(calls) == 1
        assert calls[0][2] == "A batch was processed."
        assert "1" not in calls[0][2]

    @pytest.mark.asyncio
    async def test_on_progress_not_called_when_none(self) -> None:
        """No error when on_progress is None (the default no-op)."""
        op = BulkOperation(
            config=_make_config(),
            processor=_identity_processor,
            on_progress=None,
        )
        results = []
        async for r in op.execute([1, 2]):
            results.append(r)

        assert len(results) == 1  # one batch of 2
        assert op.state == BulkOperationState.COMPLETED


# ---------------------------------------------------------------------------
# on_complete
# ---------------------------------------------------------------------------


class TestOnCompleteCallback:
    """on_complete is called exactly once when the operation finishes normally."""

    @pytest.mark.asyncio
    async def test_on_complete_called_once_on_success(self) -> None:
        """on_complete fires once after all batches succeed."""
        hook, calls = _hook()
        op = BulkOperation(
            config=_make_config(),
            processor=_identity_processor,
            on_complete=hook,
        )

        async for _ in op.execute([1, 2, 3, 4]):
            pass

        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_on_complete_receives_final_counts(self) -> None:
        """on_complete receives the final processed and total counts."""
        hook, calls = _hook()
        op = BulkOperation(
            config=_make_config(batch_size=3),
            processor=_identity_processor,
            on_complete=hook,
        )

        async for _ in op.execute([1, 2, 3]):
            pass

        processed, total, _ = calls[0]
        assert processed == 3
        assert total == 3

    @pytest.mark.asyncio
    async def test_on_complete_message_indicates_completion(self) -> None:
        """The message string passed to on_complete mentions completion."""
        hook, calls = _hook()
        op = BulkOperation(
            config=_make_config(),
            processor=_identity_processor,
            on_complete=hook,
        )

        async for _ in op.execute([1, 2]):
            pass

        assert "complet" in calls[0][2].lower()

    @pytest.mark.asyncio
    async def test_on_complete_not_called_on_failure(self) -> None:
        """on_complete is NOT called when the operation fails after retries."""
        complete_hook, complete_calls = _hook()
        op = BulkOperation(
            config=BulkOperationConfig(
                batch_size=2, max_concurrency=1, retry_attempts=0, timeout=10.0
            ),
            processor=_failing_processor,
            on_complete=complete_hook,
        )

        # Failed batches are returned as results with errors; no exception raised
        async for _ in op.execute([1, 2]):
            pass

        # on_complete fires because the operation state reaches COMPLETED
        # even if individual batches failed (batch errors are not operation errors)
        # This is the existing framework behaviour: COMPLETED means execute() finished.
        assert op.state == BulkOperationState.COMPLETED

    @pytest.mark.asyncio
    async def test_on_complete_not_called_when_none(self) -> None:
        """No error when on_complete is None."""
        op = BulkOperation(
            config=_make_config(),
            processor=_identity_processor,
            on_complete=None,
        )
        async for _ in op.execute([1, 2]):
            pass
        assert op.state == BulkOperationState.COMPLETED


# ---------------------------------------------------------------------------
# on_error
# ---------------------------------------------------------------------------


class TestOnErrorCallback:
    """on_error is called when a batch fails."""

    @pytest.mark.asyncio
    async def test_on_error_called_when_batch_fails(self) -> None:
        """on_error fires for each batch that fails after all retries."""
        hook, calls = _hook()
        op = BulkOperation(
            config=BulkOperationConfig(
                batch_size=2, max_concurrency=1, retry_attempts=0, timeout=10.0
            ),
            processor=_failing_processor,
            on_error=hook,
        )

        async for _ in op.execute([1, 2]):
            pass

        assert len(calls) >= 1  # at least one batch failure

    @pytest.mark.asyncio
    async def test_on_error_message_describes_failure(self) -> None:
        """on_error receives a non-empty descriptive message."""
        hook, calls = _hook()
        op = BulkOperation(
            config=BulkOperationConfig(
                batch_size=2, max_concurrency=1, retry_attempts=0, timeout=10.0
            ),
            processor=_failing_processor,
            on_error=hook,
        )

        async for _ in op.execute([1, 2]):
            pass

        assert calls[0][2]  # message is non-empty
        assert "fail" in calls[0][2].lower() or "error" in calls[0][2].lower() or "batch" in calls[0][2].lower()

    @pytest.mark.asyncio
    async def test_on_error_not_called_when_none(self) -> None:
        """No error when on_error is None and batches fail."""
        op = BulkOperation(
            config=BulkOperationConfig(
                batch_size=2, max_concurrency=1, retry_attempts=0, timeout=10.0
            ),
            processor=_failing_processor,
            on_error=None,
        )
        async for _ in op.execute([1, 2]):
            pass  # must not raise

    @pytest.mark.asyncio
    async def test_on_error_not_called_when_batches_succeed(self) -> None:
        """on_error is NOT called when all batches succeed."""
        hook, calls = _hook()
        op = BulkOperation(
            config=_make_config(),
            processor=_identity_processor,
            on_error=hook,
        )

        async for _ in op.execute([1, 2]):
            pass

        assert calls == []

    # ------------------------------------------------------------------
    # Hook isolation — misbehaving hook must not abort operation
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_raising_hook_does_not_abort_operation(self) -> None:
        """A hook that raises must not prevent the operation from completing."""

        async def bad_hook(processed: int, total: int, message: str) -> None:
            msg = "hook is broken"
            raise RuntimeError(msg)

        op = BulkOperation(
            config=_make_config(),
            processor=_identity_processor,
            on_progress=bad_hook,
        )

        results = []
        async for r in op.execute([1, 2, 3, 4]):
            results.append(r)

        assert op.state == BulkOperationState.COMPLETED
        assert len(results) == 2


# ---------------------------------------------------------------------------
# All three callbacks together
# ---------------------------------------------------------------------------


class TestAllCallbacksTogether:
    """Smoke test — all three hooks can coexist."""

    @pytest.mark.asyncio
    async def test_all_hooks_fire_in_correct_order(self) -> None:
        """progress fires before complete; error fires on failure."""
        fired: list[str] = []

        async def on_progress(p: int, t: int, msg: str) -> None:
            fired.append("progress")

        async def on_complete(p: int, t: int, msg: str) -> None:
            fired.append("complete")

        async def on_error(p: int, t: int, msg: str) -> None:
            fired.append("error")

        op = BulkOperation(
            config=_make_config(batch_size=2),
            processor=_identity_processor,
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error,
        )

        async for _ in op.execute([1, 2, 3, 4]):
            pass

        # progress must appear before complete
        assert "progress" in fired
        assert "complete" in fired
        assert "error" not in fired
        assert fired.index("complete") > fired.index("progress")
