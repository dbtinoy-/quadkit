"""Round-9: canonical RetryConfig semantics for the http RetryPolicy."""

from __future__ import annotations

import pytest

from quadkit.contracts.infra.resilience import RetryConfig
from quadkit.http.retry.policy import RetryPolicy


class TestCanonicalRetrySemantics:
    """Round-9: RetryPolicy honors the full shared RetryConfig contract."""

    @pytest.mark.asyncio
    async def test_max_attempts_is_total_not_plus_one(self) -> None:
        # Contract: max_attempts = total attempts including the initial
        # try. max_attempts=1 must perform exactly ONE call.
        call_count = 0

        async def fail() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("boom")

        policy = RetryPolicy(RetryConfig(max_attempts=1, base_delay=0.001))
        with pytest.raises(ValueError):
            await policy.execute(fail)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_default_config_performs_three_attempts(self) -> None:
        call_count = 0

        async def fail() -> None:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("down")

        policy = RetryPolicy(RetryConfig(max_attempts=3, base_delay=0.001))
        with pytest.raises(ConnectionError):
            await policy.execute(fail)
        assert call_count == 3  # 1 initial + 2 retries, NOT 4

    @pytest.mark.asyncio
    async def test_abort_on_never_retries(self) -> None:
        call_count = 0

        async def fail() -> None:
            nonlocal call_count
            call_count += 1
            raise TimeoutError("slow")

        policy = RetryPolicy(
            RetryConfig(
                max_attempts=3,
                base_delay=0.001,
                retry_on=(Exception,),
                abort_on=(TimeoutError,),
            )
        )
        with pytest.raises(TimeoutError):
            await policy.execute(fail)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_if_must_pass_when_retry_on_matches(self) -> None:
        # Canonical AND semantics: retry_if False suppresses the retry even
        # though the exception is in retry_on.
        call_count = 0

        async def fail() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("fatal")

        policy = RetryPolicy(
            RetryConfig(
                max_attempts=3,
                base_delay=0.001,
                retry_on=(ValueError,),
                retry_if=lambda e: "fatal" not in str(e),
            )
        )
        with pytest.raises(ValueError):
            await policy.execute(fail)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_result_retries_success(self) -> None:
        call_count = 0

        async def partial() -> str:
            nonlocal call_count
            call_count += 1
            return "incomplete" if call_count < 3 else "done"

        policy = RetryPolicy(
            RetryConfig(
                max_attempts=5,
                base_delay=0.001,
                retry_on_result=lambda r: r != "done",
            )
        )
        assert await policy.execute(partial) == "done"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_on_result_stops_at_max_attempts(self) -> None:
        # retry_on_result keeps returning True but attempts run out —
        # the last result is returned, not an error.
        async def always_partial() -> str:
            return "incomplete"

        policy = RetryPolicy(
            RetryConfig(
                max_attempts=2,
                base_delay=0.001,
                retry_on_result=lambda r: True,
            )
        )
        assert await policy.execute(always_partial) == "incomplete"

    @pytest.mark.asyncio
    async def test_abort_if_result_stops_retry(self) -> None:
        call_count = 0

        async def partial() -> str:
            nonlocal call_count
            call_count += 1
            return "incomplete"

        policy = RetryPolicy(
            RetryConfig(
                max_attempts=5,
                base_delay=0.001,
                retry_on_result=lambda r: r == "incomplete",
                abort_if=lambda r: call_count >= 2,
            )
        )
        assert await policy.execute(partial) == "incomplete"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_on_retry_called_per_retry(self) -> None:
        events: list[tuple[int, Exception | None]] = []
        call_count = 0

        async def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("down")
            return "ok"

        policy = RetryPolicy(
            RetryConfig(
                max_attempts=4,
                base_delay=0.001,
                on_retry=lambda attempt, error: events.append((attempt, error)),
            )
        )
        assert await policy.execute(flaky) == "ok"
        assert [a for a, _ in events] == [1, 2]
        assert all(isinstance(e, ConnectionError) for _, e in events)

    @pytest.mark.asyncio
    async def test_on_retry_failure_does_not_propagate(self) -> None:
        async def flaky() -> str:
            return "ok"

        def bad_callback(attempt: int, error: Exception | None) -> None:
            raise RuntimeError("callback broke")

        policy = RetryPolicy(
            RetryConfig(
                max_attempts=2,
                base_delay=0.001,
                on_retry=bad_callback,
                retry_on_result=lambda r: r == "ok",
            )
        )
        # First result triggers a retry (retry_on_result), the broken
        # callback must not surface; second result returns.
        assert await policy.execute(flaky) == "ok"

    @pytest.mark.asyncio
    async def test_exhaustion_reraises_original_exception(self) -> None:
        original = ValueError("original boom")

        async def fail() -> None:
            raise original

        policy = RetryPolicy(RetryConfig(max_attempts=2, base_delay=0.001))
        with pytest.raises(ValueError) as exc_info:
            await policy.execute(fail)
        assert exc_info.value is original


class TestClientPoolAndSessionAccessors:
    """Round-9: pool setter works; pool exposes a public session accessor."""

    @pytest.mark.asyncio
    async def test_pool_setter_replaces_pool(self) -> None:
        from quadkit.http.client import HTTPClient
        from quadkit.http.pool import ConnectionPool

        client = HTTPClient()
        original = client.pool
        replacement = ConnectionPool(max_connections=7)
        client.pool = replacement
        assert client.pool is replacement
        assert original is not replacement

    @pytest.mark.asyncio
    async def test_pool_session_accessor(self) -> None:
        from quadkit.http.pool import ConnectionPool

        pool = ConnectionPool()
        assert pool.session is None

        import aiohttp

        pool._session = aiohttp.ClientSession()  # type: ignore[assignment]
        assert pool.session is pool._session
        await pool.stop()
        assert pool.session is None
