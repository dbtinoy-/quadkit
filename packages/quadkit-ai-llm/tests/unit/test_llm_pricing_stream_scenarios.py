"""Scenario tests for LLM pricing sources, token counters, and streaming.

Covers the previously untested provider-facing paths:

* ``JSONFilePricingSource`` / ``APIPricingSource`` / ``OpenRouterPricingSource``
  / ``StaticPricingSource`` — file and HTTP pricing with error degradation
  (a pricing outage must never propagate), caching, and aliasing rules.
  The HTTP layer is faked by patching the ``ResilientHTTPClient`` symbol in
  the ``sources`` module with a deterministic async context manager.
* Token counters — ``CharEstimateCounter``, the no-dependency fallback paths
  of ``HuggingFaceCounter`` / ``MistralCounter``, and the import guard of
  ``TiktokenCounter``.
* ``SSEStreamAdapter`` / ``ServerSentEvent`` — SSE framing of streamed
  chunks including thinking chunks and mid-stream failures.
* ``ParallelStreamAggregator`` — provider racing, timeout, and probe-failure
  recovery with fully synthetic providers.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, Self
from unittest.mock import patch

import pytest
from structlog.testing import capture_logs

from quadkit.ai.llm.pricing import sources as pricing_sources
from quadkit.ai.llm.pricing.pricing_source_static import StaticPricingSource
from quadkit.ai.llm.pricing.sources import (
    APIPricingSource,
    JSONFilePricingSource,
    OpenRouterPricingSource,
)
from quadkit.ai.llm.pricing.tokens import (
    CharEstimateCounter,
    HuggingFaceCounter,
    MistralCounter,
    TiktokenCounter,
)
from quadkit.ai.llm.pricing.types import ModelPricing
from quadkit.ai.llm.streaming.parallel import ParallelStreamAggregator
from quadkit.ai.llm.streaming.sse_adapter import (
    ServerSentEvent,
    SSEStreamAdapter,
)
from quadkit.ai.llm.types import StreamChunk
from quadkit.contracts.web.http_models import HttpResponse
from quadkit.serialization import dumps_str, loads

# ── Fake HTTP for pricing sources ───────────────────────────────────────


class _FakePricingHTTP:
    """Async-context-manager stand-in for ``ResilientHTTPClient``."""

    def __init__(self, json_data: Any = None, error: Exception | None = None) -> None:
        self.json_data = json_data
        self.error = error
        self.get_count = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def get(self, url: str, **kwargs: Any) -> HttpResponse:
        self.get_count += 1
        if self.error is not None:
            raise self.error
        return HttpResponse(status=200, json=self.json_data)


# ── JSON file source ────────────────────────────────────────────────────


class TestJSONFilePricingSource:
    def _pricing_file(self, tmp_path: Any, payload: Any = None) -> Any:
        if payload is None:
            payload = {
                "models": {
                    "GPT-4": {
                        "prompt_per_1m": 5.0,
                        "completion_per_1m": 15.0,
                        "provider": "openai",
                    },
                    "Local-Model": {"prompt_per_1m": 0.0, "completion_per_1m": 0.0},
                }
            }
        path = tmp_path / "pricing.json"
        path.write_text(dumps_str(payload))
        return path

    @pytest.mark.asyncio
    async def test_loads_models_case_insensitively(self, tmp_path: Any) -> None:
        source = JSONFilePricingSource(self._pricing_file(tmp_path))
        pricing = await source.get_pricing("gpt-4")
        assert pricing is not None
        assert pricing.prompt_per_1m == 5.0
        assert pricing.completion_per_1m == 15.0
        assert pricing.provider == "openai"
        assert pricing.source == "json"

        all_pricing = await source.get_all_pricing()
        assert set(all_pricing) == {"gpt-4", "local-model"}
        assert source.source_name == "JSON File"

    @pytest.mark.asyncio
    async def test_applies_defaults_for_missing_fields(self, tmp_path: Any) -> None:
        source = JSONFilePricingSource(
            self._pricing_file(tmp_path, {"models": {"m": {}}})
        )
        pricing = await source.get_pricing("m")
        assert pricing is not None
        assert pricing.prompt_per_1m == 1.0
        assert pricing.completion_per_1m == 2.0
        assert pricing.provider == "unknown"

    @pytest.mark.asyncio
    async def test_missing_file_degrades_without_logging_private_path(
        self, tmp_path: Any
    ) -> None:
        private_path = tmp_path / "tenant-secret" / "private-pricing.json"
        source = JSONFilePricingSource(private_path)

        with capture_logs() as logs:
            assert await source.get_all_pricing() == {}

        assert await source.get_pricing("gpt-4") is None
        assert str(private_path) not in repr(logs)
        assert logs[0]["event"] == "json_pricing_file_not_found"

    @pytest.mark.asyncio
    async def test_invalid_json_degrades_to_empty(self, tmp_path: Any) -> None:
        path = tmp_path / "broken.json"
        path.write_text("{not-valid-json")
        source = JSONFilePricingSource(path)
        assert await source.get_all_pricing() == {}

    @pytest.mark.asyncio
    async def test_cache_is_reused_until_invalidated(self, tmp_path: Any) -> None:
        path = self._pricing_file(tmp_path)
        source = JSONFilePricingSource(path)
        assert await source.get_pricing("gpt-4") is not None
        # Mutate the file — the cache must keep serving stale data.
        path.write_text(dumps_str({"models": {"changed": {}}}))
        assert "gpt-4" in await source.get_all_pricing()

        source.invalidate_cache()
        reloaded = await source.get_all_pricing()
        assert set(reloaded) == {"changed"}


# ── API (LiteLLM-style) source ──────────────────────────────────────────


class TestAPIPricingSource:
    def _install_fake_http(
        self, monkeypatch: pytest.MonkeyPatch, fake: _FakePricingHTTP
    ) -> None:
        monkeypatch.setattr(
            pricing_sources, "ResilientHTTPClient", lambda **_: fake
        )

    @pytest.mark.asyncio
    async def test_converts_per_token_costs_to_per_1m(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake = _FakePricingHTTP(
            json_data={
                "gpt-4": {"input_cost_per_token": 0.000003, "output_cost_per_token": 0.000006},
                "zero-cost": {"input_cost_per_token": 0, "output_cost_per_token": 0},
            }
        )
        self._install_fake_http(monkeypatch, fake)
        source = APIPricingSource("https://pricing.example.com/models.json")
        pricing = await source.get_pricing("GPT-4")

        assert pricing is not None
        assert pricing.prompt_per_1m == pytest.approx(3.0)
        assert pricing.completion_per_1m == pytest.approx(6.0)
        assert pricing.provider == "openai"
        assert pricing.source == "api"
        # Zero-cost entries are not indexed.
        all_pricing = await source.get_all_pricing()
        assert set(all_pricing) == {"gpt-4"}
        assert source.source_name == "API source"

    @pytest.mark.asyncio
    async def test_provider_inference_matrix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = _FakePricingHTTP(
            json_data={
                "claude-3-opus": {"input_cost_per_token": 0.01},
                "gemini-1.5-pro": {"input_cost_per_token": 0.01},
                "mixtral-8x7b": {"input_cost_per_token": 0.01},
                "command-r": {"input_cost_per_token": 0.01},
                "llama-3-70b": {"input_cost_per_token": 0.01},
                "groq/llama-3": {"input_cost_per_token": 0.01},
                "mystery-model": {"input_cost_per_token": 0.01},
            }
        )
        self._install_fake_http(monkeypatch, fake)
        source = APIPricingSource("https://pricing.example.com/models.json")
        all_pricing = await source.get_all_pricing()

        assert all_pricing["claude-3-opus"].provider == "anthropic"
        assert all_pricing["gemini-1.5-pro"].provider == "google"
        assert all_pricing["mixtral-8x7b"].provider == "mistral"
        assert all_pricing["command-r"].provider == "cohere"
        assert all_pricing["llama-3-70b"].provider == "meta"
        # "groq/llama" must not be attributed to meta.
        assert all_pricing["groq/llama-3"].provider == "unknown"
        assert all_pricing["mystery-model"].provider == "unknown"

    @pytest.mark.asyncio
    async def test_fetch_error_degrades_to_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = _FakePricingHTTP(error=OSError("connection refused"))
        self._install_fake_http(monkeypatch, fake)
        source = APIPricingSource("https://pricing.example.com/models.json")
        assert await source.get_all_pricing() == {}
        assert await source.get_pricing("gpt-4") is None

    @pytest.mark.asyncio
    async def test_caches_results_until_invalidated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake = _FakePricingHTTP(json_data={"gpt-4": {"input_cost_per_token": 0.000003}})
        self._install_fake_http(monkeypatch, fake)
        source = APIPricingSource("https://pricing.example.com/models.json")
        await source.get_all_pricing()
        await source.get_all_pricing()
        assert fake.get_count == 1

        source.invalidate_cache()
        await source.get_all_pricing()
        assert fake.get_count == 2

    @pytest.mark.asyncio
    async def test_supports_coroutine_json_responses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _json_coro() -> dict[str, Any]:
            return {"gpt-4": {"input_cost_per_token": 0.000003}}

        fake = _FakePricingHTTP(json_data=_json_coro())
        self._install_fake_http(monkeypatch, fake)
        source = APIPricingSource("https://pricing.example.com/models.json")
        all_pricing = await source.get_all_pricing()
        assert set(all_pricing) == {"gpt-4"}


# ── OpenRouter source ───────────────────────────────────────────────────


_OPENROUTER_PAYLOAD = {
    "data": [
        {"id": "openai/gpt-4o", "pricing": {"prompt": "0.000005", "completion": "0.000015"}},
        {"id": "custom/gpt-4o", "pricing": {"prompt": 0.0001}},
        {"id": "anthropic/claude-3", "pricing": {"prompt": 0.00003, "completion": 0.00006}},
        {"id": "", "pricing": {"prompt": "0.0001"}},
        {"id": "no-prices/model", "pricing": {}},
        {"id": "no-pricing-key/model"},
    ]
}


class TestOpenRouterPricingSource:
    @pytest.mark.asyncio
    async def test_indices_slugs_and_unambiguous_bare_aliases(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake = _FakePricingHTTP(json_data=_OPENROUTER_PAYLOAD)
        monkeypatch.setattr(pricing_sources, "ResilientHTTPClient", lambda **_: fake)
        source = OpenRouterPricingSource()

        all_pricing = await source.get_all_pricing()
        # Slug entries for every model with prices + bare-name aliases for
        # unambiguous names.
        assert set(all_pricing) == {
            "openai/gpt-4o",
            "custom/gpt-4o",
            "gpt-4o",
            "anthropic/claude-3",
            "claude-3",
        }
        # The second "gpt-4o" slug must NOT clobber the first alias.
        assert all_pricing["gpt-4o"].provider == "openai"
        gpt4o = all_pricing["openai/gpt-4o"]
        assert gpt4o.prompt_per_1m == pytest.approx(5.0)
        assert gpt4o.completion_per_1m == pytest.approx(15.0)
        assert gpt4o.source == "api:openrouter"

        # get_pricing resolves bare names case-insensitively.
        assert (await source.get_pricing("GPT-4O")) is gpt4o
        assert source.source_name == "OpenRouter API"

    @pytest.mark.asyncio
    async def test_fetch_error_degrades_without_logging_endpoint_or_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secret_endpoint = "https://private.example/prices.json?api_key=sk-private"
        private_path = "/srv/private/pricing-config.json"
        fake = _FakePricingHTTP(
            error=OSError(f"cannot reach {secret_endpoint}; config={private_path}")
        )
        monkeypatch.setattr(pricing_sources, "ResilientHTTPClient", lambda **_: fake)
        source = OpenRouterPricingSource(endpoint=secret_endpoint)

        with capture_logs() as logs:
            assert await source.get_all_pricing() == {}

        assert secret_endpoint not in repr(logs)
        assert "sk-private" not in repr(logs)
        assert private_path not in repr(logs)

    def test_to_float_tolerates_junk_values(self) -> None:
        assert OpenRouterPricingSource._to_float("0.000005") == 5e-06
        assert OpenRouterPricingSource._to_float(0.000003) == 3e-06
        assert OpenRouterPricingSource._to_float("  ") is None
        assert OpenRouterPricingSource._to_float(None) is None
        assert OpenRouterPricingSource._to_float("abc") is None


# ── Static source (incl. lazy re-export) ────────────────────────────────


class TestStaticPricingSource:
    @pytest.mark.asyncio
    async def test_normalizes_keys_and_looks_up(self) -> None:
        entry = ModelPricing(
            model="My-Model",
            prompt_per_1m=1.0,
            completion_per_1m=2.0,
            provider="custom",
        )
        source = StaticPricingSource({"My-Model": entry})
        assert (await source.get_pricing("my-model")) is entry
        assert (await source.get_pricing("MISSING")) is None
        assert list(await source.get_all_pricing()) == ["my-model"]

    def test_lazy_reexport_from_sources_module(self) -> None:
        # ``sources.StaticPricingSource`` is a PEP 562 re-export of the
        # sibling module's class.
        assert pricing_sources.StaticPricingSource is StaticPricingSource
        with pytest.raises(AttributeError, match="has no attribute"):
            pricing_sources.DoesNotExist  # noqa: B018


# ── Token counters ──────────────────────────────────────────────────────


class TestTokenCounters:
    def test_char_estimate_counter(self) -> None:
        counter = CharEstimateCounter(model="est")
        assert counter.model == "est"
        assert counter.count("a" * 80) == 20
        assert counter.count("") == 1

    def test_char_estimate_count_messages(self) -> None:
        counter = CharEstimateCounter()
        messages = [
            SimpleNamespace(role="user", name=None, content="hello there"),
            SimpleNamespace(role="assistant", name=None, content="a" * 4),
        ]
        # count("hello there")=2, count("aaaa")=1, + 4 per message.
        assert counter.count_messages(messages) == 2 + 1 + 2 * 4

    def test_huggingface_counter_fallback_without_model(self) -> None:
        counter = HuggingFaceCounter()
        assert counter.model == "huggingface"
        assert counter.count("a" * 40) == 10
        assert counter.count_messages([SimpleNamespace(content="a" * 8)]) == 2 + 4

    def test_huggingface_counter_missing_tokenizer_falls_back(self) -> None:
        # Unknown model → tokenizer load fails → char estimation.
        counter = HuggingFaceCounter(model="org/definitely-not-a-model")
        assert counter.count("a" * 40) == 10

    def test_mistral_counter_fallback_without_tokenizer(self) -> None:
        counter = MistralCounter()
        assert counter.model == "mistral"
        assert counter.count("a" * 40) == 10

    def test_tiktoken_counter_requires_package(self) -> None:
        with patch.dict("sys.modules", {"tiktoken": None}):
            with pytest.raises(ImportError):
                TiktokenCounter(model="gpt-4")


# ── SSE adapter ─────────────────────────────────────────────────────────


def _chunk(delta: str | None = None, thinking: str | None = None) -> StreamChunk:
    return StreamChunk(
        delta=delta, model="test-model", index=0, thinking_delta=thinking
    )


def _data(event: ServerSentEvent) -> dict[str, Any]:
    return loads(event.data)


class TestSSEStreamAdapter:
    def test_encode_with_and_without_id(self) -> None:
        plain = ServerSentEvent(data="payload").encode()
        assert plain == "event: message\ndata: payload\n\n"
        with_id = ServerSentEvent(data="p", event="custom", id="7").encode()
        assert with_id == "id: 7\nevent: custom\ndata: p\n\n"

    @pytest.mark.asyncio
    async def test_adapt_emits_delta_thinking_and_done_events(self) -> None:
        adapter = SSEStreamAdapter(model="m1", provider="p1")

        async def _stream() -> Any:
            yield _chunk(delta="Hel")
            yield _chunk(thinking="hmm")
            yield _chunk(delta="")  # empty → no event, counter still advances
            yield _chunk(delta="lo")

        events = [e async for e in adapter.adapt(_stream())]
        assert [e.event for e in events] == ["delta", "thinking", "delta", "done"]

        first = _data(events[0])
        assert first == {"content": "Hel", "model": "m1", "provider": "p1", "index": 1}
        assert events[0].id == "1"

        thinking = _data(events[1])
        assert thinking == {"thinking": "hmm", "model": "m1", "provider": "p1", "index": 2}

        third = _data(events[2])
        assert third["content"] == "lo"
        assert third["index"] == 4  # empty chunk consumed index 3

        done = _data(events[3])
        assert done == {"finish_reason": "stop", "model": "m1", "total_chunks": 4}
        assert events[3].event == "done"
        assert events[3].id is None

    @pytest.mark.asyncio
    async def test_adapt_emits_sanitized_error_event_on_midstream_failure(
        self, capsys
    ) -> None:
        adapter = SSEStreamAdapter(model="m1", provider="p1")
        secret = "SSE_STREAM_SECRET_SENTINEL"

        async def _bad_stream() -> Any:
            yield _chunk(delta="x")
            raise RuntimeError(secret)

        events = [e async for e in adapter.adapt(_bad_stream())]
        assert [e.event for e in events] == ["delta", "error"]
        error_event = _data(events[1])
        assert error_event == {"error": "LLM provider request failed"}
        assert secret not in events[1].encode()
        captured = capsys.readouterr()
        assert secret not in captured.out + captured.err


# ── Parallel stream aggregator ──────────────────────────────────────────


def _evt(delta: str | None = None, thinking: str | None = None, finish: str | None = None) -> Any:
    return SimpleNamespace(
        delta=delta,
        thinking_delta=thinking,
        is_thinking=thinking is not None and delta is None,
        model="race-model",
        finish_reason=finish,
    )


class _RaceProvider:
    """Synthetic LLM client whose stream_chat yields preset events."""

    def __init__(
        self,
        events: list[Any],
        delay: float = 0.0,
        error: Exception | None = None,
    ) -> None:
        self.events = events
        self.delay = delay
        self.error = error

    def stream_chat(self, messages: Any, **kwargs: Any) -> Any:
        async def _gen() -> Any:
            if self.error is not None:
                raise self.error
            for event in self.events:
                await asyncio.sleep(self.delay)
                yield event

        return _gen()


class TestParallelStreamAggregator:
    @pytest.mark.asyncio
    async def test_empty_provider_list_raises_value_error(self) -> None:
        agg = ParallelStreamAggregator(timeout=0.1)
        with pytest.raises(ValueError, match="At least one provider"):
            await agg.stream([], [])

    @pytest.mark.asyncio
    async def test_fastest_provider_wins_the_race(self) -> None:
        fast = _RaceProvider(
            [_evt(delta="Hel"), _evt(delta="lo"), _evt(delta="!", finish="stop")]
        )
        slow = _RaceProvider([_evt(delta="slow")], delay=0.05)
        agg = ParallelStreamAggregator(timeout=5)

        stream_iter = await agg.stream([fast, slow], [])
        chunks = [c async for c in stream_iter]
        assert [c.delta for c in chunks] == ["Hel", "lo", "!"]
        assert [c.index for c in chunks] == [0, 1, 2]
        assert chunks[-1].finish_reason == "stop"
        # Chunks after the first come from the winner's own stream.
        assert all(c.model == "race-model" for c in chunks)

    @pytest.mark.asyncio
    async def test_timeout_when_no_provider_starts(self) -> None:
        slow1 = _RaceProvider([_evt(delta="a")], delay=0.2)
        slow2 = _RaceProvider([_evt(delta="b")], delay=0.2)
        agg = ParallelStreamAggregator(timeout=0.05)

        stream_iter = await agg.stream([slow1, slow2], [])
        with pytest.raises(TimeoutError):
            async for _ in stream_iter:
                pass

    @pytest.mark.asyncio
    async def test_failing_probe_is_ignored_and_other_wins(self) -> None:
        failing = _RaceProvider([], error=RuntimeError("probe failed"))
        healthy = _RaceProvider([_evt(delta="ok")])
        agg = ParallelStreamAggregator(timeout=1)

        stream_iter = await agg.stream([failing, healthy], [])
        chunks = [c async for c in stream_iter]
        assert [c.delta for c in chunks] == ["ok"]

    @pytest.mark.asyncio
    async def test_thinking_only_first_event_counts_as_winner(self) -> None:
        thinker = _RaceProvider([_evt(thinking="hmm"), _evt(delta="answer")])
        other = _RaceProvider([_evt(delta="slow")], delay=0.05)
        agg = ParallelStreamAggregator(timeout=5)

        stream_iter = await agg.stream([thinker, other], [])
        chunks = [c async for c in stream_iter]
        assert chunks[0].is_thinking is True
        assert chunks[0].thinking_delta == "hmm"
        assert chunks[0].delta is None
        assert chunks[1].delta == "answer"

    @pytest.mark.asyncio
    async def test_empty_events_do_not_count_as_first_chunk(self) -> None:
        # A provider that only emits empty/think-less events never wins.
        silent = _RaceProvider([_evt(), _evt()], delay=0.0)
        real = _RaceProvider([_evt(delta="real")], delay=0.01)
        agg = ParallelStreamAggregator(timeout=5)

        stream_iter = await agg.stream([silent, real], [])
        chunks = [c async for c in stream_iter]
        assert [c.delta for c in chunks] == ["real"]
