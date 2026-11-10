"""Token accounting across agent strategies.

Verifies every strategy reports prompt/completion/total token usage from
completion usage data (function_calling already counts; the other
strategies must too, or cost estimation in the executor never fires).
"""

from __future__ import annotations

import pytest

from quadkit.ai.agents.strategies.token_utils import (
    TokenAccumulator,
    count_tokens,
    token_split,
)


class FakeUsage:
    prompt_tokens = 100
    completion_tokens = 40
    total_tokens = 140


class FakeCompletion:
    def __init__(self, content: str = "ok", usage: object | None = None) -> None:
        self.content = content
        self.usage = usage


class FakeResult:
    def __init__(self, completion: FakeCompletion) -> None:
        self._completion = completion

    def is_ok(self) -> bool:
        return True

    def unwrap(self) -> FakeCompletion:
        return self._completion


class FakeLLM:
    """Minimal LLM client that returns completions with token usage."""

    def __init__(self, responses: list[FakeCompletion]) -> None:
        self.responses = responses
        self.call_count = 0

    async def complete(self, messages: object, **kwargs: object) -> FakeResult:
        completion = self.responses[self.call_count]
        self.call_count += 1
        return FakeResult(completion)


class TestTokenUtils:
    def test_token_split_object_usage(self) -> None:
        completion = FakeCompletion("ok", FakeUsage())
        assert token_split(completion) == (100, 40)

    def test_token_split_dict_usage(self) -> None:
        completion = FakeCompletion(
            "ok", {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        )
        assert token_split(completion) == (10, 5)

    def test_token_split_missing_usage(self) -> None:
        assert token_split(FakeCompletion("ok")) == (0, 0)

    def test_count_tokens_prefers_split(self) -> None:
        assert count_tokens(FakeCompletion("ok", FakeUsage())) == 140

    def test_count_tokens_falls_back_to_total(self) -> None:
        completion = FakeCompletion("ok", {"total_tokens": 15})
        assert count_tokens(completion) == 15

    def test_count_tokens_missing_usage(self) -> None:
        assert count_tokens(FakeCompletion("ok")) == 0

    @pytest.mark.asyncio
    async def test_accumulator_sums_multiple_completions(self) -> None:
        acc = TokenAccumulator()
        acc.add(FakeCompletion("a", FakeUsage()))
        acc.add(FakeCompletion("b", {"prompt_tokens": 3, "completion_tokens": 2}))
        acc.add(FakeCompletion("c"))
        assert acc.prompt_tokens == 103
        assert acc.completion_tokens == 42
        assert acc.total_tokens == 145


class TestReActTokens:
    @pytest.mark.asyncio
    async def test_react_reports_token_usage(self) -> None:
        from quadkit.ai.agents.strategies.react import ReActStrategy

        llm = FakeLLM([FakeCompletion("FINAL_ANSWER: done", FakeUsage())])
        strategy = ReActStrategy(max_iterations=1)
        result = await strategy.execute(message="hello", tools=[], history=[], llm=llm)  # type: ignore[arg-type]
        assert result.is_ok()
        response = result.unwrap()
        assert response.total_tokens == 140
        assert response.prompt_tokens == 100
        assert response.completion_tokens == 40


class TestSupervisorTokens:
    @pytest.mark.asyncio
    async def test_supervisor_reports_token_usage(self) -> None:
        from quadkit.ai.agents.strategies.supervisor import SupervisorStrategy

        llm = FakeLLM([FakeCompletion("FINAL_ANSWER: done", FakeUsage())])
        strategy = SupervisorStrategy(
            sub_agents={}, executor=object(), max_delegations=1
        )  # type: ignore[arg-type]
        result = await strategy.execute(message="hello", tools=[], history=[], llm=llm)  # type: ignore[arg-type]
        assert result.is_ok()
        response = result.unwrap()
        assert response.total_tokens == 140
        assert response.prompt_tokens == 100
        assert response.completion_tokens == 40


class TestReflexionTokens:
    @pytest.mark.asyncio
    async def test_reflexion_reports_token_usage(self) -> None:
        from quadkit.ai.agents.strategies.reflexion import ReflexionStrategy

        # max_iterations=0 → only the initial generation call runs.
        llm = FakeLLM([FakeCompletion("initial answer", FakeUsage())])
        strategy = ReflexionStrategy(max_iterations=0)
        result = await strategy.execute(message="hello", tools=[], history=[], llm=llm)  # type: ignore[arg-type]
        assert result.is_ok()
        response = result.unwrap()
        assert response.total_tokens == 140
        assert response.prompt_tokens == 100
        assert response.completion_tokens == 40


class TestPlanExecuteTokens:
    @pytest.mark.asyncio
    async def test_plan_execute_reports_token_usage_on_direct_fallback(self) -> None:
        from quadkit.ai.agents.strategies.plan_execute import PlanAndExecuteStrategy

        # Text without a parseable plan → direct-synthesis path (1 LLM call).
        llm = FakeLLM([FakeCompletion("unparseable plan text", FakeUsage())])
        strategy = PlanAndExecuteStrategy(max_steps=5, max_replans=0)
        result = await strategy.execute(message="hello", tools=[], history=[], llm=llm)  # type: ignore[arg-type]
        assert result.is_ok()
        response = result.unwrap()
        assert response.total_tokens == 140
        assert response.prompt_tokens == 100
        assert response.completion_tokens == 40
