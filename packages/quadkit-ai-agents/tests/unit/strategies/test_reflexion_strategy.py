"""Unit tests for ReflexionStrategy."""

from __future__ import annotations

import pytest

from quadkit.ai.agents.strategies.reflexion import ReflexionStrategy


class MockResponse:
    """Mock LLM response."""

    def __init__(self, content: str):
        self.content = content

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self):
        return self


class MockLLM:
    """Mock LLM for testing."""

    def __init__(self, responses: list[str]):
        self.responses = responses
        self.call_count = 0

    async def complete(self, messages, **kwargs):
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return MockResponse(resp)
        return MockResponse("Final answer")


class TestReflexionStrategy:
    """Tests for ReflexionStrategy."""

    def test_reflexion_strategy_init(self) -> None:
        """Test ReflexionStrategy initialization."""
        strategy = ReflexionStrategy(max_iterations=3)
        assert strategy.max_iterations == 3
        assert strategy.temperature_critique == 0.3
        assert strategy.temperature_refine == 0.5

    def test_reflexion_strategy_default_values(self) -> None:
        """Test ReflexionStrategy has sensible defaults."""
        strategy = ReflexionStrategy()
        assert strategy.max_iterations == 3
        assert strategy.temperature_critique == 0.3
        assert strategy.temperature_refine == 0.5

    @pytest.mark.asyncio
    async def test_reflexion_single_pass(self) -> None:
        """Test reflexion with single pass (no refinement)."""
        strategy = ReflexionStrategy(max_iterations=1)
        mock_llm = MockLLM(responses=[
            "Initial response about quantum computing",
            "The response looks good. NO_CHANGES_NEEDED",
        ])

        result = await strategy.execute(
            message="Explain quantum computing",
            tools=[],
            history=[],
            llm=mock_llm,
        )

        assert result.is_ok()
        response = result.unwrap()
        assert "quantum" in response.message.lower()
        assert len(response.steps) >= 1

    @pytest.mark.asyncio
    async def test_reflexion_with_critique_and_refine(self) -> None:
        """Test reflexion with critique and refinement loop."""
        strategy = ReflexionStrategy(max_iterations=2)
        mock_llm = MockLLM(responses=[
            "Initial response",
            "The response is missing details about qubits. NO_CHANGES_NEEDED",
            "Refined response with qubit details",
        ])

        result = await strategy.execute(
            message="Explain quantum computing",
            tools=[],
            history=[],
            llm=mock_llm,
        )

        assert result.is_ok()
        response = result.unwrap()
        assert len(response.steps) >= 2

    @pytest.mark.asyncio
    async def test_reflexion_early_stopping(self) -> None:
        """Test reflexion stops early when NO_CHANGES_NEEDED."""
        strategy = ReflexionStrategy(max_iterations=5)
        mock_llm = MockLLM(responses=[
            "Initial response",
            "The response looks good. NO_CHANGES_NEEDED",
        ])

        result = await strategy.execute(
            message="What is 2+2?",
            tools=[],
            history=[],
            llm=mock_llm,
        )

        assert result.is_ok()
        response = result.unwrap()
        assert mock_llm.call_count == 2

    @pytest.mark.asyncio
    async def test_reflexion_multiple_iterations(self) -> None:
        """Test reflexion runs through multiple iterations."""
        strategy = ReflexionStrategy(max_iterations=3)
        mock_llm = MockLLM(responses=[
            "First response",
            "Critique: Add more details",
            "Second response",
            "Critique: Still missing specifics",
            "Third response",
            "Critique: Looks good. NO_CHANGES_NEEDED",
        ])

        result = await strategy.execute(
            message="Explain AI",
            tools=[],
            history=[],
            llm=mock_llm,
        )

        assert result.is_ok()
        response = result.unwrap()
        assert mock_llm.call_count == 6

    @pytest.mark.asyncio
    async def test_reflexion_with_history(self) -> None:
        """Test reflexion uses conversation history."""
        strategy = ReflexionStrategy(max_iterations=1)
        mock_llm = MockLLM(responses=["Response based on history"])

        history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]

        result = await strategy.execute(
            message="Follow-up question",
            tools=[],
            history=history,
            llm=mock_llm,
        )

        assert result.is_ok()
        response = result.unwrap()
        assert response.message is not None


class TestReflexionBuildMessages:
    """Tests for message building."""

    def test_build_messages_with_system_prompt(self) -> None:
        """Test message building includes system prompt."""
        strategy = ReflexionStrategy()

        messages = strategy._build_messages(
            message="Hello",
            history=[],
            system_prompt="You are a helpful assistant",
        )

        assert len(messages) == 2
        assert messages[0].role.value == "system"
        assert "helpful" in messages[0].content

    def test_build_messages_with_history(self) -> None:
        """Test message building includes history."""
        strategy = ReflexionStrategy()

        history = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ]

        messages = strategy._build_messages(
            message="How are you?",
            history=history,
            system_prompt="",
        )

        assert len(messages) == 3
        assert messages[-1].role.value == "user"
        assert "How are you?" in messages[-1].content
