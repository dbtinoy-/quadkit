"""End-to-end scenario tests for the Ollama and Cloudflare Workers clients.

Drives ``OllamaClient`` and ``CloudflareWorkersClient`` through their public
``complete`` / ``chat`` / ``stream_chat`` / ``health_check`` / ``close``
entry points with a fully mocked transport layer:

* Ollama — the ``ollama`` package is not installed in the test environment,
  so a fake module is injected via ``sys.modules`` (same convention as
  ``test_ollama_multimodal.py``) whose ``AsyncClient`` factory yields a
  controllable fake handle.
* Cloudflare Workers — the client's lazily-created ``ResilientHTTPClient``
  is replaced with a fake exposing ``post`` / ``get`` / ``close``.

These tests intentionally exercise the full template-method path
(retry/circuit-breaker plumbing in ``AbstractLLMClient``) rather than the
provider-specific ``_do_*`` helpers directly.
"""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest

from quadkit.ai.llm.clients.cloudflare_workers import CloudflareWorkersClient
from quadkit.ai.llm.clients.ollama import OllamaClient
from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.exceptions import (
    LLMAuthenticationError,
    LLMError,
    LLMModelNotFoundError,
    LLMRateLimitError,
)
from quadkit.ai.llm.types import AIError, ChatMessage
from quadkit.contracts.ai.agents.types import ToolDefinition
from quadkit.contracts.ai.llm import FunctionCall, Role, ToolCall
from quadkit.contracts.ai.multimodal import ImageBase64Part, ImageUrlPart
from quadkit.contracts.ai.thinking import ThinkingConfig
from quadkit.contracts.core.health import HealthStatus
from quadkit.contracts.web.http_models import HttpResponse, HttpStatusError

# ── Ollama fakes ────────────────────────────────────────────────────────


class _FakeOllamaAsyncClient:
    """Controllable stand-in for ``ollama.AsyncClient``."""

    def __init__(self) -> None:
        self.chat_response: Any = None
        self.chat_stream: Any = None
        self.chat_error: Exception | None = None
        self.chat_calls: list[dict[str, Any]] = []
        self.list_result: Any = None
        self.list_error: Exception | None = None
        self.closed = False

    async def chat(self, **kwargs: Any) -> Any:
        self.chat_calls.append(kwargs)
        if self.chat_error is not None:
            raise self.chat_error
        if self.chat_stream is not None:
            return self.chat_stream
        return self.chat_response

    async def list(self) -> Any:
        if self.list_error is not None:
            raise self.list_error
        return self.list_result

    async def close(self) -> None:
        self.closed = True


def _ollama_client(
    fake: _FakeOllamaAsyncClient,
    **config_kwargs: Any,
) -> OllamaClient:
    """Construct an ``OllamaClient`` with the fake transport installed."""
    module = types.ModuleType("ollama")
    module.AsyncClient = (lambda **_: fake)  # type: ignore[attr-defined]
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(sys.modules, "ollama", module)
        return OllamaClient(config=ClientConfig(model="llama3", **config_kwargs))


def _assistant_chunk(
    content: str | None = None,
    *,
    done: bool = False,
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant"}
    if content is not None:
        message["content"] = content
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return {"model": "llama3", "message": message, "done": done}


def _user(msg: str = "Hello") -> ChatMessage:
    return ChatMessage(role=Role.USER, content=msg)


class TestOllamaClientScenarios:
    """Public-entry-point scenarios for the Ollama client."""

    @pytest.mark.asyncio
    async def test_complete_success_maps_content_usage_and_metadata(self) -> None:
        fake = _FakeOllamaAsyncClient()
        fake.chat_response = {
            "model": "llama3",
            "message": {"role": "assistant", "content": "Hello from Ollama"},
            "done": True,
            "prompt_eval_count": 10,
            "eval_count": 5,
            "total_duration": 2_000_000_000,
            "load_duration": 500_000_000,
        }
        client = _ollama_client(fake)
        result = await client.complete([_user()])

        assert result.is_ok()
        completion = result.unwrap()
        assert completion.content == "Hello from Ollama"
        assert completion.model == "llama3"
        assert completion.usage is not None
        assert completion.usage.prompt_tokens == 10
        assert completion.usage.completion_tokens == 5
        assert completion.usage.total_tokens == 15
        assert completion.metadata is not None
        # Ollama reports durations in nanoseconds; they pass through as-is.
        assert completion.metadata["total_duration"] == 2_000_000_000
        assert completion.metadata["load_duration"] == 500_000_000

        # Request shape: model + options (temperature / max_tokens).
        call = fake.chat_calls[0]
        assert call["model"] == "llama3"
        assert call["options"]["temperature"] == pytest.approx(0.7)
        assert call["options"]["num_predict"] is None  # max_tokens unset
        assert call["messages"] == [{"role": "user", "content": "Hello"}]

    @pytest.mark.asyncio
    async def test_complete_with_max_tokens_and_explicit_temperature(self) -> None:
        fake = _FakeOllamaAsyncClient()
        fake.chat_response = _assistant_chunk("ok")
        client = _ollama_client(fake)
        await client.complete([_user()], temperature=0.1, max_tokens=128)

        call = fake.chat_calls[0]
        assert call["options"]["temperature"] == pytest.approx(0.1)
        assert call["options"]["num_predict"] == 128

    @pytest.mark.asyncio
    async def test_complete_thinking_suppression_injects_think_false(self) -> None:
        fake = _FakeOllamaAsyncClient()
        fake.chat_response = _assistant_chunk("ok")
        client = _ollama_client(fake, thinking=ThinkingConfig(suppress=True))
        await client.complete([_user()])
        assert fake.chat_calls[0]["think"] is False

    @pytest.mark.asyncio
    async def test_complete_without_thinking_config_omits_think(self) -> None:
        fake = _FakeOllamaAsyncClient()
        fake.chat_response = _assistant_chunk("ok")
        client = _ollama_client(fake)
        await client.complete([_user()])
        assert "think" not in fake.chat_calls[0]

    @pytest.mark.asyncio
    async def test_complete_passes_extra_kwargs_through(self) -> None:
        fake = _FakeOllamaAsyncClient()
        fake.chat_response = _assistant_chunk("ok")
        client = _ollama_client(fake)
        await client.complete([_user()], seed=42, top_k=5)
        assert fake.chat_calls[0]["seed"] == 42
        assert fake.chat_calls[0]["top_k"] == 5

    @pytest.mark.asyncio
    async def test_complete_converts_tool_definitions_into_payload(self) -> None:
        fake = _FakeOllamaAsyncClient()
        fake.chat_response = _assistant_chunk("ok")
        client = _ollama_client(fake)
        tools = [
            ToolDefinition(
                name="get_weather",
                description="Get the weather for a city",
                parameters={
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            ),
            ToolDefinition(name="", description="skip me", parameters={}),
        ]
        await client.complete([_user()], tools=tools)

        assert fake.chat_calls[0]["tools"] == [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get the weather for a city",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                        "required": ["city"],
                    },
                },
            }
        ]

    @pytest.mark.asyncio
    async def test_chat_entry_point_forwards_tools_to_payload(self) -> None:
        """Regression (BUG #43): chat(..., tools=...) must not drop tools."""
        fake = _FakeOllamaAsyncClient()
        fake.chat_response = _assistant_chunk("ok")
        client = _ollama_client(fake)
        tools = [ToolDefinition(name="get_weather", description="d", parameters={})]
        result = await client.chat([_user()], tools=tools)

        assert result.is_ok()
        assert fake.chat_calls[0]["tools"] == [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "d",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

    @pytest.mark.asyncio
    async def test_complete_parses_response_tool_calls(self) -> None:
        fake = _FakeOllamaAsyncClient()
        fake.chat_response = {
            "model": "llama3",
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"city": "Manila"}',
                        }
                    },
                    {"function": None},  # malformed entry → skipped
                ],
            },
            "done": True,
        }
        client = _ollama_client(fake)
        result = await client.complete([_user()])

        assert result.is_ok()
        completion = result.unwrap()
        assert completion.tool_calls is not None
        assert len(completion.tool_calls) == 1
        tool_call = completion.tool_calls[0]
        assert tool_call.id  # synthetic uuid hex for id-less Ollama calls
        assert tool_call.function is not None
        assert tool_call.function.name == "get_weather"
        # Ollama returns arguments as a raw JSON string; it is kept as-is.
        assert tool_call.function.arguments == '{"city": "Manila"}'

    @pytest.mark.asyncio
    async def test_complete_parses_sdk_style_tool_call_objects(self) -> None:
        fake = _FakeOllamaAsyncClient()
        tool_call_obj = SimpleNamespace(
            id="explicit-id",
            function=SimpleNamespace(name="fn", arguments='{"a": 1}'),
        )
        fake.chat_response = {
            "model": "llama3",
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [tool_call_obj],
            },
            "done": True,
        }
        client = _ollama_client(fake)
        result = await client.complete([_user()])

        completion = result.unwrap()
        assert completion.tool_calls is not None
        # Ollama responses get synthetic ids regardless of input objects.
        assert completion.tool_calls[0].id
        assert completion.tool_calls[0].function is not None
        assert completion.tool_calls[0].function.name == "fn"
        assert completion.tool_calls[0].function.arguments == '{"a": 1}'

    @pytest.mark.asyncio
    async def test_complete_keeps_raw_arguments_verbatim(self) -> None:
        # _parse_tool_calls preserves raw argument payloads (string or
        # non-dict) as received; the round-trip serializer is responsible
        # for normalising them on the way back out.
        fake = _FakeOllamaAsyncClient()
        fake.chat_response = {
            "model": "llama3",
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"function": {"name": "fn", "arguments": "{not-json"}},
                    {"function": {"name": "fn2", "arguments": 42}},
                ],
            },
            "done": True,
        }
        client = _ollama_client(fake)
        result = await client.complete([_user()])

        completion = result.unwrap()
        assert completion.tool_calls is not None
        assert completion.tool_calls[0].function is not None
        assert completion.tool_calls[0].function.arguments == "{not-json"
        assert completion.tool_calls[1].function is not None
        assert completion.tool_calls[1].function.arguments == 42

    @pytest.mark.asyncio
    async def test_complete_failure_raises_sanitized_ai_error(self) -> None:
        fake = _FakeOllamaAsyncClient()
        secret = "INVALID_MODEL_SECRET_SENTINEL"
        # "invalid" keeps the base template from retrying in this test.
        fake.chat_error = RuntimeError(f"invalid {secret}")
        client = _ollama_client(fake)

        with pytest.raises(AIError) as exc:
            await client.complete([_user()])

        assert secret not in str(exc.value)
        assert secret not in repr(exc.value.to_dict())
        assert exc.value.details == {"error_type": "LLMError"}

    @pytest.mark.asyncio
    async def test_stream_yields_non_empty_deltas_and_stops_on_done(self) -> None:
        fake = _FakeOllamaAsyncClient()

        async def _stream() -> Any:
            yield _assistant_chunk("Hel")
            yield _assistant_chunk("")  # empty delta → skipped
            yield _assistant_chunk("lo")
            yield _assistant_chunk("!", done=True)

        fake.chat_stream = _stream()
        client = _ollama_client(fake)
        stream = client.stream_chat([_user()])

        chunks = []
        async for chunk in stream:
            chunks.append(chunk)

        assert not stream.failed
        assert [c.delta for c in chunks] == ["Hel", "lo", "!"]
        assert [c.index for c in chunks] == [0, 1, 2]
        # The final chunk (content + done) carries the finish reason.
        assert chunks[-1].finish_reason == "stop"
        assert chunks[0].finish_reason is None
        # Stream request shape: stream=True, same model/options.
        call = fake.chat_calls[0]
        assert call["stream"] is True
        assert call["model"] == "llama3"

    @pytest.mark.asyncio
    async def test_stream_failure_is_typed_stream_error(self) -> None:
        secret = "INVALID_STREAM_SECRET_SENTINEL"

        async def _boom() -> Any:
            yield _assistant_chunk("x")
            # "invalid" keeps the base template from retrying (and
            # re-consumes the one-shot fake stream).
            raise RuntimeError(f"invalid {secret}")

        fake = _FakeOllamaAsyncClient()
        fake.chat_stream = _boom()
        client = _ollama_client(fake)
        stream = client.stream_chat([_user()])

        chunks = []
        async for chunk in stream:
            chunks.append(chunk)

        assert [c.delta for c in chunks] == ["x"]
        assert len(fake.chat_calls) == 1
        assert stream.failed
        assert isinstance(stream.error, AIError)
        assert secret not in str(stream.error)
        assert secret not in repr(stream.error.to_dict())

    @pytest.mark.asyncio
    async def test_health_check_healthy_lists_available_models(self) -> None:
        fake = _FakeOllamaAsyncClient()
        fake.list_result = SimpleNamespace(
            models=[
                SimpleNamespace(model="llama3"),
                SimpleNamespace(model="mistral"),
            ]
        )
        client = _ollama_client(fake)
        health = await client.health_check()

        assert health.status is HealthStatus.HEALTHY
        assert health.component == "llm.ollama"
        assert health.details == {
            "provider": "ollama",
            "model": "llama3",
            "available_models": ["llama3", "mistral"],
        }

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_on_connection_failure(self) -> None:
        fake = _FakeOllamaAsyncClient()
        fake.list_error = ConnectionError("refused")
        client = _ollama_client(fake)
        health = await client.health_check()

        assert health.status is HealthStatus.UNHEALTHY
        assert "ConnectionError" in health.error
        assert "refused" not in health.error

    @pytest.mark.asyncio
    async def test_close_releases_the_transport(self) -> None:
        """Regression (BUG #44): close() must close the underlying transport."""
        fake = _FakeOllamaAsyncClient()
        client = _ollama_client(fake)
        await client.close()
        assert fake.closed is True
        assert client._closed is True  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_model_manager_switches_and_loads_on_first_use(self) -> None:
        calls: list[tuple[str, str]] = []

        class _FakeModelManager:
            async def switch_provider(self, name: str) -> None:
                calls.append(("switch", name))

            async def load_model(self, model: str) -> None:
                calls.append(("load", model))

        fake = _FakeOllamaAsyncClient()
        fake.chat_response = _assistant_chunk("ok")
        client = _ollama_client(fake)
        client.model_manager = _FakeModelManager()  # type: ignore[assignment]
        # A different current model forces the switch+load path.
        client.current_model = "other-model"
        result = await client.complete([_user()])

        assert result.is_ok()
        assert calls == [("switch", "ollama"), ("load", "llama3")]
        assert client.current_model == "llama3"
        # Second completion: already the current model → no extra work.
        await client.complete([_user()])
        assert calls == [("switch", "ollama"), ("load", "llama3")]

    @pytest.mark.asyncio
    async def test_model_manager_none_is_a_noop(self) -> None:
        fake = _FakeOllamaAsyncClient()
        fake.chat_response = _assistant_chunk("ok")
        client = _ollama_client(fake)
        client.current_model = "other-model"
        result = await client.complete([_user()])
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_image_url_content_is_prefetched_to_base64(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from quadkit.ai.llm.clients import ollama as ollama_module

        fetched: list[str] = []

        async def _fake_fetch(url: str, timeout: float = 10.0) -> ImageBase64Part:
            fetched.append(url)
            return ImageBase64Part(data="aW1hZ2U=", media_type="image/png")

        monkeypatch.setattr(ollama_module, "fetch_image_as_base64", _fake_fetch)
        fake = _FakeOllamaAsyncClient()
        fake.chat_response = _assistant_chunk("ok")
        client = _ollama_client(fake)
        message = ChatMessage(role=Role.USER, content=[ImageUrlPart(url="http://x/i.png")])
        await client.complete([message])

        assert fetched == ["http://x/i.png"]
        assert fake.chat_calls[0]["messages"] == [
            {"role": "user", "content": "", "images": ["aW1hZ2U="]}
        ]


class TestOllamaStaticHelpers:
    """Unit coverage for the pure serialization helpers."""

    def test_convert_tools_defaults_parameters_and_skips_nameless(self) -> None:
        tools = [
            SimpleNamespace(name="t1", description="d1"),  # no parameters attr
            SimpleNamespace(name="", description="skip"),
            SimpleNamespace(
                name="t2",
                description="d2",
                parameters={"type": "object", "properties": {"x": {"type": "int"}}},
            ),
        ]
        assert OllamaClient._convert_tools(tools) == [
            {
                "type": "function",
                "function": {
                    "name": "t1",
                    "description": "d1",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "t2",
                    "description": "d2",
                    "parameters": {"type": "object", "properties": {"x": {"type": "int"}}},
                },
            },
        ]

    def test_serialize_tool_calls_handles_string_args_and_none_function(self) -> None:
        fake = _FakeOllamaAsyncClient()
        client = _ollama_client(fake)
        tool_calls = [
            ToolCall(
                id="1", type="function", function=FunctionCall(name="f", arguments='{"a": 1}')
            ),
            ToolCall(
                id="2", type="function", function=FunctionCall(name="g", arguments={"b": 2})
            ),
            ToolCall(id="3", type="function", function=None),
        ]
        serialized = client._serialize_tool_calls(tool_calls)  # noqa: SLF001
        assert serialized == [
            {"function": {"name": "f", "arguments": {"a": 1}}},
            {"function": {"name": "g", "arguments": {"b": 2}}},
        ]

    def test_parse_tool_calls_none_and_empty(self) -> None:
        assert OllamaClient._parse_tool_calls(None) is None
        assert OllamaClient._parse_tool_calls([]) is None


# ── Cloudflare Workers fakes ────────────────────────────────────────────


class _FakeCFHTTP:
    """Controllable stand-in for ``ResilientHTTPClient``."""

    def __init__(self) -> None:
        self.post_result: Any = None
        self.get_result: Any = None
        self.post_error: Exception | None = None
        self.get_error: Exception | None = None
        self.posts: list[tuple[str, dict[str, Any]]] = []
        self.get_urls: list[str] = []
        self.closed = False

    async def post(self, url: str, **kwargs: Any) -> Any:
        self.posts.append((url, kwargs.get("json")))
        if self.post_error is not None:
            raise self.post_error
        return self.post_result

    async def get(self, url: str, **kwargs: Any) -> Any:
        self.get_urls.append(url)
        if self.get_error is not None:
            raise self.get_error
        return self.get_result

    async def close(self) -> None:
        self.closed = True


def _cf_client(fake: _FakeCFHTTP, **extra: Any) -> CloudflareWorkersClient:
    """Construct a Cloudflare client wired to the fake HTTP layer."""
    payload = dict(extra)
    payload.setdefault("cf_account_id", "acct-123")
    payload.setdefault("cf_api_token", "token-abc")
    client = CloudflareWorkersClient(
        config=ClientConfig(provider="cloudflare", model="cf-model", extra=payload)
    )
    # Replace the lazily-created transport with the fake.
    object.__setattr__(client, "_http", fake)
    return client


def _http_error(status: int, message: str) -> HttpStatusError:
    return HttpStatusError(message, status=status, response=HttpResponse(status=status))


class TestCloudflareClientScenarios:
    """Public-entry-point scenarios for the Cloudflare Workers client."""

    def test_init_requires_account_id_and_token(self) -> None:
        with pytest.raises(LLMAuthenticationError, match="cf_account_id"):
            CloudflareWorkersClient(config=ClientConfig(model="m", extra={}))
        with pytest.raises(LLMAuthenticationError):
            CloudflareWorkersClient(
                config=ClientConfig(model="m", extra={"cf_account_id": "a"})
            )
        with pytest.raises(LLMAuthenticationError):
            CloudflareWorkersClient(
                config=ClientConfig(model="m", extra={"cf_api_token": "t"})
            )

    @pytest.mark.asyncio
    async def test_complete_success_posts_converted_messages(self) -> None:
        fake = _FakeCFHTTP()
        fake.post_result = HttpResponse(
            status=200,
            json={
                "success": True,
                "result": {
                    "response": "Hi from CF",
                    "usage": {
                        "prompt_tokens": 7,
                        "completion_tokens": 3,
                        "total_tokens": 10,
                    },
                },
            },
        )
        client = _cf_client(fake)
        result = await client.complete([_user("Hi there")])

        assert result.is_ok()
        completion = result.unwrap()
        assert completion.content == "Hi from CF"
        assert completion.model == "cf-model"
        assert completion.usage is not None
        assert completion.usage.prompt_tokens == 7
        assert completion.usage.completion_tokens == 3
        assert completion.usage.total_tokens == 10

        url, payload = fake.posts[0]
        assert url == "/client/v4/accounts/acct-123/ai/run/cf-model"
        assert payload["stream"] is False
        assert payload["temperature"] == pytest.approx(0.2)
        assert "max_tokens" not in payload
        assert payload["messages"] == [{"role": "user", "content": "Hi there"}]

    @pytest.mark.asyncio
    async def test_complete_max_tokens_and_tools_in_payload(self) -> None:
        fake = _FakeCFHTTP()
        fake.post_result = HttpResponse(
            status=200, json={"success": True, "result": {"response": "ok"}}
        )
        client = _cf_client(fake)
        tools = [ToolDefinition(name="fn", description="d", parameters={})]
        await client.complete([_user()], max_tokens=64, tools=tools)

        _, payload = fake.posts[0]
        assert payload["max_tokens"] == 64
        assert payload["tools"] == [
            {
                "type": "function",
                "function": {"name": "fn", "description": "d", "parameters": {}},
            }
        ]

    @pytest.mark.asyncio
    async def test_chat_entry_point_forwards_tools(self) -> None:
        fake = _FakeCFHTTP()
        fake.post_result = HttpResponse(
            status=200, json={"success": True, "result": {"response": "ok"}}
        )
        client = _cf_client(fake)
        tools = [ToolDefinition(name="fn", description="d", parameters={})]
        result = await client.chat([_user()], tools=tools)
        assert result.is_ok()
        _, payload = fake.posts[0]
        assert "tools" in payload

    @pytest.mark.asyncio
    async def test_complete_success_false_returns_sanitized_llm_error(self) -> None:
        secret = "INVALID_PROMPT_SECRET_SENTINEL"
        fake = _FakeCFHTTP()
        fake.post_result = HttpResponse(
            status=200, json={"success": False, "errors": [f"invalid {secret}"]}
        )
        client = _cf_client(fake)
        result = await client.complete([_user()])

        assert result.is_err()
        error = result.unwrap_err()
        assert secret not in str(error)
        assert secret not in repr(error.to_dict())

    @pytest.mark.asyncio
    async def test_complete_parses_response_tool_calls(self) -> None:
        fake = _FakeCFHTTP()
        fake.post_result = HttpResponse(
            status=200,
            json={
                "success": True,
                "result": {
                    "response": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "function": {"name": "fn", "arguments": '{"a": 1}'},
                        },
                        {"function": {"name": "fn2", "arguments": {"b": 2}}},
                    ],
                },
            },
        )
        client = _cf_client(fake)
        result = await client.complete([_user()])

        completion = result.unwrap()
        tool_calls = completion.tool_calls
        assert tool_calls is not None
        assert len(tool_calls) == 2
        assert tool_calls[0].id == "call_1"
        assert tool_calls[0].function is not None
        assert tool_calls[0].function.name == "fn"
        assert tool_calls[0].function.arguments == '{"a": 1}'
        # id-less call falls back to the function name; dict args are
        # JSON-encoded for the wire format.
        assert tool_calls[1].id == "fn2"
        assert tool_calls[1].function is not None
        # orjson dumps are compact (no spaces).
        assert tool_calls[1].function.arguments == '{"b":2}'

    @pytest.mark.parametrize(
        ("status", "message", "expected"),
        [
            (401, "invalid token", LLMAuthenticationError),
            (403, "forbidden", LLMAuthenticationError),
            (429, "rate limited", LLMRateLimitError),
            (404, "nope", LLMModelNotFoundError),
            (400, "Model 'nope' does not exist", LLMModelNotFoundError),
            (400, "bad payload", LLMError),
        ],
        ids=["401", "403", "429", "404", "400-not-found", "400-bad-request"],
    )
    @pytest.mark.asyncio
    async def test_error_matrix_maps_to_typed_failures(
        self, status: int, message: str, expected: type[LLMError]
    ) -> None:
        fake = _FakeCFHTTP()
        fake.post_error = _http_error(status, message)
        client = _cf_client(fake)

        if expected is LLMAuthenticationError:
            with pytest.raises(LLMAuthenticationError):
                await client.complete([_user()])
            return

        result = await client.complete([_user()])
        assert result.is_err()
        assert isinstance(result.unwrap_err(), expected)

    @pytest.mark.asyncio
    async def test_unexpected_exception_becomes_sanitized_ai_error(self) -> None:
        fake = _FakeCFHTTP()
        secret = "UPSTREAM_SECRET_SENTINEL"
        # No ``status`` attribute → falls through to the generic AIError
        # branch; "invalid" keeps the base template from retrying.
        fake.post_error = RuntimeError(f"invalid {secret}")
        client = _cf_client(fake)
        with pytest.raises(AIError) as exc:
            await client.complete([_user()])
        assert secret not in str(exc.value)
        assert secret not in repr(exc.value.to_dict())

    @pytest.mark.asyncio
    async def test_http_500_becomes_sanitized_ai_error(self) -> None:
        fake = _FakeCFHTTP()
        secret = "UPSTREAM_RESPONSE_SECRET_SENTINEL"
        fake.post_error = _http_error(500, f"invalid {secret}")
        client = _cf_client(fake)
        with pytest.raises(AIError) as exc:
            await client.complete([_user()])
        assert secret not in str(exc.value)
        assert secret not in repr(exc.value.to_dict())

    @pytest.mark.asyncio
    async def test_stream_chat_yields_sse_deltas(self) -> None:
        body = (
            "event: ping\n"
            "id: 1\n"
            'data: {"response": "Hel"}\n'
            "\n"
            'data: {"response": "lo"}\n'
            "data: [DONE]\n"
            "data: not-json\n"
        )
        fake = _FakeCFHTTP()
        fake.post_result = HttpResponse(status=200, text=body)
        client = _cf_client(fake)
        stream = client.stream_chat([_user()])

        chunks = []
        async for chunk in stream:
            chunks.append(chunk)

        assert not stream.failed
        assert [c.delta for c in chunks] == ["Hel", "lo"]
        assert [c.model for c in chunks] == ["cf-model", "cf-model"]
        assert [c.finish_reason for c in chunks] == [None, None]
        _, payload = fake.posts[0]
        assert payload["stream"] is True

    @pytest.mark.asyncio
    async def test_health_check_healthy_and_unhealthy(self) -> None:
        fake = _FakeCFHTTP()
        fake.get_result = HttpResponse(status=200, json={"models": []})
        client = _cf_client(fake)
        health = await client.health_check()
        assert health.status is HealthStatus.HEALTHY
        assert health.component == "cloudflare"
        assert fake.get_urls == [
            "/client/v4/accounts/acct-123/ai/models/search?per_page=1"
        ]

        fake.get_error = ConnectionError("boom")
        health = await client.health_check()
        assert health.status is HealthStatus.UNHEALTHY
        assert "ConnectionError" in health.error
        assert "boom" not in health.error

    @pytest.mark.asyncio
    async def test_close_releases_the_transport(self) -> None:
        fake = _FakeCFHTTP()
        client = _cf_client(fake)
        await client.close()
        assert fake.closed is True


class TestCloudflareMessageConversion:
    """Unit coverage for the message/tool-call conversion helpers."""

    def test_convert_messages_supports_dict_and_chatmessage_forms(self) -> None:
        from quadkit.ai.llm.clients import cloudflare_workers as cf_mod

        assistant_tc = ChatMessage(
            role=Role.ASSISTANT,
            content=None,
            tool_calls=[
                ToolCall(
                    id="c1",
                    type="function",
                    function=FunctionCall(name="f", arguments={"a": 1}),
                )
            ],
        )
        tool_msg = ChatMessage(role=Role.TOOL, content="result", tool_call_id="call_9")
        converted = cf_mod._convert_messages_for_cloudflare(
            [
                {"role": "system", "content": "sys"},
                {"content": "bare-dict"},
                _user("hi"),
                assistant_tc,
                tool_msg,
            ]
        )
        assert converted == [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "bare-dict"},
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "f", "arguments": '{"a":1}'},
                    }
                ],
            },
            {"role": "tool", "content": "result", "tool_call_id": "call_9"},
        ]

    def test_convert_messages_keeps_plain_assistant_content(self) -> None:
        from quadkit.ai.llm.clients import cloudflare_workers as cf_mod

        assistant = ChatMessage(role=Role.ASSISTANT, content="plain")
        converted = cf_mod._convert_messages_for_cloudflare([assistant])
        assert converted == [{"role": "assistant", "content": "plain"}]

    @pytest.mark.asyncio
    async def test_parse_sse_body_ignores_non_data_and_bad_lines(self) -> None:
        from quadkit.ai.llm.clients import cloudflare_workers as cf_mod

        body = 'event: x\nid: 1\ndata: {"response": "a"}\n\ndata: [DONE]\ndata: bad\n'
        chunks = [
            chunk async for chunk in cf_mod._parse_cf_sse_body(body, "m")
        ]
        assert [c.delta for c in chunks] == ["a"]
        assert [c.index for c in chunks] == [0]
