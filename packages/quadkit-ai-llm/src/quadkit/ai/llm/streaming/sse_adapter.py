"""Server-Sent Events adapter for streaming responses."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.ai.llm.exceptions import sanitize_llm_error
from quadkit.logging import (
    get_logger,
)
from quadkit.serialization.backends.json import dumps_str

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = get_logger(__name__)


class ServerSentEvent:
    """Represents a single SSE event for sending to client."""

    def __init__(
        self,
        data: str,
        event: str = "message",
        id: str | None = None,
    ) -> None:
        """Initialize SSE.

        Args:
            data: Event data (usually JSON string)
            event: Event type name
            id: Optional event ID
        """
        self.data = data
        self.event = event
        self.id = id

    def encode(self) -> str:
        """Encode event as SSE format string.

        Returns:
            Formatted SSE string
        """
        lines = []
        if self.id:
            lines.append(f"id: {self.id}")
        lines.append(f"event: {self.event}")
        lines.append(f"data: {self.data}")
        return "\n".join(lines) + "\n\n"


class SSEStreamAdapter:
    """Convert streaming responses to Server-Sent Events format.

    Adapts internal streaming format to SSE for web clients.
    """

    def __init__(
        self,
        model: str,
        provider: str,
    ) -> None:
        """Initialize SSE adapter.

        Args:
            model: Model being used
            provider: Provider name
        """
        self.model = model
        self.provider = provider
        self._chunk_counter = 0

    async def adapt(
        self,
        stream: AsyncGenerator[Any, None],
    ) -> AsyncGenerator[ServerSentEvent, None]:
        """Adapt streaming response to SSE events.

        Args:
            stream: Raw streaming response

        Yields:
            ServerSentEvent objects
        """
        try:
            async for chunk in stream:
                self._chunk_counter += 1

                # Emit thinking chunk (Anthropic, Gemini, Bedrock, etc.)
                thinking_delta = chunk.thinking_delta
                if thinking_delta:
                    yield ServerSentEvent(
                        data=dumps_str(
                            {
                                "thinking": thinking_delta,
                                "model": self.model,
                                "provider": self.provider,
                                "index": self._chunk_counter,
                            }
                        ),
                        event="thinking",
                        id=str(self._chunk_counter),
                    )
                    logger.debug(
                        "sse_thinking_chunk_sent",
                        chunk_index=self._chunk_counter,
                        chunk_size=len(thinking_delta),
                    )
                    continue

                # Yield answer text chunk
                content = chunk.delta or ""
                if content:
                    event = ServerSentEvent(
                        data=dumps_str(
                            {
                                "content": content,
                                "model": self.model,
                                "provider": self.provider,
                                "index": self._chunk_counter,
                            }
                        ),
                        event="delta",
                        id=str(self._chunk_counter),
                    )
                    yield event

                    logger.debug(
                        "sse_chunk_sent",
                        chunk_index=self._chunk_counter,
                        chunk_size=len(content),
                    )

            # Send completion event
            yield ServerSentEvent(
                data=dumps_str(
                    {
                        "finish_reason": "stop",
                        "model": self.model,
                        "total_chunks": self._chunk_counter,
                    }
                ),
                event="done",
            )

        except Exception as e:  # noqa: BLE001
            safe_error = sanitize_llm_error(e)
            logger.error(
                "sse_stream_error",
                error_type=type(e).__name__,
            )
            yield ServerSentEvent(
                data=dumps_str(
                    {
                        "error": safe_error.message,
                    }
                ),
                event="error",
            )
