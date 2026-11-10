"""Mock LLM client for testing.

Provides deterministic responses without making real API calls.
"""

from collections.abc import AsyncGenerator
from typing import Any

from quadkit.ai.llm.exceptions import LLMError, LLMRateLimitError
from quadkit.ai.llm.types import (
    ChatMessage,
    Completion,
    Role,
    StreamChunk,
    TokenUsage,
)
from quadkit.result import Err, Ok, Result


class MockLLMClient:
    """Mock LLM client for testing.

    Provides deterministic responses without making real API calls.
    Useful for unit tests, integration tests, and development.

    Example:
        >>> mock_llm = MockLLMClient(responses=[
        ...     "The answer is 42.",
        ...     "Python is a programming language."
        ... ])
        >>> completion = await mock_llm.complete([
        ...     ChatMessage(role=Role.USER, content="What is the answer?")
        ... ])
        >>> completion.content
        'The answer is 42.'
    """

    def __init__(
        self,
        responses: list[str] | None = None,
        response_delay: float = 0.0,
        simulate_errors: bool = False,
        model: str = "mock-model",
    ):
        """Initialize mock LLM client.

        Args:
            responses: List of canned responses to return in order
            response_delay: Simulated delay in seconds (for testing async behavior)
            simulate_errors: Whether to simulate random errors
            model: Model name for testing (default: "mock-model")
        """
        self.model = model
        self.responses = responses or ["This is a mock response."]
        self._response_index = 0
        self.response_delay = response_delay
        self.simulate_errors = simulate_errors
        self._call_count = 0
        self._call_history: list[list[ChatMessage | dict[str, str]]] = []
        self._closed = False

    def _get_next_response(self) -> str:
        """Get next response from the queue.

        Returns:
            Next response string

        Raises:
            StopIteration: If no more responses available
        """
        if self._response_index >= len(self.responses):
            # Cycle back to start
            self._response_index = 0

        response = self.responses[self._response_index]
        self._response_index += 1
        return response

    async def complete(
        self,
        messages: list[ChatMessage | dict[str, str]],
        **kwargs,
    ) -> Result[Completion, LLMError]:
        """Complete a chat conversation.

        Args:
            messages: List of messages
            **kwargs: Additional parameters (ignored in mock)

        Returns:
            ``Ok(Completion)`` mock completion.
        """
        if self.response_delay > 0:
            import asyncio

            await asyncio.sleep(self.response_delay)

        self._call_count += 1
        self._call_history.append(messages)

        response_content = self._get_next_response()

        # Calculate mock token usage
        total_input_tokens = 0
        for msg in messages:
            content = msg.get("content", "") if isinstance(msg, dict) else msg.content
            total_input_tokens += len(str(content).split())

        output_tokens = len(response_content.split())

        return Ok(
            Completion(
                content=response_content,
                role=Role.ASSISTANT,
                usage=TokenUsage(
                    prompt_tokens=total_input_tokens,
                    completion_tokens=output_tokens,
                    total_tokens=total_input_tokens + output_tokens,
                ),
                model=self.model,
            )
        )

    def stream_chat(
        self,
        messages: list[ChatMessage | dict[str, str]],
        **kwargs,
    ) -> Any:
        """Start streaming chat completion (protocol-aligned method).

        Args:
            messages: List of messages
            **kwargs: Additional parameters (ignored in mock)

        Returns:
            ``AsyncStream[StreamChunk, LLMError]`` streaming words.
        """
        from quadkit.contracts.infra import AsyncStream
        
        return AsyncStream(
            self._stream_impl(messages, **kwargs),
            error_adapter=lambda e: LLMError(str(e))
        )

    async def _stream_impl(
        self,
        messages: list[ChatMessage | dict[str, str]],
        **kwargs,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Internal async generator that yields stream chunks word by word."""
        if self.response_delay > 0:
            import asyncio

            await asyncio.sleep(self.response_delay)

        self._call_count += 1
        self._call_history.append(messages)

        response_content = self._get_next_response()

        # Yield words one by one to simulate streaming
        words = response_content.split()
        for i, word in enumerate(words):
            # Add space after each word except the last
            content = word if i == len(words) - 1 else f"{word} "

            yield StreamChunk(
                delta=content,
                role=Role.ASSISTANT,
                finish_reason="stop" if i == len(words) - 1 else None,
            )

            # Small delay between chunks for realism
            if self.response_delay > 0:
                import asyncio

                await asyncio.sleep(self.response_delay / len(words))

    async def chat(
        self,
        messages: list[ChatMessage | dict[str, str]],
        tools: list[Any] | None = None,
        **kwargs,
    ) -> Result[Completion, LLMError]:
        """Chat with optional tool calling.

        Args:
            messages: List of messages
            tools: Optional tools (not used in mock)
            **kwargs: Additional parameters

        Returns:
            ``Ok(Completion)`` on success.  ``Err(LLMError)`` on failure.
        """
        return await self.complete(messages, **kwargs)

    def get_call_count(self) -> int:
        """Get number of times the mock was called.

        Returns:
            Call count
        """
        return self._call_count

    def get_call_history(self) -> list[list[ChatMessage | dict[str, str]]]:
        """Get history of all calls.

        Returns:
            List of message lists from each call
        """
        return self._call_history

    def reset(self) -> None:
        """Reset mock state."""
        self._response_index = 0
        self._call_count = 0
        self._call_history.clear()

    async def close(self) -> None:
        """Close mock client."""
        self._closed = True

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"MockLLMClient(responses={len(self.responses)}, calls={self._call_count})"
        )


class MockLLMClientWithErrors(MockLLMClient):
    """Mock LLM client that can simulate errors.

    Useful for testing error handling in your application.

    Example:
        >>> mock_llm = MockLLMClientWithErrors(
        ...     responses=["Success"],
        ...     error_on_call=1  # Fail on first call
        ... )
        >>> # First call will raise an error
        >>> # Second call will succeed
    """

    def __init__(
        self,
        responses: list[str] | None = None,
        error_on_call: int | None = None,
        error_rate: float | None = None,
        error_message: str = "Mock API error",
    ):
        """Initialize error-simulating mock.

        Args:
            responses: List of canned responses
            error_on_call: Which call number should error (1-indexed)
            error_rate: Probabilistic error rate (0-1)
            error_message: Error message to raise
        """
        super().__init__(responses)
        self.error_on_call = error_on_call
        self.error_rate = error_rate
        self.error_message = error_message

    async def complete(
        self,
        messages: list[ChatMessage | dict[str, str]],
        **kwargs,
    ) -> Result[Completion, LLMError]:
        """Complete with possible error simulation.

        Args:
            messages: List of messages
            **kwargs: Additional parameters

        Returns:
            ``Ok(Completion)`` on success, ``Err(LLMRateLimitError)`` on the
            configured error call.
        """
        if self.error_on_call is not None:
            if self._call_count + 1 == self.error_on_call:
                self._call_count += 1
                return Err(LLMRateLimitError(self.error_message))

        return await super().complete(messages, **kwargs)


class MockStreamingLLMClient(MockLLMClient):
    """Mock LLM client with enhanced streaming simulation.

    Simulates more realistic streaming behavior with character-by-character
    or token-by-token streaming.

    Example:
        >>> mock_llm = MockStreamingLLMClient(
        ...     responses=["Hello world"],
        ...     stream_by="token",
        ...     chunk_delay=0.01
        ... )
        >>> async for chunk in mock_llm.stream_chat(messages):
        ...     print(chunk.content, end="")
        Hello world
    """

    def __init__(
        self,
        responses: list[str] | None = None,
        stream_chunks: list[str] | None = None,
        model: str | None = None,
        stream_by: str = "word",  # "word", "char", or "token"
        chunk_delay: float = 0.01,
    ):
        """Initialize streaming mock.

        Args:
            responses: List of canned responses
            stream_chunks: Optional explicit stream chunks
            model: Optional model name
            stream_by: How to chunk the stream ("word", "char", "token")
            chunk_delay: Delay between chunks in seconds
        """
        # If explicit stream chunks are provided, use them as the response list
        if stream_chunks is not None:
            super().__init__(stream_chunks)
        else:
            super().__init__(responses)
        # Set model if provided
        if model is not None:
            self.model = model
        self.stream_by = stream_by
        self.chunk_delay = chunk_delay

    def stream_chat(
        self,
        messages: list[ChatMessage | dict[str, str]],
        **kwargs,
    ) -> Any:
        """Start streaming with configurable chunking (protocol-aligned method).

        Args:
            messages: List of messages
            **kwargs: Additional parameters

        Returns:
            ``AsyncStream[StreamChunk, LLMError]`` streaming chunks.
        """
        from quadkit.contracts.infra import AsyncStream
        
        return AsyncStream(
            self._stream_impl(messages, **kwargs),
            error_adapter=lambda e: LLMError(str(e))
        )

    async def _stream_impl(  # type: ignore[override]
        self,
        messages: list[ChatMessage | dict[str, str]],
        **kwargs,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Internal async generator with configurable chunking strategy."""
        import asyncio

        self._call_count += 1
        self._call_history.append(messages)

        response_content = self._get_next_response()

        if self.stream_by == "word":
            chunks = response_content.split()
            for i, chunk in enumerate(chunks):
                yield StreamChunk(
                    delta=chunk if i == len(chunks) - 1 else f"{chunk} ",
                    role=Role.ASSISTANT,
                    finish_reason="stop" if i == len(chunks) - 1 else None,
                )
                if self.chunk_delay > 0:
                    await asyncio.sleep(self.chunk_delay)

        elif self.stream_by == "char":
            for i, char in enumerate(response_content):
                yield StreamChunk(
                    delta=char,
                    role=Role.ASSISTANT,
                    finish_reason="stop" if i == len(response_content) - 1 else None,
                )
                if self.chunk_delay > 0:
                    await asyncio.sleep(self.chunk_delay)

        else:  # token
            # Simple tokenization (split on spaces and punctuation)
            import re

            tokens = re.findall(r"\w+|[^\w\s]", response_content)
            for i, token in enumerate(tokens):
                yield StreamChunk(
                    delta=token,
                    role=Role.ASSISTANT,
                    finish_reason="stop" if i == len(tokens) - 1 else None,
                )
                if self.chunk_delay > 0:
                    await asyncio.sleep(self.chunk_delay)
