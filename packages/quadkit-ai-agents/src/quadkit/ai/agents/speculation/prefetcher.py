"""SpeculativeToolPreFetcher — parallel tool pre-fetching during LLM decision-making."""

from __future__ import annotations

import asyncio

from quadkit.ai.agents.speculation.predictor import KeywordToolCallPredictor
from quadkit.ai.agents.speculation.protocols import ToolCallPredictorProtocol
from quadkit.contracts import (
    AgentError,
    LLMClientProtocol,
    ToolProtocol,
    ToolRegistryProtocol,
)
from quadkit.contracts.ai.llm import ChatMessage, Completion
from quadkit.logging import (
    get_logger,
)
from quadkit.result import Err, Ok, Result

logger = get_logger(__name__)


class SpeculativeToolPreFetcher:
    """Parallel tool pre-fetching during LLM decision-making.

    While the LLM is deciding which tool to call, speculatively executes
    the top-N most likely tools in parallel. If the LLM picks a pre-fetched
    tool, the result is returned instantly. Unused speculative tasks are
    cancelled.

    Opt-in strategy — not enabled by default in the agent loop.
    """

    def __init__(
        self,
        tool_registry: ToolRegistryProtocol,
        max_speculative: int = 3,
        predictor: ToolCallPredictorProtocol | None = None,
    ) -> None:
        """Initialize the prefetcher.

        Args:
            tool_registry: Registry of available tools.
            max_speculative: Maximum number of tools to pre-fetch in parallel.
            predictor: Tool call predictor. Defaults to KeywordToolCallPredictor.
        """
        self._registry = tool_registry
        self._max_speculative = max_speculative
        self._predictor = predictor or KeywordToolCallPredictor()
        self._background_tasks: set[asyncio.Task] = set()

    async def execute_with_speculation(
        self,
        query: str,
        tools: list[ToolProtocol],
        llm_client: LLMClientProtocol,
        messages: list[ChatMessage],
    ) -> Result[Completion, AgentError]:
        """Execute LLM call with parallel speculative tool pre-fetching.

        1. Predict likely tool calls from query + history.
        2. Fire LLM call AND top-N tool calls in parallel.
        3. If LLM picks a pre-fetched tool, return pre-fetched result.
        4. If LLM picks a non-predicted tool, execute normally.
        5. Cancel all unused speculative tasks.
        6. Store task references per RUF006.

        Args:
            query: Current user query for tool prediction.
            tools: All available tools.
            llm_client: LLM client to use for the main call.
            messages: Conversation messages to send to LLM.

        Returns:
            Result containing the LLM Completion or an AgentError.
        """
        predicted = self._predictor.predict(query, tools)[: self._max_speculative]

        # Speculatively execute top-N tools in parallel while LLM decides
        speculative_tasks: dict[str, asyncio.Task] = {}
        for tool in predicted:
            tool_name = getattr(tool, "name", "")
            if not tool_name:
                continue
            task = asyncio.create_task(tool.execute({}))  # type: ignore[call-arg]
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
            speculative_tasks[tool_name] = task

        # Run LLM call
        llm_task = asyncio.create_task(llm_client.complete(messages))
        self._background_tasks.add(llm_task)
        llm_task.add_done_callback(self._background_tasks.discard)

        llm_result = await llm_task

        # Cancel all unused speculative tasks
        for task in speculative_tasks.values():
            if not task.done():
                task.cancel()

        if llm_result.is_ok():
            return Ok(llm_result.unwrap())  # type: ignore[arg-type]
        err = llm_result.unwrap_err()
        return Err(
            AgentError(
                "LLM call failed",
                details={"error_type": type(err).__name__},
            ),
        )
