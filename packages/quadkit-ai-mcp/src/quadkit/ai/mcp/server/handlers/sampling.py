"""MCP sampling handler — server-side LLM inference capability.

When an MCP client sends a ``sampling/createMessage`` request, the server
uses its configured ``LLMClientProtocol`` to generate a completion and returns
it in the MCP sampling response format.

This implements the MCP Sampling specification:
https://spec.modelcontextprotocol.io/specification/client/sampling/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from quadkit.contracts.mcp.exceptions import MCPError, MCPToolCallError
from quadkit.logging import (
    get_logger,
)
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.ai.llm import LLMClientProtocol

logger = get_logger(__name__)


@dataclass
class SamplingRequest:
    """MCP sampling/createMessage request payload.

    Maps directly to the MCP sampling request schema.
    """

    messages: list[dict[str, Any]]
    """Conversation messages in MCP content format."""

    model_preferences: dict[str, Any] = field(default_factory=dict)
    """Client model hints (hints, cost_priority, speed_priority, intelligence_priority)."""

    system_prompt: str | None = None
    """Optional system prompt to prepend."""

    max_tokens: int = 1024
    """Maximum tokens for the completion."""

    temperature: float | None = None
    """Sampling temperature (0.0-2.0). None uses the model default."""

    stop_sequences: list[str] = field(default_factory=list)
    """Optional stop sequences."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Pass-through metadata (ignored by the server, forwarded as-is)."""


@dataclass
class SamplingResponse:
    """MCP sampling/createMessage response payload."""

    role: str
    """Always 'assistant' for server-generated completions."""

    content: dict[str, Any]
    """MCP content item — typically ``{"type": "text", "text": "..."}``."""

    model: str
    """The model identifier used to generate the response."""

    stop_reason: str | None = None
    """Why generation stopped: 'end_turn', 'max_tokens', 'stop_sequence', etc."""

    def to_dict(self) -> dict[str, Any]:
        """Serialise to MCP sampling response format."""
        data: dict[str, Any] = {
            "role": self.role,
            "content": self.content,
            "model": self.model,
        }
        if self.stop_reason is not None:
            data["stopReason"] = self.stop_reason
        return data


class SamplingHandler:
    """MCP sampling capability — server-side LLM inference.

    When an MCP client sends a ``sampling/createMessage`` request, this
    handler converts it to an ``LLMClientProtocol.complete()`` call and
    returns the result.

    The handler is optional — registered only when an LLM client is
    available in the container (see ``MCPProvider._boot_handlers``).

    Example::

        handler = SamplingHandler(llm=openai_client)
        result = await handler.handle(request)
        if result.is_ok():
            response = result.unwrap()
    """

    def __init__(self, llm: LLMClientProtocol) -> None:
        """Initialize the sampling handler.

        Args:
            llm: LLM client used to generate completions.
        """
        self._llm = llm

    async def create_message(
        self,
        messages: list[dict[str, Any]] | None = None,
        maxTokens: int = 1024,
        modelPreferences: dict[str, Any] | None = None,
        systemPrompt: str | None = None,
        temperature: float | None = None,
        stopSequences: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **_kwargs: Any,
    ) -> Result[dict[str, Any], MCPError]:
        """Handle the ``sampling/createMessage`` MCP method.

        Accepts MCP-spec camelCase kwargs directly so the MCPServer dispatcher
        can call ``handler(**params)`` without transformation.

        Args:
            messages: MCP conversation messages.
            maxTokens: Maximum tokens to generate.
            modelPreferences: Client model hints (ignored, best-effort).
            systemPrompt: Optional system prompt to prepend.
            temperature: Sampling temperature.
            stopSequences: Stop sequences.
            metadata: Pass-through metadata.
            **_kwargs: Ignored extra params for forward-compatibility.

        Returns:
            ``Result`` containing the MCP sampling response payload.
        """
        request = SamplingRequest(
            messages=messages or [],
            model_preferences=modelPreferences or {},
            system_prompt=systemPrompt,
            max_tokens=maxTokens,
            temperature=temperature,
            stop_sequences=stopSequences or [],
            metadata=metadata or {},
        )
        result = await self._handle(request)
        if result.is_ok():
            return Ok(result.unwrap().to_dict())
        return Err(result.unwrap_err())

    async def _handle(
        self, request: SamplingRequest
    ) -> Result[SamplingResponse, MCPError]:
        """Convert MCP sampling request to LLM call and return a response.

        Args:
            request: Parsed sampling request.

        Returns:
            ``Ok(SamplingResponse)`` or ``Err(MCPError)``.
        """
        from quadkit.contracts.ai.llm import ChatMessage

        chat_messages: list[Any] = []

        # Convert MCP message format to LLM chat messages
        for msg in request.messages:
            role = msg.get("role", "user")
            content = msg.get("content", {})
            if isinstance(content, dict):
                text = content.get("text", "")
            else:
                text = str(content)
            chat_messages.append(ChatMessage(role=role, content=text))

        kwargs: dict[str, Any] = {}
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature

        completion_result = await self._llm.complete(
            chat_messages,
            max_tokens=request.max_tokens,
            **kwargs,
        )

        if completion_result.is_err():
            llm_error = completion_result.unwrap_err()
            return Err(
                MCPToolCallError(
                    message=f"LLM sampling failed: {llm_error}",
                )
            )

        completion = completion_result.unwrap()
        text = getattr(completion, "text", "") or ""
        model = getattr(completion, "model", "unknown") or "unknown"
        stop_reason = getattr(completion, "finish_reason", None)

        return Ok(
            SamplingResponse(
                role="assistant",
                content={"type": "text", "text": text},
                model=model,
                stop_reason=stop_reason,
            )
        )


__all__ = ["SamplingHandler", "SamplingRequest", "SamplingResponse"]
