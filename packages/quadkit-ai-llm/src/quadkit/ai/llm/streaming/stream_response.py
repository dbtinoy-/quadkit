"""Streaming response aggregation and metrics.

Tracks incoming chunks for a streaming response, aggregates content,
and computes timing/token metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from quadkit.ai.llm.types import StreamChunk
from quadkit.contracts.ai.models import ModelResponse
from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)

__all__ = [
    "StreamingMetrics",
    "StreamingResponse",
]


@dataclass(frozen=True)
class StreamingMetrics:
    """Metrics for a streaming response.

    Attributes:
        total_chunks: Number of chunks received
        total_tokens: Total tokens in response
        total_input_tokens: Input tokens from request
        total_latency_ms: Total time from request to completion
        time_to_first_chunk_ms: Time until first chunk received
        chunks_per_second: Average chunks received per second
    """

    total_chunks: int = 0
    total_tokens: int = 0
    total_input_tokens: int = 0
    total_latency_ms: float = 0.0
    time_to_first_chunk_ms: float | None = None
    chunks_per_second: float = 0.0


class StreamingResponse:
    """Manages streaming response state and aggregation.

    Tracks incoming chunks, aggregates content, and maintains metrics
    about the streaming response.
    """

    def __init__(
        self,
        provider: str,
        model_id: str,
    ) -> None:
        """Initialize streaming response tracker.

        Args:
            provider: Provider name
            model_id: Model ID being used
        """
        self.provider = provider
        self.model_id = model_id
        self.chunks: list[StreamChunk] = []
        self.start_time = datetime.now(UTC)
        self.first_chunk_time: datetime | None = None
        self.finished = False
        self.finish_reason: str | None = None

    def add_chunk(self, chunk: StreamChunk) -> None:
        """Add a chunk to the response.

        Args:
            chunk: Chunk to add
        """
        if self.first_chunk_time is None:
            self.first_chunk_time = datetime.now(UTC)

        self.chunks.append(chunk)
        logger.debug(
            "stream_chunk_received",
            chunk_index=chunk.index,
            chunk_content_len=len(
                (chunk.content if chunk.content is not None else chunk.delta) or ""
            ),
        )

    def finish(self, reason: str | None = None) -> None:
        """Mark streaming as finished.

        Args:
            reason: Why the stream ended
        """
        self.finished = True
        self.finish_reason = reason
        if self.chunks:
            self.finish_reason = self.chunks[-1].finish_reason or reason

    def get_aggregated_content(self) -> str:
        """Get concatenated answer content of all non-thinking chunks.

        Returns:
            Full response text (thinking chunks excluded)
        """
        return "".join(
            ((chunk.content if chunk.content is not None else chunk.delta) or "")
            for chunk in self.chunks
            if not chunk.is_thinking
        )

    def get_aggregated_thinking(self) -> str:
        """Get concatenated thinking content from all thinking chunks.

        Returns:
            Full thinking text, empty string when thinking was not enabled.
        """
        return "".join(
            chunk.thinking_delta or "" for chunk in self.chunks if chunk.is_thinking
        )

    def get_metrics(self) -> StreamingMetrics:
        """Calculate streaming metrics.

        Returns:
            StreamingMetrics with aggregate values
        """
        now = datetime.now(UTC)
        total_latency = (now - self.start_time).total_seconds() * 1000

        time_to_first = None
        if self.first_chunk_time:
            time_to_first = (
                self.first_chunk_time - self.start_time
            ).total_seconds() * 1000

        total_tokens = sum(chunk.tokens_used for chunk in self.chunks)
        if total_tokens == 0 and self.chunks:
            total_tokens = len(self.chunks)
        chunks_per_sec = len(self.chunks) / max(total_latency / 1000, 0.001)

        return StreamingMetrics(
            total_chunks=len(self.chunks),
            total_tokens=total_tokens,
            total_latency_ms=total_latency,
            time_to_first_chunk_ms=time_to_first,
            chunks_per_second=chunks_per_sec,
        )

    async def to_model_response(
        self,
        input_tokens: int = 0,
    ) -> ModelResponse:
        """Convert streaming response to standard ModelResponse.

        Args:
            input_tokens: Number of input tokens from request

        Returns:
            ModelResponse with aggregated content
        """
        return ModelResponse(
            content=self.get_aggregated_content(),
            tokens_used=(
                sum(chunk.tokens_used for chunk in self.chunks) or len(self.chunks)
            ),
            stop_reason=self.finish_reason,
            extra_metadata={
                "provider": self.provider,
                "model_id": self.model_id,
                "chunks": len(self.chunks),
                "time_to_first_chunk_ms": (
                    self.get_metrics().time_to_first_chunk_ms or 0.0
                ),
                "input_tokens": input_tokens,
            },
        )
