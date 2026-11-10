"""Unit tests for TokenOptimizedPipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.llm.recipes.token_optimized import TokenOptimizedPipeline
from quadkit.contracts.ai.exceptions import AIError, LLMError
from quadkit.contracts.ai.llm import ChatMessage, Role
from quadkit.contracts.ai.rag import RAGResponse
from quadkit.result import Err, Ok


class TestTokenOptimizedPipeline:
    """Test suite for TokenOptimizedPipeline."""

    @pytest.fixture
    def mock_counter(self) -> MagicMock:
        """Mock TokenCounterProtocol."""
        counter = MagicMock()
        counter.count = MagicMock(return_value=100)
        counter.count_messages = MagicMock(return_value=150)
        counter.model = "gpt-4"
        return counter

    @pytest.fixture
    def mock_assembler(self) -> MagicMock:
        """Mock PromptAssemblerProtocol."""
        assembler = MagicMock()
        messages = [
            ChatMessage(role=Role.SYSTEM, content="You are helpful."),
            ChatMessage(role=Role.USER, content="What is 2+2?"),
        ]
        assembler.assemble = MagicMock(return_value=messages)
        return assembler

    @pytest.fixture
    def mock_llm_client(self) -> MagicMock:
        """Mock LLMClientProtocol."""
        client = MagicMock()
        completion = MagicMock()
        completion.content = "The answer is 4."
        completion.model = "gpt-4"
        client.complete = AsyncMock(return_value=Ok(completion))
        return client

    @pytest.fixture
    def mock_semantic_cache(self) -> MagicMock:
        """Mock SemanticCacheProtocol."""
        cache = MagicMock()
        cache.lookup = AsyncMock(return_value=None)
        cache.store = AsyncMock(return_value=None)
        return cache

    @pytest.fixture
    def mock_context_pruner(self) -> MagicMock:
        """Mock ContextPrunerProtocol."""
        pruner = MagicMock()
        pruned_history = [
            ChatMessage(role=Role.USER, content="Previous question"),
            ChatMessage(role=Role.ASSISTANT, content="Previous answer"),
        ]
        pruner.prune = AsyncMock(return_value=pruned_history)
        return pruner

    @pytest.fixture
    def mock_compressor(self) -> MagicMock:
        """Mock PromptCompressorProtocol."""
        compressor = MagicMock()
        compressor.compress = AsyncMock(return_value="Compressed text.")
        return compressor

    @pytest.fixture
    def mock_rag_pipeline(self) -> MagicMock:
        """Mock RAGPipelineProtocol."""
        rag = MagicMock()
        source = MagicMock()
        source.text = "Retrieved document text."
        response = RAGResponse(answer="From RAG", sources=[source])
        rag.execute = AsyncMock(return_value=Ok(response))
        return rag

    @pytest.fixture
    def pipeline_with_all_services(
        self,
        mock_counter: MagicMock,
        mock_assembler: MagicMock,
        mock_llm_client: MagicMock,
        mock_semantic_cache: MagicMock,
        mock_context_pruner: MagicMock,
        mock_compressor: MagicMock,
        mock_rag_pipeline: MagicMock,
    ) -> TokenOptimizedPipeline:
        """Create pipeline with all optional services."""
        return TokenOptimizedPipeline(
            counter=mock_counter,
            assembler=mock_assembler,
            llm_client=mock_llm_client,
            semantic_cache=mock_semantic_cache,
            context_pruner=mock_context_pruner,
            compressor=mock_compressor,
            rag_pipeline=mock_rag_pipeline,
        )

    @pytest.fixture
    def pipeline_minimal(
        self,
        mock_counter: MagicMock,
        mock_assembler: MagicMock,
        mock_llm_client: MagicMock,
    ) -> TokenOptimizedPipeline:
        """Create pipeline with only required services."""
        return TokenOptimizedPipeline(
            counter=mock_counter,
            assembler=mock_assembler,
            llm_client=mock_llm_client,
        )

    @pytest.mark.asyncio
    async def test_cache_hit_skips_all_stages(
        self,
        pipeline_with_all_services: TokenOptimizedPipeline,
        mock_semantic_cache: MagicMock,
        mock_context_pruner: MagicMock,
        mock_rag_pipeline: MagicMock,
        mock_llm_client: MagicMock,
    ) -> None:
        """Semantic cache hit should skip all stages and return immediately."""
        mock_semantic_cache.lookup = AsyncMock(return_value="Cached response text.")

        result = await pipeline_with_all_services.execute(query="What is AI?")

        assert result.is_ok()
        assert result.unwrap() == "Cached response text."

        # Verify that later stages were skipped
        mock_context_pruner.prune.assert_not_called()
        mock_rag_pipeline.execute.assert_not_called()
        mock_llm_client.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_full_pipeline_without_optional_services(
        self,
        pipeline_minimal: TokenOptimizedPipeline,
    ) -> None:
        """Pipeline works with only required services."""
        result = await pipeline_minimal.execute(
            query="What is 2+2?",
            system="You are helpful.",
        )

        assert result.is_ok()
        assert result.unwrap() == "The answer is 4."

    @pytest.mark.asyncio
    async def test_returns_sanitized_result_err_on_llm_failure(
        self,
        pipeline_minimal: TokenOptimizedPipeline,
        mock_llm_client: MagicMock,
        capsys,
    ) -> None:
        """LLM provider text is omitted from errors and logs."""
        secret = "TOKEN_PIPELINE_LLM_SECRET_SENTINEL"
        llm_error = LLMError(secret)
        mock_llm_client.complete = AsyncMock(return_value=Err(llm_error))

        result = await pipeline_minimal.execute(query="What is AI?")

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, AIError)
        assert secret not in str(error)
        assert secret not in repr(error.to_dict())
        captured = capsys.readouterr()
        assert secret not in captured.out + captured.err

    @pytest.mark.asyncio
    async def test_caches_result_after_llm_call(
        self,
        pipeline_with_all_services: TokenOptimizedPipeline,
        mock_semantic_cache: MagicMock,
    ) -> None:
        """After successful LLM call, result should be cached."""
        mock_semantic_cache.lookup = AsyncMock(return_value=None)

        result = await pipeline_with_all_services.execute(
            query="What is the capital of France?",
            provider="openai",
        )

        assert result.is_ok()
        mock_semantic_cache.store.assert_called_once()
        call_args = mock_semantic_cache.store.call_args
        assert call_args[1]["query"] == "What is the capital of France?"
        assert call_args[1]["response"] == "The answer is 4."
        assert call_args[1]["model"] == "openai"

    @pytest.mark.asyncio
    async def test_cache_store_failure_does_not_log_exception_text(
        self,
        pipeline_with_all_services: TokenOptimizedPipeline,
        mock_semantic_cache: MagicMock,
        capsys,
    ) -> None:
        secret = "TOKEN_PIPELINE_CACHE_SECRET_SENTINEL"
        mock_semantic_cache.lookup = AsyncMock(return_value=None)
        mock_semantic_cache.store = AsyncMock(side_effect=RuntimeError(secret))

        result = await pipeline_with_all_services.execute(query="private query")

        assert result.is_ok()
        captured = capsys.readouterr()
        assert secret not in captured.out + captured.err

    @pytest.mark.asyncio
    async def test_context_pruning_when_history_provided(
        self,
        pipeline_with_all_services: TokenOptimizedPipeline,
        mock_context_pruner: MagicMock,
        mock_semantic_cache: MagicMock,
    ) -> None:
        """Context pruning should be called when history is provided."""
        mock_semantic_cache.lookup = AsyncMock(return_value=None)
        history = [
            ChatMessage(role=Role.USER, content="First question"),
            ChatMessage(role=Role.ASSISTANT, content="First answer"),
            ChatMessage(role=Role.USER, content="Second question"),
            ChatMessage(role=Role.ASSISTANT, content="Second answer"),
        ]

        result = await pipeline_with_all_services.execute(
            query="What is AI?",
            history=history,
        )

        assert result.is_ok()
        mock_context_pruner.prune.assert_called_once()
        call_args = mock_context_pruner.prune.call_args
        assert call_args[1]["history"] == history
        assert call_args[1]["current_query"] == "What is AI?"
        assert call_args[1]["max_turns"] == 10

    @pytest.mark.asyncio
    async def test_rag_pipeline_integration_on_success(
        self,
        pipeline_with_all_services: TokenOptimizedPipeline,
        mock_rag_pipeline: MagicMock,
        mock_semantic_cache: MagicMock,
    ) -> None:
        """RAG pipeline should be called and its results integrated."""
        mock_semantic_cache.lookup = AsyncMock(return_value=None)

        result = await pipeline_with_all_services.execute(
            query="What is in the knowledge base?",
        )

        assert result.is_ok()
        mock_rag_pipeline.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_rag_failure_does_not_log_query_or_error_text(
        self,
        pipeline_with_all_services: TokenOptimizedPipeline,
        mock_rag_pipeline: MagicMock,
        mock_semantic_cache: MagicMock,
        capsys,
    ) -> None:
        """RAG errors and the user query are not written to logs."""
        secret = "TOKEN_PIPELINE_RAG_SECRET_SENTINEL"
        mock_semantic_cache.lookup = AsyncMock(return_value=None)
        rag_error = AIError(secret)
        mock_rag_pipeline.execute = AsyncMock(return_value=Err(rag_error))

        result = await pipeline_with_all_services.execute(
            query=f"What is in the knowledge base? {secret}",
        )

        # Pipeline should still succeed despite RAG failure
        assert result.is_ok()
        assert result.unwrap() == "The answer is 4."
        captured = capsys.readouterr()
        assert secret not in captured.out + captured.err

    @pytest.mark.asyncio
    async def test_compression_on_token_budget_exceeded(
        self,
        pipeline_with_all_services: TokenOptimizedPipeline,
        mock_compressor: MagicMock,
        mock_counter: MagicMock,
        mock_semantic_cache: MagicMock,
    ) -> None:
        """Compressor should be called when token budget is exceeded."""
        mock_semantic_cache.lookup = AsyncMock(return_value=None)
        # Make counter return high token count for reference docs
        mock_counter.count = MagicMock(side_effect=[5000, 200])

        result = await pipeline_with_all_services.execute(
            query="What is AI?",
        )

        assert result.is_ok()
        # Compressor should be called since 5000 > available_tokens
        mock_compressor.compress.assert_called_once()
        call_args = mock_compressor.compress.call_args
        assert call_args[1]["target_token_count"] == (4096 - 500) // 2

    @pytest.mark.asyncio
    async def test_assembler_receives_all_components(
        self,
        pipeline_with_all_services: TokenOptimizedPipeline,
        mock_assembler: MagicMock,
        mock_semantic_cache: MagicMock,
        mock_context_pruner: MagicMock,
    ) -> None:
        """Assembler receives system, tools, docs, few-shot, history, and query."""
        mock_semantic_cache.lookup = AsyncMock(return_value=None)

        few_shot_examples = [
            ChatMessage(role=Role.USER, content="Example 1"),
            ChatMessage(role=Role.ASSISTANT, content="Response 1"),
        ]
        tools = [{"name": "calculator", "description": "Does math"}]

        result = await pipeline_with_all_services.execute(
            query="What is 5+3?",
            system="You are a math tutor.",
            few_shot=few_shot_examples,
            tools=tools,
        )

        assert result.is_ok()
        mock_assembler.assemble.assert_called_once()
        call_args = mock_assembler.assemble.call_args
        assert call_args[1]["system"] == "You are a math tutor."
        assert call_args[1]["tools"] == tools
        assert call_args[1]["few_shot"] == few_shot_examples
        assert call_args[1]["query"] == "What is 5+3?"
