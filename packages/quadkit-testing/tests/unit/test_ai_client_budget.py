"""Unit tests for AITestClient token budget (M45)."""

from __future__ import annotations

import pytest

from quadkit.testing.clients.ai.client import AITestClient
from quadkit.testing.clients.ai.data import AITestData
from quadkit.testing.exceptions import TokenBudgetExceededError


class _FakeTestBed:
    """Minimal stand-in for an AITestBed."""

    def __init__(self) -> None:
        self.test_data = AITestData()


class TestAITestClientTokenBudget:
    """AITestClient enforces a configurable per-run token budget."""

    def _client(self, *, max_tokens: int = 10_000) -> AITestClient:
        return AITestClient(_FakeTestBed(), max_tokens_per_run=max_tokens)

    # -- properties --

    def test_initial_tokens_used_is_zero(self) -> None:
        client = self._client()
        assert client.tokens_used == 0

    def test_token_budget_reflects_constructor_argument(self) -> None:
        client = self._client(max_tokens=500)
        assert client.token_budget == 500

    def test_reset_token_budget_zeroes_usage(self) -> None:
        client = self._client(max_tokens=1000)
        client._charge_tokens(100)
        assert client.tokens_used == 100

        client.reset_token_budget()

        assert client.tokens_used == 0

    # -- charge_tokens --

    def test_charge_tokens_accumulates(self) -> None:
        client = self._client(max_tokens=1000)
        client._charge_tokens(300)
        client._charge_tokens(200)
        assert client.tokens_used == 500

    def test_charge_tokens_raises_when_budget_exceeded(self) -> None:
        client = self._client(max_tokens=100)

        with pytest.raises(TokenBudgetExceededError):
            client._charge_tokens(101)

    def test_charge_tokens_allows_exactly_at_limit(self) -> None:
        client = self._client(max_tokens=100)
        # Should not raise
        client._charge_tokens(100)
        assert client.tokens_used == 100

    def test_charge_tokens_unlimited_when_budget_is_zero(self) -> None:
        client = self._client(max_tokens=0)
        client._charge_tokens(1_000_000)
        assert client.tokens_used == 0  # unlimited; no tracking needed

    # -- complete_with_llm --

    @pytest.mark.asyncio
    async def test_complete_with_llm_records_completion(self) -> None:
        client = self._client()
        result = await client.complete_with_llm("hello world")
        assert result["prompt"] == "hello world"

    @pytest.mark.asyncio
    async def test_complete_with_llm_uses_tokens_from_mock_response(self) -> None:
        client = self._client(max_tokens=1000)
        client.test_data.set_mock_response("llm", {"response": "ok", "tokens": 50})

        await client.complete_with_llm("prompt")

        assert client.tokens_used == 50

    @pytest.mark.asyncio
    async def test_complete_with_llm_estimates_tokens_when_not_in_mock(self) -> None:
        import math

        client = self._client(max_tokens=10_000)
        prompt = "one two three four five"  # 5 words → ceil(5 * 1.3) = 7

        await client.complete_with_llm(prompt)

        assert client.tokens_used == math.ceil(5 * 1.3)

    @pytest.mark.asyncio
    async def test_complete_with_llm_raises_token_budget_exceeded(self) -> None:
        client = self._client(max_tokens=10)
        client.test_data.set_mock_response("llm", {"response": "ok", "tokens": 100})

        with pytest.raises(TokenBudgetExceededError):
            await client.complete_with_llm("too many tokens")

    # -- TokenBudgetExceededError message --

    def test_token_budget_exceeded_error_contains_usage_info(self) -> None:
        with pytest.raises(TokenBudgetExceededError) as exc_info:
            raise TokenBudgetExceededError(tokens_used=80, token_budget=100)

        message = str(exc_info.value)
        assert "80" in message
        assert "100" in message
