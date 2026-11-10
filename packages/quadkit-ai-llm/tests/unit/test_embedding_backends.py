"""Round-56 pins: real embedding backends.

The five built-in embedding adapters (openai, cohere, jina, voyage,
local) previously returned **random mock vectors** while being registered
as production defaults — any RAG pipeline on them retrieved noise
silently.  This round replaced the mocks with real provider calls over
``ResilientHTTPClient``; these tests pin:

- the exact request shape (endpoint, payload, auth header) per provider,
- response vectors flowing through **verbatim** (never generated locally),
- batching, input normalization, and index ordering,
- credential resolution (config key → provider env var) and fail-fast
  ``EmbeddingError`` when neither is set,
- HTTP status → error mapping (401/403 → LLMAuthenticationError,
  429 → LLMRateLimitError, other → EmbeddingError),
- malformed-response rejection,
- the local adapter's real sentence-transformers path (lazy import,
  deterministic vectors, clean error when the dependency is missing).
"""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.ai.llm.embedding import (
    CohereEmbeddingAdapter,
    CohereEmbeddingConfig,
    JinaEmbeddingAdapter,
    JinaEmbeddingConfig,
    LocalEmbeddingAdapter,
    LocalEmbeddingConfig,
    OpenAIEmbeddingAdapter,
    OpenAIEmbeddingConfig,
    VoyageEmbeddingAdapter,
    VoyageEmbeddingConfig,
)
from quadkit.ai.llm.embedding.registry import (
    EmbeddingProviderRegistry,
    register_default_embedding_adapters,
)
from quadkit.ai.llm.exceptions import (
    EmbeddingError,
    LLMAuthenticationError,
    LLMRateLimitError,
)


def _fake_response(payload: object, status: int = 200, text: str = "") -> SimpleNamespace:
    """Minimal HTTP response double (status/json/text as the adapters read)."""
    return SimpleNamespace(status=status, json=payload, text=text or str(payload))


def _openai_payload(texts: list[str]) -> object:
    return {
        "data": [
            {"index": i, "embedding": [i + 0.1, i + 0.2]} for i in range(len(texts))
        ]
    }


def _patch_client(adapter: object, fake: MagicMock) -> Any:
    """Patch the adapter's HTTP client seam (no network)."""
    return patch.object(adapter, "_get_http_client", return_value=fake)


class TestOpenAIEmbeddingAdapter:
    async def test_vectors_flow_through_verbatim_from_transport(self) -> None:
        """The anti-mock pin: output must equal the provider response."""
        adapter = OpenAIEmbeddingAdapter(OpenAIEmbeddingConfig(api_key="sk-test"))
        fake = MagicMock(
            post=AsyncMock(return_value=_fake_response(_openai_payload(["a", "b"])))
        )
        with _patch_client(adapter, fake):
            vectors = await adapter.embed(["a", "b"])
        assert vectors == [[0.1, 0.2], [1.1, 1.2]]

    async def test_request_shape_and_auth_header(self) -> None:
        adapter = OpenAIEmbeddingAdapter(OpenAIEmbeddingConfig(api_key="sk-test"))
        fake = MagicMock(
            post=AsyncMock(return_value=_fake_response(_openai_payload(["a"])))
        )
        with _patch_client(adapter, fake):
            await adapter.embed(["a"])
        args, kwargs = fake.post.call_args
        assert args == ("/embeddings",)
        assert kwargs["data"] == {"model": "text-embedding-3-small", "input": ["a"]}
        assert kwargs["headers"] == {"Authorization": "Bearer sk-test"}

    async def test_dimensions_override_sent_when_configured(self) -> None:
        adapter = OpenAIEmbeddingAdapter(
            OpenAIEmbeddingConfig(api_key="sk-test", dimensions=256)
        )
        fake = MagicMock(
            post=AsyncMock(return_value=_fake_response(_openai_payload(["a"])))
        )
        with _patch_client(adapter, fake):
            await adapter.embed(["a"])
        assert fake.post.call_args.kwargs["data"]["dimensions"] == 256

    def test_base_url_from_config(self) -> None:
        adapter = OpenAIEmbeddingAdapter(
            OpenAIEmbeddingConfig(api_key="sk-test", base_url="http://proxy/v1")
        )
        assert adapter._get_http_client().base_url == "http://proxy/v1"

    async def test_response_rows_reordered_by_index(self) -> None:
        adapter = OpenAIEmbeddingAdapter(OpenAIEmbeddingConfig(api_key="sk-test"))
        payload = {
            "data": [
                {"index": 1, "embedding": [2.0]},
                {"index": 0, "embedding": [1.0]},
            ]
        }
        fake = MagicMock(post=AsyncMock(return_value=_fake_response(payload)))
        with _patch_client(adapter, fake):
            assert await adapter.embed(["a", "b"]) == [[1.0], [2.0]]

    async def test_batching_splits_requests_and_preserves_order(self) -> None:
        adapter = OpenAIEmbeddingAdapter(OpenAIEmbeddingConfig(api_key="sk-test"))
        responses = [
            _fake_response(_openai_payload(["a", "b"])),
            _fake_response(_openai_payload(["c"])),
        ]
        fake = MagicMock(post=AsyncMock(side_effect=responses))
        with _patch_client(adapter, fake):
            vectors = await adapter.embed(["a", "b", "c"], batch_size=2)
        assert fake.post.await_count == 2
        assert fake.post.call_args_list[0].kwargs["data"]["input"] == ["a", "b"]
        assert fake.post.call_args_list[1].kwargs["data"]["input"] == ["c"]
        assert len(vectors) == 3

    async def test_empty_input_returns_without_request(self) -> None:
        adapter = OpenAIEmbeddingAdapter(OpenAIEmbeddingConfig(api_key="sk-test"))
        fake = MagicMock(post=AsyncMock())
        with _patch_client(adapter, fake):
            assert await adapter.embed([]) == []
        fake.post.assert_not_awaited()

    async def test_missing_key_raises_embedding_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        adapter = OpenAIEmbeddingAdapter(OpenAIEmbeddingConfig())
        with pytest.raises(EmbeddingError, match="OPENAI_API_KEY"):
            await adapter.embed(["a"])

    async def test_env_var_key_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
        adapter = OpenAIEmbeddingAdapter(OpenAIEmbeddingConfig())
        fake = MagicMock(
            post=AsyncMock(return_value=_fake_response(_openai_payload(["a"])))
        )
        with _patch_client(adapter, fake):
            await adapter.embed(["a"])
        assert fake.post.call_args.kwargs["headers"]["Authorization"] == "Bearer sk-env"

    async def test_401_maps_to_authentication_error(self) -> None:
        adapter = OpenAIEmbeddingAdapter(OpenAIEmbeddingConfig(api_key="sk-test"))
        fake = MagicMock(
            post=AsyncMock(return_value=_fake_response({"error": "nope"}, 401))
        )
        with _patch_client(adapter, fake):
            with pytest.raises(LLMAuthenticationError):
                await adapter.embed(["a"])

    async def test_429_maps_to_rate_limit_error(self) -> None:
        adapter = OpenAIEmbeddingAdapter(OpenAIEmbeddingConfig(api_key="sk-test"))
        fake = MagicMock(
            post=AsyncMock(return_value=_fake_response({"error": "slow down"}, 429))
        )
        with _patch_client(adapter, fake):
            with pytest.raises(LLMRateLimitError):
                await adapter.embed(["a"])

    async def test_500_maps_to_embedding_error(self) -> None:
        adapter = OpenAIEmbeddingAdapter(OpenAIEmbeddingConfig(api_key="sk-test"))
        fake = MagicMock(
            post=AsyncMock(return_value=_fake_response({"error": "boom"}, 500))
        )
        with _patch_client(adapter, fake):
            with pytest.raises(EmbeddingError, match="HTTP 500"):
                await adapter.embed(["a"])

    async def test_provider_error_body_is_not_exposed(self) -> None:
        private_detail = "api_key=sk-private /srv/tenant-42/private.txt"
        adapter = OpenAIEmbeddingAdapter(OpenAIEmbeddingConfig(api_key="sk-test"))
        fake = MagicMock(
            post=AsyncMock(
                return_value=_fake_response({}, 500, text=private_detail)
            )
        )
        with _patch_client(adapter, fake):
            with pytest.raises(EmbeddingError) as exc_info:
                await adapter.embed(["a"])

        message = str(exc_info.value)
        assert "HTTP 500" in message
        assert "api_key=sk-private" not in message
        assert "/srv/tenant-42/private.txt" not in message

    @pytest.mark.parametrize(
        "payload",
        [
            {"foo": 1},
            {"data": [{"index": 0}]},
        ],
    )
    async def test_malformed_response_raises(self, payload: object) -> None:
        adapter = OpenAIEmbeddingAdapter(OpenAIEmbeddingConfig(api_key="sk-test"))
        fake = MagicMock(post=AsyncMock(return_value=_fake_response(payload)))
        with _patch_client(adapter, fake):
            with pytest.raises(EmbeddingError):
                await adapter.embed(["a"])

    async def test_health_check_without_key_is_unhealthy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        adapter = OpenAIEmbeddingAdapter(OpenAIEmbeddingConfig())
        result = await adapter.health_check()
        assert result.status.value == "unhealthy"
        message = result.message
        assert message is not None
        assert "API key" in message

    async def test_health_check_with_key_is_healthy(self) -> None:
        adapter = OpenAIEmbeddingAdapter(OpenAIEmbeddingConfig(api_key="sk-test"))
        result = await adapter.health_check()
        assert result.status.value == "healthy"

    async def test_close_closes_http_client(self) -> None:
        adapter = OpenAIEmbeddingAdapter(OpenAIEmbeddingConfig(api_key="sk-test"))
        fake = MagicMock(close=AsyncMock())
        adapter._client = fake
        await adapter.close()
        fake.close.assert_awaited_once()
        assert adapter._client is None


class TestJinaEmbeddingAdapter:
    def test_jina_base_url(self) -> None:
        adapter = JinaEmbeddingAdapter(JinaEmbeddingConfig(api_key="jina-test"))
        assert adapter._get_http_client().base_url == "https://api.jina.ai/v1"

    async def test_jina_defaults_and_env_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("JINA_API_KEY", "jina-env")
        adapter = JinaEmbeddingAdapter(JinaEmbeddingConfig())
        fake = MagicMock(
            post=AsyncMock(return_value=_fake_response(_openai_payload(["a"])))
        )
        with _patch_client(adapter, fake):
            await adapter.embed(["a"])
        data = fake.post.call_args.kwargs["data"]
        assert data["model"] == "jina-embeddings-v3"
        assert fake.post.call_args.kwargs["headers"]["Authorization"] == "Bearer jina-env"


class TestVoyageEmbeddingAdapter:
    def test_voyage_base_url(self) -> None:
        adapter = VoyageEmbeddingAdapter(VoyageEmbeddingConfig(api_key="vg-test"))
        assert adapter._get_http_client().base_url == "https://api.voyageai.com/v3"

    async def test_voyage_defaults_and_no_dimensions_field(self) -> None:
        adapter = VoyageEmbeddingAdapter(
            VoyageEmbeddingConfig(api_key="vg-test", dimensions=256)
        )
        fake = MagicMock(
            post=AsyncMock(return_value=_fake_response(_openai_payload(["a"])))
        )
        with _patch_client(adapter, fake):
            await adapter.embed(["a"])
        data = fake.post.call_args.kwargs["data"]
        assert data["model"] == "voyage-3"
        # Voyage selects dimensions per model — never send the field.
        assert "dimensions" not in data


class TestCohereEmbeddingAdapter:
    def test_cohere_base_url(self) -> None:
        adapter = CohereEmbeddingAdapter(CohereEmbeddingConfig(api_key="co-test"))
        assert adapter._get_http_client().base_url == "https://api.cohere.com"

    async def test_request_shape_and_response_mapping(self) -> None:
        adapter = CohereEmbeddingAdapter(CohereEmbeddingConfig(api_key="co-test"))
        payload = {"embeddings": [[0.5, 0.6]]}
        fake = MagicMock(post=AsyncMock(return_value=_fake_response(payload)))
        with _patch_client(adapter, fake):
            vectors = await adapter.embed(["a"])
        args, kwargs = fake.post.call_args
        assert args == ("/v2/embed",)
        assert kwargs["data"] == {
            "model": "embed-english-v3.0",
            "texts": ["a"],
            "input_type": "search_document",
        }
        assert kwargs["headers"] == {"Authorization": "Bearer co-test"}
        assert vectors == [[0.5, 0.6]]

    async def test_missing_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("COHERE_API_KEY", raising=False)
        adapter = CohereEmbeddingAdapter(CohereEmbeddingConfig())
        with pytest.raises(EmbeddingError, match="COHERE_API_KEY"):
            await adapter.embed(["a"])

    async def test_401_maps_to_authentication_error(self) -> None:
        adapter = CohereEmbeddingAdapter(CohereEmbeddingConfig(api_key="co-test"))
        fake = MagicMock(post=AsyncMock(return_value=_fake_response({}, 401)))
        with _patch_client(adapter, fake):
            with pytest.raises(LLMAuthenticationError):
                await adapter.embed(["a"])


class TestLocalEmbeddingAdapter:
    async def test_missing_dependency_raises_clean_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "sentence_transformers", None)
        adapter = LocalEmbeddingAdapter(LocalEmbeddingConfig())
        with pytest.raises(EmbeddingError, match="sentence-transformers"):
            await adapter.embed(["a"])

    async def test_embed_uses_sentence_transformers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        encode_calls: list[tuple[list[str], int]] = []

        class _FakeST:
            def __init__(self, model: str, device: str, cache_folder: object) -> None:
                assert model == "all-MiniLM-L6-v2"

            def encode(self, texts: list[str], batch_size: int) -> list[list[float]]:
                encode_calls.append((list(texts), batch_size))
                return [[0.25, 0.5], [0.75, 1.0]]

        fake_module = types.ModuleType("sentence_transformers")
        fake_module.SentenceTransformer = _FakeST  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

        adapter = LocalEmbeddingAdapter(LocalEmbeddingConfig())
        vectors = await adapter.embed(["a", "b"], batch_size=2)
        assert vectors == [[0.25, 0.5], [0.75, 1.0]]
        assert encode_calls == [(["a", "b"], 2)]

    async def test_health_check_unhealthy_when_model_unloadable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "sentence_transformers", None)
        adapter = LocalEmbeddingAdapter(LocalEmbeddingConfig())
        result = await adapter.health_check()
        assert result.status.value == "unhealthy"
        message = result.message
        assert message is not None
        assert "Embedding health check failed (EmbeddingError)" in message
        assert "sentence-transformers" not in message


class TestRegistryIntegration:
    def test_default_registry_adapters_are_the_real_backends(self) -> None:
        registry = EmbeddingProviderRegistry()
        register_default_embedding_adapters(registry)
        assert sorted(registry.list_providers()) == [
            "cohere",
            "jina",
            "local",
            "openai",
            "voyage",
        ]

    async def test_registry_openai_adapter_uses_real_transport(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-registry")
        registry = EmbeddingProviderRegistry()
        register_default_embedding_adapters(registry)
        adapter = registry.get_adapter("openai")
        assert isinstance(adapter, OpenAIEmbeddingAdapter)
        # The registry's adapter must go through the real transport seam,
        # never generating vectors locally.
        fake = MagicMock(
            post=AsyncMock(return_value=_fake_response(_openai_payload(["x"])))
        )
        with _patch_client(adapter, fake):
            assert await adapter.embed(["x"]) == [[0.1, 0.2]]
