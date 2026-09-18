"""Tests for token engineering protocols and types."""

from __future__ import annotations

import pytest

from quadkit.contracts.ai.llm import (
    ChatMessage,
    PromptAssemblerProtocol,
    Role,
    SemanticCacheProtocol,
    TokenBudget,
    TokenCounterProtocol,
)
from quadkit.contracts.ai.rag import PromptCompressorProtocol
from quadkit.contracts.ai.session import ContextPrunerProtocol


class TestTokenBudget:
    """Test TokenBudget value object."""

    def test_create_token_budget(self) -> None:
        """Test creating a TokenBudget."""
        budget = TokenBudget(
            model_context_limit=4096,
            reserved_for_output=256,
            system_prompt_tokens=100,
            tool_definitions_tokens=50,
        )
        assert budget.model_context_limit == 4096
        assert budget.reserved_for_output == 256
        assert budget.system_prompt_tokens == 100
        assert budget.tool_definitions_tokens == 50
        assert budget.rag_context_tokens == 0
        assert budget.history_tokens == 0

    def test_total_used_calculation(self) -> None:
        """Test total_used property."""
        budget = TokenBudget(
            model_context_limit=4096,
            reserved_for_output=256,
            system_prompt_tokens=100,
            tool_definitions_tokens=50,
            rag_context_tokens=200,
            history_tokens=300,
        )
        # 100 + 50 + 200 + 300 + 256 = 906
        assert budget.total_used == 906

    def test_remaining_calculation(self) -> None:
        """Test remaining property."""
        budget = TokenBudget(
            model_context_limit=4096,
            reserved_for_output=256,
            system_prompt_tokens=100,
            tool_definitions_tokens=50,
            rag_context_tokens=200,
            history_tokens=300,
        )
        # 4096 - 906 = 3190
        assert budget.remaining == 3190

    def test_remaining_clamped_to_zero(self) -> None:
        """Test that remaining never goes negative."""
        budget = TokenBudget(
            model_context_limit=400,
            reserved_for_output=256,
            system_prompt_tokens=100,
            tool_definitions_tokens=100,
        )
        assert budget.remaining == 0

    def test_remaining_for_history(self) -> None:
        """Test remaining_for_history property."""
        budget = TokenBudget(
            model_context_limit=4096,
            reserved_for_output=256,
            system_prompt_tokens=100,
            tool_definitions_tokens=50,
            rag_context_tokens=200,
            history_tokens=300,
        )
        # 4096 - (100 + 50 + 200 + 256) = 3490
        assert budget.remaining_for_history == 3490

    def test_over_budget_false(self) -> None:
        """Test over_budget when under limit."""
        budget = TokenBudget(
            model_context_limit=4096,
            reserved_for_output=256,
            system_prompt_tokens=100,
            tool_definitions_tokens=50,
        )
        assert not budget.over_budget

    def test_over_budget_true(self) -> None:
        """Test over_budget when exceeding limit."""
        budget = TokenBudget(
            model_context_limit=500,
            reserved_for_output=256,
            system_prompt_tokens=100,
            tool_definitions_tokens=100,
            rag_context_tokens=100,
            history_tokens=100,
        )
        # total = 100 + 100 + 100 + 100 + 256 = 656 > 500
        assert budget.over_budget

    def test_with_rag_tokens(self) -> None:
        """Test with_rag_tokens creates new immutable instance."""
        budget1 = TokenBudget(
            model_context_limit=4096,
            reserved_for_output=256,
            system_prompt_tokens=100,
            tool_definitions_tokens=50,
            rag_context_tokens=0,
        )
        budget2 = budget1.with_rag_tokens(500)

        # Original unchanged
        assert budget1.rag_context_tokens == 0
        assert budget1.remaining == 3690

        # New instance has updated RAG tokens
        assert budget2.rag_context_tokens == 500
        assert budget2.remaining == 3190

        # Verify other fields are preserved
        assert budget2.model_context_limit == 4096
        assert budget2.reserved_for_output == 256
        assert budget2.system_prompt_tokens == 100
        assert budget2.tool_definitions_tokens == 50

    def test_with_history_tokens(self) -> None:
        """Test with_history_tokens creates new immutable instance."""
        budget1 = TokenBudget(
            model_context_limit=4096,
            reserved_for_output=256,
            system_prompt_tokens=100,
            tool_definitions_tokens=50,
            history_tokens=0,
        )
        budget2 = budget1.with_history_tokens(800)

        # Original unchanged
        assert budget1.history_tokens == 0
        assert budget1.remaining == 3690

        # New instance has updated history tokens
        assert budget2.history_tokens == 800
        assert budget2.remaining == 2890

        # Verify other fields are preserved
        assert budget2.model_context_limit == 4096
        assert budget2.reserved_for_output == 256
        assert budget2.system_prompt_tokens == 100

    def test_frozen_prevents_direct_mutation(self) -> None:
        """Test that frozen=True prevents direct mutation."""
        budget = TokenBudget(
            model_context_limit=4096,
            reserved_for_output=256,
            system_prompt_tokens=100,
            tool_definitions_tokens=50,
        )
        with pytest.raises(AttributeError):
            budget.rag_context_tokens = 100

    def test_chaining_builder_methods(self) -> None:
        """Test chaining with_* builder methods."""
        budget = TokenBudget(
            model_context_limit=4096,
            reserved_for_output=256,
            system_prompt_tokens=100,
            tool_definitions_tokens=50,
        )
        updated = budget.with_rag_tokens(300).with_history_tokens(600)

        assert updated.rag_context_tokens == 300
        assert updated.history_tokens == 600
        # 100 + 50 + 300 + 600 + 256 = 1306
        assert updated.total_used == 1306
        assert updated.remaining == 2790


class TestTokenCounterProtocol:
    """Test TokenCounterProtocol isinstance checks."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """Test that TokenCounterProtocol supports isinstance checks."""

        class MockTokenCounter:
            """Mock implementation of TokenCounterProtocol."""

            def count(self, text: str) -> int:
                return len(text.split())

            def count_messages(self, messages: list[ChatMessage]) -> int:
                return sum(len(m.content.split()) for m in messages)

            @property
            def model(self) -> str:
                return "gpt-4"

        counter = MockTokenCounter()
        assert isinstance(counter, TokenCounterProtocol)

    def test_protocol_rejects_incomplete_implementation(self) -> None:
        """Test that incomplete implementations don't satisfy the protocol."""

        class IncompleteCounter:
            """Missing required methods."""

            @property
            def model(self) -> str:
                return "gpt-4"

        counter = IncompleteCounter()
        assert not isinstance(counter, TokenCounterProtocol)


class TestPromptAssemblerProtocol:
    """Test PromptAssemblerProtocol isinstance checks."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """Test that PromptAssemblerProtocol supports isinstance checks."""

        class MockAssembler:
            """Mock implementation of PromptAssemblerProtocol."""

            def assemble(
                self,
                system: str,
                tools: list[dict] | None,
                reference_docs: list[str] | None,
                few_shot: list[ChatMessage] | None,
                history: list[ChatMessage],
                query: str,
                provider: str,
                dynamic_metadata: str | None = None,
            ) -> list[ChatMessage]:
                messages: list[ChatMessage] = []
                if system:
                    messages.append(ChatMessage(role=Role.SYSTEM, content=system))
                messages.extend(history)
                messages.append(ChatMessage(role=Role.USER, content=query))
                return messages

        assembler = MockAssembler()
        assert isinstance(assembler, PromptAssemblerProtocol)


class TestSemanticCacheProtocol:
    """Test SemanticCacheProtocol isinstance checks."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """Test that SemanticCacheProtocol supports isinstance checks."""

        class MockSemanticCache:
            """Mock implementation of SemanticCacheProtocol."""

            async def lookup(self, query: str) -> str | None:
                return None

            async def store(self, query: str, response: str, model: str) -> None:
                pass

            async def invalidate(self, query: str) -> bool:
                return False

        cache = MockSemanticCache()
        assert isinstance(cache, SemanticCacheProtocol)


class TestPromptCompressorProtocol:
    """Test PromptCompressorProtocol isinstance checks."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """Test that PromptCompressorProtocol supports isinstance checks."""

        class MockCompressor:
            """Mock implementation of PromptCompressorProtocol."""

            async def compress(
                self,
                text: str,
                target_token_count: int,
                force_tokens: list[str] | None = None,
            ) -> str:
                return text[: target_token_count * 4]

        compressor = MockCompressor()
        assert isinstance(compressor, PromptCompressorProtocol)


class TestContextPrunerProtocol:
    """Test ContextPrunerProtocol isinstance checks."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """Test that ContextPrunerProtocol supports isinstance checks."""

        class MockPruner:
            """Mock implementation of ContextPrunerProtocol."""

            async def prune(
                self,
                history: list[ChatMessage],
                current_query: str,
                max_turns: int,
            ) -> list[ChatMessage]:
                return history[-max_turns:] if len(history) > max_turns else history

        pruner = MockPruner()
        assert isinstance(pruner, ContextPrunerProtocol)
