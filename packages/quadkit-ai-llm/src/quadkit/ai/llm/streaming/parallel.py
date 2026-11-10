"""Parallel stream aggregator — race multiple LLM providers, yield from the fastest.

``ParallelStreamAggregator`` launches streaming requests against every provided
LLM client simultaneously and yields chunks from whichever provider delivers the
first token.  Once a winner is chosen all other requests are cancelled.

This is useful for latency-sensitive applications where the user does not care
*which* model answers, only that the answer arrives as fast as possible.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from quadkit.ai.llm.types import StreamChunk
from quadkit.logging import (
    get_logger,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from quadkit.contracts.ai.llm import ChatMessageProtocol, LLMClientProtocol
    from quadkit.contracts.infra import AsyncStream

logger = get_logger(__name__)


class ParallelStreamAggregator:
    """Race multiple LLM providers and yield chunks from the first to respond.

    All providers are started concurrently; the first provider to yield a
    non-empty chunk is declared the winner.  All other provider tasks are
    cancelled immediately so that API quota and cost are kept minimal.

    Args:
        timeout: Seconds to wait for *any* provider to start streaming before
            raising ``TimeoutError``.  Defaults to 30 seconds.

    Example::

        agg = ParallelStreamAggregator(timeout=15)
        async for chunk in agg.stream([openai_client, anthropic_client], messages):
            print(chunk.delta or "", end="", flush=True)
    """

    def __init__(self, *, timeout: float = 30.0) -> None:
        """Initialize the aggregator.

        Args:
            timeout: Seconds to wait for the first provider to start yielding.
        """
        self._timeout = timeout

    async def stream(
        self,
        providers: list[LLMClientProtocol],
        messages: list[ChatMessageProtocol],
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """Stream from whichever provider responds first.

        Args:
            providers: Ordered list of LLM clients to race.
            messages: Chat messages to send to each provider.
            **kwargs: Forwarded to each provider's ``stream_chat`` call
                (e.g. ``model``, ``temperature``, ``max_tokens``).

        Returns:
            Async iterator of :class:`~quadkit.ai.llm.streaming.stream.StreamChunk`.

        Raises:
            TimeoutError: If no provider starts yielding within ``self._timeout``.
            ValueError: If ``providers`` is empty.
        """
        if not providers:
            raise ValueError("At least one provider is required")
        return self._race(providers, messages, kwargs)

    async def _race(
        self,
        providers: list[LLMClientProtocol],
        messages: list[ChatMessageProtocol],
        kwargs: dict[str, Any],
    ) -> AsyncIterator[StreamChunk]:
        """Internal generator that races providers and yields the winner's chunks."""
        # First-chunk queue: (provider_index, first_chunk, stream_iterator)
        first_chunk_queue: asyncio.Queue[
            tuple[int, StreamChunk, AsyncStream[Any, Any]]
        ] = asyncio.Queue()

        tasks: list[asyncio.Task[None]] = []

        async def _probe(idx: int, client: LLMClientProtocol) -> None:
            """Start streaming and put the first chunk into the queue."""
            try:
                # stream_chat() is no longer async and returns AsyncStream directly
                stream_iter = client.stream_chat(messages, **kwargs)

                async for raw_evt in stream_iter:
                    content = raw_evt.delta or ""
                    thinking_delta = raw_evt.thinking_delta or ""
                    is_thinking = raw_evt.is_thinking
                    if content or thinking_delta:
                        chunk = StreamChunk(
                            delta=content or None,
                            model=raw_evt.model,
                            index=0,
                            finish_reason=None,
                            thinking_delta=thinking_delta or None,
                            is_thinking=is_thinking,
                        )
                        await first_chunk_queue.put((idx, chunk, stream_iter))
                        return
            except Exception:  # noqa: BLE001 — probe failures must not break the parallel stream
                return

        for i, provider in enumerate(providers):
            task = asyncio.create_task(_probe(i, provider))
            tasks.append(task)

        try:
            winner_idx, first_chunk, winner_iter = await asyncio.wait_for(
                first_chunk_queue.get(),
                timeout=self._timeout,
            )
        except TimeoutError:
            for t in tasks:
                t.cancel()
            raise

        # Cancel all non-winner probes
        for i, task in enumerate(tasks):
            if i != winner_idx and not task.done():
                task.cancel()

        logger.info(
            "parallel_stream_winner_selected",
            provider_index=winner_idx,
            total_providers=len(providers),
        )

        # Yield the first chunk we already captured
        yield first_chunk

        # Continue yielding from the winner's iterator
        chunk_index = 1
        async for raw_evt in winner_iter:
            content = raw_evt.delta or ""
            thinking_delta = raw_evt.thinking_delta or ""
            is_thinking = raw_evt.is_thinking
            finish = raw_evt.finish_reason
            yield StreamChunk(
                delta=content or None,
                model=raw_evt.model,
                index=chunk_index,
                finish_reason=finish,
                thinking_delta=thinking_delta or None,
                is_thinking=is_thinking,
            )
            chunk_index += 1
            if finish is not None:
                break


__all__ = ["ParallelStreamAggregator"]
