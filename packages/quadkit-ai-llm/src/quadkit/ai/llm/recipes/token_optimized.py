"""Reference composition of all token engineering techniques.

This module implements the TokenOptimizedPipeline — a canonical orchestration
of token optimization services. It demonstrates how to compose semantic caching,
token budgeting, context pruning, RAG retrieval, prompt compression, and
assembly in a complete pipeline.

Note: This is documentation-as-code. Applications are expected to compose
services directly based on their specific needs.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from quadkit.ai.llm.exceptions import sanitize_llm_error
from quadkit.contracts.ai.rag import RAGContext
from quadkit.logging import get_logger, safe_error_type
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.ai.exceptions import AIError
    from quadkit.contracts.ai.llm import (
        ChatMessage,
        LLMClientProtocol,
        PromptAssemblerProtocol,
        SemanticCacheProtocol,
        TokenCounterProtocol,
    )
    from quadkit.contracts.ai.rag import (
        PromptCompressorProtocol,
        RAGPipelineProtocol,
    )
    from quadkit.contracts.ai.session import ContextPrunerProtocol

logger = get_logger(__name__)


class TokenOptimizedPipeline:
    """Reference composition of all token engineering techniques.

    This is NOT a required abstraction. It demonstrates the canonical
    composition pattern. Applications are expected to compose services
    directly based on their specific needs.

    Requires all relevant services to be registered in the container:
    - TokenCounterProtocol (from quadkit-ai-llm)
    - SemanticCacheProtocol (from quadkit-cache, optional)
    - ContextPrunerProtocol (from the optional provider, optional)
    - PromptCompressorProtocol (from the optional provider, optional)
    - PromptAssemblerProtocol (from the AI prompt layer)
    - LLMClientProtocol (from quadkit-ai-llm)
    """

    def __init__(
        self,
        counter: TokenCounterProtocol,
        assembler: PromptAssemblerProtocol,
        llm_client: LLMClientProtocol,
        semantic_cache: SemanticCacheProtocol | None = None,
        context_pruner: ContextPrunerProtocol | None = None,
        compressor: PromptCompressorProtocol | None = None,
        rag_pipeline: RAGPipelineProtocol | None = None,
    ) -> None:
        """Initialize the token-optimized pipeline.

        Args:
            counter: Token counter for the target model.
            assembler: Prompt assembler with static-first ordering.
            llm_client: LLM client for completions.
            semantic_cache: Optional semantic cache for query deduplication.
            context_pruner: Optional context pruner for history relevance scoring.
            compressor: Optional prompt compressor for token budget compliance.
            rag_pipeline: Optional RAG pipeline for document retrieval.
        """
        self.counter = counter
        self.assembler = assembler
        self.llm_client = llm_client
        self.semantic_cache = semantic_cache
        self.context_pruner = context_pruner
        self.compressor = compressor
        self.rag_pipeline = rag_pipeline

    async def execute(
        self,
        query: str,
        history: Sequence[ChatMessage] | None = None,
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        few_shot: Sequence[ChatMessage] | None = None,
        provider: str = "openai",
        output_schema: type | None = None,
    ) -> Result[str, AIError]:
        """Execute the full token-optimized pipeline.

        Stages:
        1. Semantic cache lookup (skip everything if hit)
        2. Token budget calculation
        3. Context pruning (if history provided)
        4. RAG retrieval + reranking (if RAG pipeline configured)
        5. Compression (if over budget)
        6. Prompt assembly (static-first ordering + cache annotations)
        7. LLM call (with output constraints if schema provided)
        8. Cache storage + return

        Args:
            query: User query string.
            history: Optional conversation history.
            system: Optional system prompt.
            tools: Optional tool/function definitions.
            few_shot: Optional few-shot examples.
            provider: LLM provider key (e.g., "openai").
            output_schema: Optional output schema for structured extraction.

        Returns:
            Ok(response_text) on success, or Err(AIError) on recoverable failures.

        Raises:
            Infrastructure errors (connection failures, serialization bugs) propagate
            as exceptions and are not wrapped in Result.
        """
        try:
            # Stage 1: Semantic cache lookup
            logger.info(
                "token_pipeline_stage_1_cache_lookup",
                query_length=len(query),
                cache_enabled=self.semantic_cache is not None,
            )
            if self.semantic_cache:
                cached_response = await self.semantic_cache.lookup(query)
                if cached_response:
                    logger.info(
                        "token_pipeline_cache_hit",
                        query_length=len(query),
                    )
                    return Ok(cached_response)

            logger.info("token_pipeline_cache_miss")

            # Stage 2: Token budget calculation
            logger.info("token_pipeline_stage_2_budget_calculation")
            # Default budget: 4096 tokens (adjustable per provider)
            budget_tokens = 4096
            reserved_tokens = 500  # Reserve for response
            available_tokens = budget_tokens - reserved_tokens

            # Stage 3: Context pruning
            pruned_history: Sequence[ChatMessage] | None = history
            if history and self.context_pruner:
                logger.info(
                    "token_pipeline_stage_3_context_pruning",
                    history_length=len(history),
                )
                pruned_history = await self.context_pruner.prune(  # type: ignore[assignment]
                    history=history,
                    current_query=query,
                    max_turns=10,  # Configurable
                )
                logger.info(
                    "token_pipeline_pruned_history",
                    original_length=len(history) if history else 0,
                    pruned_length=len(pruned_history) if pruned_history else 0,
                )

            # Stage 4: RAG retrieval (if configured)
            reference_docs = None
            if self.rag_pipeline:
                logger.info(
                    "token_pipeline_stage_4_rag_retrieval",
                    query_length=len(query),
                )
                rag_context = RAGContext(query=query)
                rag_result = await self.rag_pipeline.execute(rag_context)

                if rag_result.is_ok():
                    rag_response = rag_result.unwrap()
                    reference_docs = [source.text for source in rag_response.sources]
                    logger.info(
                        "token_pipeline_rag_success",
                        source_count=len(reference_docs),
                    )
                else:
                    rag_error = rag_result.unwrap_err()
                    logger.warning(
                        "token_pipeline_rag_failure",
                        error_type=type(rag_error).__name__,
                    )

            # Stage 5: Compression (if over budget)
            compressed_system = system
            compressed_docs = reference_docs
            if reference_docs and self.compressor:
                combined_text = "\n".join(reference_docs)
                current_tokens = self.counter.count(combined_text)
                if current_tokens > available_tokens:
                    logger.info(
                        "token_pipeline_stage_5_compression",
                        current_tokens=current_tokens,
                        available_tokens=available_tokens,
                    )
                    compressed = await self.compressor.compress(
                        text=combined_text,
                        target_token_count=available_tokens // 2,
                    )
                    compressed_docs = [compressed]
                    logger.info(
                        "token_pipeline_compressed",
                        original_tokens=current_tokens,
                        compressed_tokens=self.counter.count(compressed),
                    )

            # Stage 6: Prompt assembly (static-first ordering + cache annotations)
            logger.info("token_pipeline_stage_6_prompt_assembly")
            assembled_messages = self.assembler.assemble(
                system=compressed_system,
                tools=tools,
                reference_docs=compressed_docs,
                few_shot=few_shot,  # type: ignore[arg-type]
                history=list(pruned_history or []),
                query=query,
                provider=provider,
            )

            # Stage 7: LLM call (with output constraints if schema provided)
            logger.info(
                "token_pipeline_stage_7_llm_call",
                has_schema=output_schema is not None,
            )
            kwargs: dict[str, Any] = {
                "messages": assembled_messages,
                "model": provider,
                "temperature": 0.7,
                "max_tokens": reserved_tokens,
            }
            if output_schema is not None:
                kwargs["output_schema"] = output_schema

            llm_result = await self.llm_client.complete(**kwargs)
            if llm_result.is_ok():
                completion = llm_result.unwrap()
            else:
                llm_error = llm_result.unwrap_err()
                logger.error(
                    "token_pipeline_llm_error",
                    error_type=safe_error_type(llm_error),
                )
                return Err(sanitize_llm_error(llm_error))
            response_text = completion.content

            # Stage 8: Cache storage + return
            logger.info("token_pipeline_stage_8_cache_storage")
            if self.semantic_cache:
                try:
                    await self.semantic_cache.store(
                        query=query,
                        response=response_text,
                        model=provider,
                    )
                    logger.info("token_pipeline_cache_stored")
                except Exception as e:  # noqa: BLE001 — semantic cache store is best-effort
                    logger.warning(
                        "token_pipeline_cache_store_error",
                        error_type=type(e).__name__,
                    )

            logger.info("token_pipeline_success")
            return Ok(response_text)

        except Exception as e:
            logger.error(
                "token_pipeline_fatal_error",
                error_type=type(e).__name__,
            )
            raise
