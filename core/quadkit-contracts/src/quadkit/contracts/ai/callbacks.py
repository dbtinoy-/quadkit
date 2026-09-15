"""Callback protocols for AI observability."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from quadkit.contracts.ai.llm import ChatMessage, Completion


@runtime_checkable
class CallbackHandlerProtocol(Protocol):
    """Protocol for AI callback handlers.

    Defines 12 callback methods for observing LLM, chain, tool, agent,
    and retriever operations. Implementations can subscribe to these
    events for logging, monitoring, or instrumentation.
    """

    async def on_llm_start(
        self,
        messages: list[ChatMessage],
        model: str,
        **kwargs: Any,
    ) -> None:
        """Called when an LLM call starts.

        Args:
            messages: The messages being sent to the LLM.
            model: The model being used.
            **kwargs: Additional provider-specific parameters.
        """
        ...

    async def on_llm_new_token(
        self,
        token: str,
        **kwargs: Any,
    ) -> None:
        """Called for each new token in a streaming LLM response.

        Args:
            token: The new token received.
            **kwargs: Additional context (e.g., run_id, model).
        """
        ...

    async def on_llm_end(
        self,
        response: Completion,
        **kwargs: Any,
    ) -> None:
        """Called when an LLM call completes successfully.

        Args:
            response: The completion response.
            **kwargs: Additional context (e.g., run_id, model).
        """
        ...

    async def on_llm_error(
        self,
        error: Exception,
        **kwargs: Any,
    ) -> None:
        """Called when an LLM call fails.

        Args:
            error: The exception that was raised.
            **kwargs: Additional context (e.g., run_id, model, messages).
        """
        ...

    async def on_chain_start(
        self,
        name: str,
        inputs: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Called when a chain/pipeline starts executing.

        Args:
            name: The name of the chain.
            inputs: The input parameters to the chain.
            **kwargs: Additional context.
        """
        ...

    async def on_chain_end(
        self,
        name: str,
        outputs: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Called when a chain/pipeline completes.

        Args:
            name: The name of the chain.
            outputs: The output from the chain.
            **kwargs: Additional context.
        """
        ...

    async def on_tool_start(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Called when a tool starts executing.

        Args:
            tool_name: The name of the tool being invoked.
            arguments: The arguments being passed to the tool.
            **kwargs: Additional context (e.g., run_id).
        """
        ...

    async def on_tool_end(
        self,
        tool_name: str,
        result: Any,
        **kwargs: Any,
    ) -> None:
        """Called when a tool finishes executing.

        Args:
            tool_name: The name of the tool that was invoked.
            result: The result from the tool.
            **kwargs: Additional context (e.g., run_id).
        """
        ...

    async def on_agent_action(
        self,
        action: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Called when an agent takes an action.

        Args:
            action: The action details (e.g., tool call, thought).
            **kwargs: Additional context (e.g., run_id).
        """
        ...

    async def on_agent_finish(
        self,
        response: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Called when an agent finishes executing.

        Args:
            response: The final response from the agent.
            **kwargs: Additional context (e.g., run_id).
        """
        ...

    async def on_retriever_start(
        self,
        query: str,
        **kwargs: Any,
    ) -> None:
        """Called when a retriever starts a search.

        Args:
            query: The search query.
            **kwargs: Additional context (e.g., run_id).
        """
        ...

    async def on_retriever_end(
        self,
        documents: list[Any],
        **kwargs: Any,
    ) -> None:
        """Called when a retriever completes a search.

        Args:
            documents: The retrieved documents.
            **kwargs: Additional context (e.g., run_id, query).
        """
        ...


@runtime_checkable
class CallbackManagerProtocol(Protocol):
    """Protocol for managing callback handlers.

    Manages registration and lifecycle of callback handlers, supporting
    hierarchical managers (parent-child) for run-scoped event propagation.
    """

    def register(self, handler: CallbackHandlerProtocol) -> None:
        """Register a callback handler.

        Args:
            handler: The handler to register.
        """
        ...

    def unregister(self, handler: CallbackHandlerProtocol) -> None:
        """Unregister a callback handler.

        Args:
            handler: The handler to remove.
        """
        ...

    def child(self, run_id: str) -> CallbackManagerProtocol:
        """Create a child callback manager for a specific run.

        The child manager inherits all handlers from the parent and
        can be used to scope callbacks to a specific execution run.

        Args:
            run_id: Unique identifier for this run.

        Returns:
            A child CallbackManagerProtocol instance.
        """
        ...


__all__ = [
    "CallbackHandlerProtocol",
    "CallbackManagerProtocol",
]
