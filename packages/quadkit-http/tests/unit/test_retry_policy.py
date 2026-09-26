"""Tests for quadkit.http.retry.policy."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.infra.resilience.models import RetryConfig
from quadkit.http.retry.policy import RetryPolicy


class TestRetryPolicyInit:
    """Tests for RetryPolicy initialization."""

    def test_default_config(self) -> None:
        """Default config uses RetryConfig defaults."""
        policy = RetryPolicy()
        assert policy.config is not None
        assert policy.config.max_attempts == 3

    def test_custom_config(self) -> None:
        """Custom config is used."""
        config = RetryConfig(max_attempts=5, base_delay=2.0)
        policy = RetryPolicy(config)
        assert policy.config.max_attempts == 5
        assert policy.config.base_delay == 2.0

    def test_none_config(self) -> None:
        """None config creates default RetryConfig."""
        policy = RetryPolicy(None)
        assert policy.config is not None

    def test_config_attributes(self) -> None:
        """Config has expected attributes."""
        config = RetryConfig(
            max_attempts=10,
            base_delay=0.5,
            max_delay=30.0,
            backoff_factor=2.0,
        )
        policy = RetryPolicy(config)
        assert policy.config.max_attempts == 10
        assert policy.config.base_delay == 0.5
        assert policy.config.max_delay == 30.0
        assert policy.config.backoff_factor == 2.0

    def test_jitter_config(self) -> None:
        """Jitter config is stored."""
        config = RetryConfig(jitter=False)
        policy = RetryPolicy(config)
        assert policy.config.jitter is False

        config_with_jitter = RetryConfig(jitter=0.3)
        policy_j = RetryPolicy(config_with_jitter)
        assert policy_j.config.jitter == 0.3

    def test_retry_on_config(self) -> None:
        """retry_on tuple is stored."""
        config = RetryConfig(retry_on=(ValueError, KeyError))
        policy = RetryPolicy(config)
        assert ValueError in policy.config.retry_on
        assert KeyError in policy.config.retry_on

    def test_default_retry_on_is_exception(self) -> None:
        """Default retry_on is (Exception,)."""
        policy = RetryPolicy()
        assert Exception in policy.config.retry_on

    def test_config_is_frozen(self) -> None:
        """RetryConfig is frozen/immutable."""
        from dataclasses import is_dataclass

        assert is_dataclass(RetryConfig)


class TestRetryPolicyInstanceAttributes:
    """Tests for RetryPolicy instance."""

    def test_has_execute_method(self) -> None:
        """Policy has execute method."""
        policy = RetryPolicy()
        assert hasattr(policy, "execute")
        assert callable(policy.execute)

    def test_has_config_attribute(self) -> None:
        """Policy has config attribute after init."""
        policy = RetryPolicy()
        assert hasattr(policy, "config")

    def test_config_is_retry_config(self) -> None:
        """Config is RetryConfig instance."""
        policy = RetryPolicy()
        assert isinstance(policy.config, RetryConfig)


class TestRetryPolicyExecute:
    """Tests for RetryPolicy.execute()."""

    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        """Successful call returns result immediately."""

        async def ok() -> str:
            return "done"

        policy = RetryPolicy()
        result = await policy.execute(ok)
        assert result == "done"

    @pytest.mark.asyncio
    async def test_execute_retry_then_success(self) -> None:
        """Fails once then succeeds on retry."""
        call_count = 0

        async def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("timeout")
            return "ok"

        policy = RetryPolicy(RetryConfig(max_attempts=2, base_delay=0.01))
        result = await policy.execute(flaky)
        assert result == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_execute_exhaust_retries(self) -> None:
        """Raises last exception after all retries exhausted."""

        async def always_fail() -> None:
            raise ValueError("boom")

        policy = RetryPolicy(RetryConfig(max_attempts=2, base_delay=0.01))
        with pytest.raises(ValueError, match="boom"):
            await policy.execute(always_fail)

    @pytest.mark.asyncio
    async def test_execute_non_retryable_exception(self) -> None:
        """Raises immediately for exception not in retry_on."""

        async def fail() -> None:
            raise KeyError("missing")

        policy = RetryPolicy(RetryConfig(max_attempts=2, retry_on=(ValueError,)))
        with pytest.raises(KeyError):
            await policy.execute(fail)

    @pytest.mark.asyncio
    async def test_execute_no_retries(self) -> None:
        """max_attempts=1 means no retries on failure."""

        async def fail() -> None:
            raise RuntimeError("fail")

        policy = RetryPolicy(RetryConfig(max_attempts=1, base_delay=0.01))
        with pytest.raises(RuntimeError):
            await policy.execute(fail)

    @pytest.mark.asyncio
    async def test_execute_with_retry_if(self) -> None:
        """retry_if callback controls retry decision."""

        async def fail() -> None:
            raise ValueError("ephemeral")

        def should_retry(e: Exception) -> bool:
            return "ephemeral" in str(e)

        policy = RetryPolicy(
            RetryConfig(max_attempts=1, retry_if=should_retry, base_delay=0.01)
        )
        with pytest.raises(ValueError, match="ephemeral"):
            await policy.execute(fail)

    @pytest.mark.asyncio
    async def test_execute_passes_args_and_kwargs(self) -> None:
        """Args and kwargs are forwarded to the callable."""

        async def identity(*args: int, **kwargs: str) -> dict:
            return {"args": args, "kwargs": kwargs}

        policy = RetryPolicy()
        result = await policy.execute(identity, 1, 2, key="val")
        assert result == {"args": (1, 2), "kwargs": {"key": "val"}}

    @pytest.mark.asyncio
    async def test_execute_retries_idempotent_method(self) -> None:
        """GET/HEAD/OPTIONS are retried by default (idempotent)."""
        call_count = 0

        async def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("timeout")
            return "ok"

        policy = RetryPolicy(RetryConfig(max_attempts=2, base_delay=0.01))
        result = await policy.execute(flaky, method="GET")
        assert result == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_execute_does_not_retry_non_idempotent_method(self) -> None:
        """POST/PUT/DELETE/PATCH raise immediately (idempotency gate)."""
        call_count = 0

        async def always_fail() -> None:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("timeout")

        policy = RetryPolicy(RetryConfig(max_attempts=2, base_delay=0.01))
        with pytest.raises(ConnectionError):
            await policy.execute(always_fail, method="POST")
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_execute_method_not_forwarded_to_callable(self) -> None:
        """The method kwarg is consumed by the policy, not the callable."""

        async def spy(**kwargs: Any) -> dict:
            return kwargs

        policy = RetryPolicy()
        result = await policy.execute(spy, method="GET")
        assert result == {}

    @pytest.mark.asyncio
    async def test_execute_idempotent_gate_opt_out(self) -> None:
        """idempotent_methods_only=False retries non-idempotent methods."""
        call_count = 0

        async def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("timeout")
            return "ok"

        policy = RetryPolicy(
            RetryConfig(
                max_attempts=2,
                base_delay=0.01,
                idempotent_methods_only=False,
            )
        )
        result = await policy.execute(flaky, method="POST")
        assert result == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_execute_no_method_gate_inactive(self) -> None:
        """Callers without a method (non-HTTP) are retried as before."""
        call_count = 0

        async def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("timeout")
            return "ok"

        policy = RetryPolicy(RetryConfig(max_attempts=2, base_delay=0.01))
        result = await policy.execute(flaky)
        assert result == "ok"
        assert call_count == 2


class TestCalculateDelay:
    """Tests for _calculate_delay."""

    def test_calculate_delay_no_jitter(self) -> None:
        """Delay computed with exponential backoff, no jitter."""
        from quadkit.http.retry.policy import _calculate_delay

        config = RetryConfig(backoff_factor=2.0, max_delay=60.0, jitter=False)
        delay = _calculate_delay(0, config, base_delay=1.0)
        assert delay == 1.0

        delay_attempt1 = _calculate_delay(1, config, base_delay=1.0)
        assert delay_attempt1 == 2.0

        delay_attempt2 = _calculate_delay(2, config, base_delay=1.0)
        assert delay_attempt2 == 4.0

    def test_calculate_delay_caps_at_max(self) -> None:
        """Delay is capped at max_delay."""
        from quadkit.http.retry.policy import _calculate_delay

        config = RetryConfig(backoff_factor=10.0, max_delay=5.0, jitter=False)
        delay = _calculate_delay(5, config, base_delay=1.0)
        assert delay == 5.0

    def test_calculate_delay_with_jitter(self) -> None:
        """Jitter randomizes delay within expected range."""
        from quadkit.http.retry.policy import _calculate_delay

        config = RetryConfig(backoff_factor=2.0, max_delay=60.0, jitter=0.5)
        delay = _calculate_delay(0, config, base_delay=1.0)
        assert 0.5 <= delay <= 1.5

        delay_attempt1 = _calculate_delay(1, config, base_delay=1.0)
        assert 1.0 <= delay_attempt1 <= 3.0

    def test_calculate_delay_default_jitter(self) -> None:
        """Boolean jitter=True uses default jitter range of 0.5."""
        from quadkit.http.retry.policy import _calculate_delay

        config = RetryConfig(backoff_factor=2.0, max_delay=60.0, jitter=True)
        delay = _calculate_delay(0, config, base_delay=1.0)
        assert 0.5 <= delay <= 1.5

    def test_calculate_delay_zero_base(self) -> None:
        """Zero base delay yields zero delay."""
        from quadkit.http.retry.policy import _calculate_delay

        config = RetryConfig(backoff_factor=2.0, max_delay=60.0, jitter=False)
        delay = _calculate_delay(5, config, base_delay=0.0)
        assert delay == 0.0
