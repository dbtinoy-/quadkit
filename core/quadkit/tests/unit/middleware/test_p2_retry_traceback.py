"""P2-retry-traceback: RetryMiddleware must preserve exception traceback on re-raise."""

from __future__ import annotations

import pytest

from quadkit.middleware.builtins.resilience import RetryMiddleware


class TestRetryMiddlewarePreservesTraceback:
    """P2: The exception raised after retries exhausted must chain via __cause__."""

    @pytest.mark.asyncio
    async def test_exception_has_traceback_after_retries_exhausted(self) -> None:
        """Traceback is preserved when all retry attempts fail."""
        middleware = RetryMiddleware(catch=ValueError, max_retries=1, delay=0.0)

        async def always_fails(ctx: object) -> None:
            raise ValueError("boom")

        caught: BaseException | None = None
        try:
            await middleware(None, always_fails)
        except ValueError as exc:
            caught = exc

        assert caught is not None, "Expected ValueError to propagate"
        assert caught.__traceback__ is not None, (
            "RetryMiddleware lost the exception traceback on re-raise"
        )

    @pytest.mark.asyncio
    async def test_exception_is_chained_via_cause(self) -> None:
        """raise last_error from last_error must set __cause__ on the re-raised exception.

        This is the observable difference between `raise exc` and `raise exc from exc`.
        `raise exc from exc` sets exc.__cause__ = exc (explicit chaining), which allows
        tooling to distinguish an explicitly chained raise from a bare re-raise.
        """
        middleware = RetryMiddleware(catch=RuntimeError, max_retries=0, delay=0.0)

        async def raise_once(ctx: object) -> None:
            raise RuntimeError("chained")

        with pytest.raises(RuntimeError) as exc_info:
            await middleware(None, raise_once)

        raised = exc_info.value
        # `raise exc from exc` sets __cause__ = exc (self-chaining) and
        # __suppress_context__ = True.  Without `from`, both remain None/False.
        assert raised.__cause__ is raised, (
            "RetryMiddleware must use 'raise last_error from last_error' "
            "to explicitly chain the exception (sets __cause__ = exc)"
        )

    @pytest.mark.asyncio
    async def test_original_exception_identity_is_preserved(self) -> None:
        """The re-raised exception is the same object that was caught inside the loop."""
        middleware = RetryMiddleware(catch=RuntimeError, max_retries=0, delay=0.0)
        sentinel = RuntimeError("sentinel")

        async def raise_sentinel(ctx: object) -> None:
            raise sentinel

        with pytest.raises(RuntimeError) as exc_info:
            await middleware(None, raise_sentinel)

        assert exc_info.value is sentinel
