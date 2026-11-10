"""Unit tests for streaming module."""

from __future__ import annotations

import pytest

from quadkit.ai.llm.streaming.stream import (
    AnthropicStreamingAdapter,
    GoogleStreamingAdapter,
    OpenAIStreamingAdapter,
    StreamChunk,
    StreamingMetrics,
    StreamingOrchestrator,
    StreamingResponse,
)
from quadkit.contracts.ai.models import ModelRequest

# ── StreamChunk ──────────────────────────────────────────────────────

class TestStreamChunk:
    def test_defaults(self) -> None:
        chunk = StreamChunk(content="hello")
        assert chunk.content == "hello"
        assert chunk.tokens_used == 0
        assert chunk.index == 0
        assert chunk.finish_reason is None
        assert chunk.metadata == {}

    def test_with_metadata(self) -> None:
        chunk = StreamChunk(content="x", tokens_used=5, index=3, finish_reason="stop")
        assert chunk.tokens_used == 5
        assert chunk.index == 3
        assert chunk.finish_reason == "stop"


# ── StreamingMetrics ─────────────────────────────────────────────────

class TestStreamingMetrics:
    def test_defaults(self) -> None:
        m = StreamingMetrics()
        assert m.total_chunks == 0
        assert m.total_tokens == 0
        assert m.time_to_first_chunk_ms is None


# ── StreamingResponse ────────────────────────────────────────────────

class TestStreamingResponse:
    def test_add_chunks_and_aggregate(self) -> None:
        resp = StreamingResponse(provider="openai", model_id="gpt-4")
        resp.add_chunk(StreamChunk(content="Hello ", index=0))
        resp.add_chunk(StreamChunk(content="World", index=1, finish_reason="stop"))
        resp.finish()

        assert resp.get_aggregated_content() == "Hello World"
        assert resp.finished is True
        assert resp.finish_reason == "stop"
        assert len(resp.chunks) == 2

    def test_first_chunk_time_set(self) -> None:
        resp = StreamingResponse(provider="openai", model_id="gpt-4")
        assert resp.first_chunk_time is None
        resp.add_chunk(StreamChunk(content="a"))
        assert resp.first_chunk_time is not None

    def test_get_metrics(self) -> None:
        resp = StreamingResponse(provider="test", model_id="m")
        resp.add_chunk(StreamChunk(content="a", tokens_used=5))
        resp.add_chunk(StreamChunk(content="b", tokens_used=3))
        resp.finish()

        metrics = resp.get_metrics()
        assert metrics.total_chunks == 2
        assert metrics.total_tokens == 8
        assert metrics.time_to_first_chunk_ms is not None
        assert metrics.chunks_per_second > 0

    def test_finish_without_reason(self) -> None:
        resp = StreamingResponse(provider="test", model_id="m")
        resp.finish(reason="length")
        assert resp.finish_reason == "length"

    @pytest.mark.asyncio
    async def test_to_model_response(self) -> None:
        resp = StreamingResponse(provider="openai", model_id="gpt-4")
        resp.add_chunk(StreamChunk(content="hello", tokens_used=2))
        resp.finish()

        model_resp = await resp.to_model_response(input_tokens=10)
        assert model_resp.content == "hello"
        assert model_resp.tokens_used == 2
        assert model_resp.extra_metadata["provider"] == "openai"
        assert model_resp.extra_metadata["input_tokens"] == 10


# ── Streaming Adapters ───────────────────────────────────────────────

class TestStreamingAdapters:
    @pytest.mark.asyncio
    async def test_openai_adapter_streams_chunks(self) -> None:
        adapter = OpenAIStreamingAdapter(provider="openai")
        request = ModelRequest(prompt="Hello")
        chunks = []
        async for chunk in adapter.stream(request, "gpt-4"):
            chunks.append(chunk)
        assert len(chunks) == 3
        assert chunks[-1].finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_anthropic_adapter_streams_chunks(self) -> None:
        adapter = AnthropicStreamingAdapter(provider="anthropic")
        request = ModelRequest(prompt="Hello")
        chunks = []
        async for chunk in adapter.stream(request, "claude-3"):
            chunks.append(chunk)
        assert len(chunks) == 3
        assert chunks[-1].finish_reason == "end_turn"

    @pytest.mark.asyncio
    async def test_google_adapter_streams_chunks(self) -> None:
        adapter = GoogleStreamingAdapter(provider="google")
        request = ModelRequest(prompt="Hello")
        chunks = []
        async for chunk in adapter.stream(request, "gemini"):
            chunks.append(chunk)
        assert len(chunks) == 3

    @pytest.mark.asyncio
    async def test_stream_to_response(self) -> None:
        adapter = OpenAIStreamingAdapter(provider="openai")
        request = ModelRequest(prompt="Test")
        response = await adapter.stream_to_response(request, "gpt-4")
        assert response.finished is True
        assert response.get_aggregated_content() == "Hello from OpenAI"


# ── StreamingOrchestrator ────────────────────────────────────────────

class TestStreamingOrchestrator:
    @pytest.mark.asyncio
    async def test_register_and_stream(self) -> None:
        orch = StreamingOrchestrator()
        adapter = OpenAIStreamingAdapter(provider="openai")
        await orch.register_adapter("openai", adapter)

        request = ModelRequest(prompt="Test")
        resp = await orch.stream(request, "openai", "gpt-4")
        assert resp.finished is True
        assert "Hello" in resp.get_aggregated_content()

    @pytest.mark.asyncio
    async def test_stream_unregistered_provider_raises(self) -> None:
        orch = StreamingOrchestrator()
        request = ModelRequest(prompt="Test")
        with pytest.raises(ValueError, match="No streaming adapter"):
            await orch.stream(request, "unknown", "model-x")

    @pytest.mark.asyncio
    async def test_stream_with_fallback(self) -> None:
        orch = StreamingOrchestrator()
        await orch.register_adapter(
            "anthropic", AnthropicStreamingAdapter(provider="anthropic"),
        )

        request = ModelRequest(prompt="Test")
        resp = await orch.stream_with_fallback(
            request,
            providers=["missing", "anthropic"],
            model_ids={"anthropic": "claude-3"},
        )
        assert resp.finished is True

    @pytest.mark.asyncio
    async def test_stream_with_fallback_all_fail(self) -> None:
        orch = StreamingOrchestrator()
        request = ModelRequest(prompt="Test")
        with pytest.raises(ValueError, match="Streaming failed"):
            await orch.stream_with_fallback(
                request,
                providers=["none"],
                model_ids={},
            )

    @pytest.mark.asyncio
    async def test_stream_with_fallback_does_not_expose_provider_error(
        self, capsys
    ) -> None:
        secret = "STREAM_FALLBACK_SECRET_SENTINEL"

        class FailingAdapter:
            async def stream_to_response(
                self, request: ModelRequest, model_id: str
            ) -> StreamingResponse:
                raise RuntimeError(secret)

        orch = StreamingOrchestrator()
        await orch.register_adapter("provider", FailingAdapter())  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="Streaming failed for all providers") as error:
            await orch.stream_with_fallback(
                ModelRequest(prompt="Test"),
                providers=["provider"],
                model_ids={"provider": "test-model"},
            )

        assert secret not in str(error.value)
        assert error.value.__cause__ is None
        captured = capsys.readouterr()
        assert secret not in captured.out + captured.err

    @pytest.mark.asyncio
    async def test_stream_with_chunking(self) -> None:
        orch = StreamingOrchestrator()
        await orch.register_adapter(
            "openai", OpenAIStreamingAdapter(provider="openai"),
        )

        received: list[StreamChunk] = []

        async def on_chunk(chunk: StreamChunk) -> None:
            received.append(chunk)

        request = ModelRequest(prompt="Test")
        resp = await orch.stream_with_chunking(
            request, "openai", "gpt-4", chunk_callback=on_chunk,
        )
        assert resp.finished is True
        assert len(received) == 3

    @pytest.mark.asyncio
    async def test_stream_with_chunking_unregistered(self) -> None:
        orch = StreamingOrchestrator()
        request = ModelRequest(prompt="Test")
        with pytest.raises(ValueError, match="No streaming adapter"):
            await orch.stream_with_chunking(request, "none", "m")
