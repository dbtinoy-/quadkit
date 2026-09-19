"""Unit tests for AOPInterceptorChain per-interceptor timeout (M48)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from quadkit.di.extensions.aop_interceptors import (
    AOPInterceptorChain,
    InterceptorTimeoutError,
    MethodInterceptorProtocol,
    MethodInvocation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_invocation() -> MethodInvocation:
    """Return a simple sync method invocation."""

    def noop() -> str:
        return "done"

    return MethodInvocation(
        target=object(),
        method_name="noop",
        args=(),
        kwargs={},
        method=noop,
    )


class _PassThroughInterceptor:
    """Interceptor that delegates immediately without any timeout_seconds."""

    async def intercept(
        self,
        invocation: MethodInvocation,
        next_interceptor: Callable[[], Awaitable[Any]],
    ) -> Any:
        return await next_interceptor()


class _SlowInterceptor:
    """Interceptor that sleeps for a configurable duration with a timeout_seconds."""

    def __init__(self, sleep: float, timeout_seconds: float | None = None) -> None:
        self._sleep = sleep
        if timeout_seconds is not None:
            self.timeout_seconds = timeout_seconds

    async def intercept(
        self,
        invocation: MethodInvocation,
        next_interceptor: Callable[[], Awaitable[Any]],
    ) -> Any:
        await asyncio.sleep(self._sleep)
        return await next_interceptor()


class _RecordingInterceptor:
    """Tracks whether it was called."""

    called: bool = False

    async def intercept(
        self,
        invocation: MethodInvocation,
        next_interceptor: Callable[[], Awaitable[Any]],
    ) -> Any:
        self.called = True
        return await next_interceptor()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAOPInterceptorChainTimeout:
    """AOPInterceptorChain wraps each interceptor with asyncio.timeout() when configured."""

    # -- no timeout --

    @pytest.mark.asyncio
    async def test_chain_completes_without_timeout_when_not_configured(self) -> None:
        chain = AOPInterceptorChain([_PassThroughInterceptor()])
        invocation = _make_invocation()
        result = await chain.proceed(invocation)
        assert result == "done"

    @pytest.mark.asyncio
    async def test_slow_interceptor_without_timeout_completes(self) -> None:
        """Interceptor without timeout_seconds attribute is not time-limited."""
        slow = _SlowInterceptor(sleep=0.0)  # no timeout_seconds set
        chain = AOPInterceptorChain([slow])
        invocation = _make_invocation()
        result = await chain.proceed(invocation)
        assert result == "done"

    # -- with timeout --

    @pytest.mark.asyncio
    async def test_fast_interceptor_passes_within_timeout(self) -> None:
        fast = _SlowInterceptor(sleep=0.0, timeout_seconds=1.0)
        chain = AOPInterceptorChain([fast])
        result = await chain.proceed(_make_invocation())
        assert result == "done"

    @pytest.mark.asyncio
    async def test_slow_interceptor_raises_interceptor_timeout_error(self) -> None:
        slow = _SlowInterceptor(sleep=5.0, timeout_seconds=0.01)
        chain = AOPInterceptorChain([slow])

        with pytest.raises(InterceptorTimeoutError) as exc_info:
            await chain.proceed(_make_invocation())

        error = exc_info.value
        assert error.timeout_seconds == pytest.approx(0.01)
        assert "noop" in error.method_signature

    @pytest.mark.asyncio
    async def test_interceptor_timeout_error_contains_interceptor_name(self) -> None:
        slow = _SlowInterceptor(sleep=5.0, timeout_seconds=0.01)
        chain = AOPInterceptorChain([slow])

        with pytest.raises(InterceptorTimeoutError) as exc_info:
            await chain.proceed(_make_invocation())

        assert "_SlowInterceptor" in str(exc_info.value)

    # -- chaining — only the timed-out interceptor raises --

    @pytest.mark.asyncio
    async def test_timeout_in_second_interceptor_propagates(self) -> None:
        recording = _RecordingInterceptor()
        slow = _SlowInterceptor(sleep=5.0, timeout_seconds=0.01)
        chain = AOPInterceptorChain([recording, slow])

        with pytest.raises(InterceptorTimeoutError):
            await chain.proceed(_make_invocation())

        # First interceptor executed before timeout was hit
        assert recording.called

    # -- InterceptorTimeoutError properties --

    def test_error_captures_interceptor_reference(self) -> None:
        interceptor = _PassThroughInterceptor()
        error = InterceptorTimeoutError(
            interceptor=interceptor,
            method_signature="Foo.bar",
            timeout_seconds=2.5,
        )
        assert error.interceptor is interceptor
        assert error.method_signature == "Foo.bar"
        assert error.timeout_seconds == 2.5
