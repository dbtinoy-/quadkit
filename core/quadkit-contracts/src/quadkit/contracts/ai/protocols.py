"""Core AI provider and subsystem protocols.

Defines the two top-level structural contracts for AI packages:

* ``AIProviderProtocol`` — any package that acts as an AI provider (chat, etc.)
* ``AISubsystemProtocol`` — any AI subsystem package discovered via entry points

For other AI contracts import from the focused sub-modules directly:

* ``quadkit.contracts.ai.llm``     — LLM clients and prompt protocols
* ``quadkit.contracts.ai.vector``  — Vector store and document protocols
* ``quadkit.contracts.ai.rag``     — RAG pipeline protocols
* ``quadkit.contracts.ai.guards``  — GuardProtocol chain protocols
* ``quadkit.contracts.ai.agents``  — Agent strategy and memory protocols
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from quadkit.contracts.core.provider import ProviderProtocol

if TYPE_CHECKING:
    from quadkit.contracts.ai.llm import ChatMessageProtocol, CompletionProtocol


@runtime_checkable
class AIProviderProtocol(ProviderProtocol, Protocol):
    """Protocol for AI provider implementations."""

    async def chat(
        self,
        messages: list[ChatMessageProtocol],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> CompletionProtocol:
        """Chat with optional tool calling.

        Args:
            messages: List of chat messages.
            tools: Optional list of JSON Schema tool definitions.
                Intentionally ``list[dict[str, Any]]`` — tool schemas are
                provider-specific JSON and their shape is not constrained here.
            **kwargs: Provider-specific options.

        Returns:
            Completion with optional tool calls.
        """
        ...


@runtime_checkable
class AISubsystemProtocol(Protocol):
    """Contract for AI subsystem packages discovered via entry points."""

    name: str

    async def initialize(self) -> None:
        """Initialize the subsystem after all providers are booted."""
        ...

    async def health_check(self) -> bool:
        """Return True if the subsystem is healthy."""
        ...


__all__ = [
    "AIProviderProtocol",
    "AISubsystemProtocol",
]
