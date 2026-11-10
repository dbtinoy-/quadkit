"""Scenario tests for the OpenAI-compatible family clients and Gemini helpers.

Covers the public entry points of ``GroqClient``, ``MistralClient``, and
``CohereClient`` (all HTTP-backed, mocked with a fake
``ResilientHTTPClient`` stand-in) plus the pure conversion helpers shared by
the Gemini and Vertex AI clients in ``gemini_helpers``.

Key regression coverage:

* ``HttpResponse.json`` is a *data field* on the framework response object —
  a successful non-streaming response must parse without error (BUG #47).
* Assistant tool-call turns with ``content=None`` must round-trip through
  the shared OpenAI message serializer (BUG #46).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, Self

import aiohttp
import pytest
import yarl

from quadkit.ai.llm.clients.cohere import CohereClient
from quadkit.ai.llm.clients.gemini_helpers import (
    inject_thinking_config,
    messages_to_gemini,
    parse_gemini_response,
    parse_gemini_response_with_tools,
    parse_gemini_sse_body,
    tool_to_gemini_function,
)
from quadkit.ai.llm.clients.groq import GroqClient
from quadkit.ai.llm.clients.mistral import MistralClient
from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.exceptions import (
    LLMAuthenticationError,
    LLMModelNotFoundError,
    LLMQuotaExceededError,
    LLMRateLimitError,
)
from quadkit.ai.llm.types import AIError, ChatMessage
from quadkit.contracts.ai.agents.types import ToolDefinition
from quadkit.contracts.ai.llm import FunctionCall, Role, ToolCall
from quadkit.contracts.core.health import HealthStatus
from quadkit.contracts.web.http_models import HttpResponse, HttpStatusError

# ── Fakes ───────────────────────────────────────────────────────────────


class _FakeStreamCtx:
    """Line-oriented streaming response context."""

    def __init__(self, lines: list[str]) -> None:
        self.lines = lines
        self.status = 200

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise HttpStatusError(
                f"HTTP {self.status}", status=self.status,
                response=HttpResponse(status=self.status),
            )

    async def aiter_lines(self) -> Any:
        for line in self.lines:
            yield line

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _FakeCompatHTTP:
    """Stand-in for ``ResilientHTTPClient`` used by groq/mistral/cohere."""

    def __init__(self) -> None:
        self.post_result: Any = None
        self.get_result: Any = None
        self.post_error: Exception | None = None
        self.get_error: Exception | None = None
        self.posts: list[tuple[str, dict[str, Any] | None]] = []
        self.get_urls: list[str] = []
        self.stream_lines: list[str] = []
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

    @asynccontextmanager
    async def stream(self, method: str, url: str, **kwargs: Any) -> Any:
        # Mirrors ResilientHTTPClient.stream: an async context manager that
        # yields a line-oriented response context (BUG #48 regression guard).
        yield _FakeStreamCtx(self.stream_lines)

    async def close(self) -> None:
        self.closed = True


def _wire(client: Any, fake: _FakeCompatHTTP) -> None:
    object.__setattr__(client, "_client", fake)


def _user(msg: str = "Hello") -> ChatMessage:
    return ChatMessage(role=Role.USER, content=msg)


def _aiohttp_error(status: int, message: str) -> aiohttp.ClientResponseError:
    url = yarl.URL("https://api.example.com/v1")
    info = aiohttp.RequestInfo(url=url, method="POST", headers={}, real_url=url)
    return aiohttp.ClientResponseError(info, (), status=status, message=message)


def _openai_payload(content: str = "ok", tool_calls: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return {
        "choices": [{"message": message, "finish_reason": "stop"}],
        "model": "echo-model",
        "usage": {
            "prompt_tokens": 4,
            "completion_tokens": 6,
            "total_tokens": 10,
        },
    }


# ── Groq ────────────────────────────────────────────────────────────────


class TestGroqClientScenarios:
    @pytest.mark.asyncio
    async def test_complete_success_parses_openai_shaped_response(self) -> None:
        fake = _FakeCompatHTTP()
        fake.post_result = HttpResponse(status=200, json=_openai_payload("hi from groq"))
        client = GroqClient(config=ClientConfig(provider="groq", model="llama-3.1-8b-instant"))
        _wire(client, fake)
        result = await client.complete([_user()])

        assert result.is_ok()
        completion = result.unwrap()
        assert completion.content == "hi from groq"
        assert completion.model == "llama-3.1-8b-instant"
        assert completion.usage is not None
        assert (completion.usage.prompt_tokens, completion.usage.completion_tokens) == (4, 6)

        url, payload = fake.posts[0]
        assert url == "/chat/completions"
        assert payload["stream"] is False
        assert payload["messages"] == [{"role": "user", "content": "Hello"}]

    @pytest.mark.asyncio
    async def test_complete_assistant_tool_call_turn_round_trips(self) -> None:
        # Regression (BUG #46): content=None assistant tool-call turns must
        # serialize without crashing.
        fake = _FakeCompatHTTP()
        fake.post_result = HttpResponse(status=200, json=_openai_payload("ok"))
        client = GroqClient(config=ClientConfig(provider="groq", model="llama-3.1-8b-instant"))
        _wire(client, fake)
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
        tool_result = ChatMessage(role=Role.TOOL, content="42", tool_call_id="c1")
        result = await client.complete([_user(), assistant_tc, tool_result])

        assert result.is_ok()
        _, payload = fake.posts[0]
        assert payload["messages"][1]["content"] is None
        assert payload["messages"][1]["tool_calls"][0]["function"]["name"] == "f"
        assert payload["messages"][2]["tool_call_id"] == "c1"

    @pytest.mark.asyncio
    async def test_complete_parses_tool_calls(self) -> None:
        fake = _FakeCompatHTTP()
        fake.post_result = HttpResponse(
            status=200,
            json=_openai_payload(
                None,
                tool_calls=[
                    {"id": "call_9", "type": "function",
                     "function": {"name": "get_weather", "arguments": '{"city": "MNL"}'}}
                ],
            ),
        )
        client = GroqClient(config=ClientConfig(provider="groq", model="llama-3.1-8b-instant"))
        _wire(client, fake)
        result = await client.complete([_user()])

        completion = result.unwrap()
        # OpenAI tool-call responses carry content=None; the template's
        # thinking normalizer must pass such completions through (BUG #45).
        assert completion.content is None
        assert completion.tool_calls is not None
        assert completion.tool_calls[0].id == "call_9"
        assert completion.tool_calls[0].function is not None
        assert completion.tool_calls[0].function.name == "get_weather"

    @pytest.mark.asyncio
    async def test_chat_forwards_tools(self) -> None:
        fake = _FakeCompatHTTP()
        fake.post_result = HttpResponse(status=200, json=_openai_payload("ok"))
        client = GroqClient(config=ClientConfig(provider="groq", model="llama-3.1-8b-instant"))
        _wire(client, fake)
        tools = [ToolDefinition(name="fn", description="d", parameters={})]
        result = await client.chat([_user()], tools=tools)
        assert result.is_ok()
        _, payload = fake.posts[0]
        assert payload["tools"] == [
            {"type": "function", "function": {"name": "fn", "description": "d", "parameters": {}}}
        ]

    @pytest.mark.asyncio
    async def test_stream_yields_sse_deltas(self) -> None:
        fake = _FakeCompatHTTP()
        fake.stream_lines = [
            'data: {"choices":[{"delta":{"content":"Hel"},"finish_reason":null}],"model":"g"}',
            'data: {"choices":[{"delta":{"content":"lo"},"finish_reason":"stop"}],"model":"g"}',
            "data: [DONE]",
            "",
        ]
        client = GroqClient(config=ClientConfig(provider="groq", model="llama-3.1-8b-instant"))
        _wire(client, fake)
        stream = client.stream_chat([_user()])
        chunks = [c async for c in stream]

        assert not stream.failed
        assert [c.delta for c in chunks] == ["Hel", "lo"]
        assert chunks[-1].finish_reason == "stop"
        assert chunks[0].model == "g"

    @pytest.mark.asyncio
    async def test_error_matrix(self) -> None:
        cases = [
            (_aiohttp_error(401, "Invalid API Key"), LLMAuthenticationError, "raise"),
            (_aiohttp_error(429, "rate limit"), LLMRateLimitError, "err"),
            (_aiohttp_error(402, "payment required"), LLMQuotaExceededError, "err"),
            (_aiohttp_error(404, "no such model"), LLMModelNotFoundError, "err"),
        ]
        for error, expected, mode in cases:  # noqa: B007
            fake = _FakeCompatHTTP()
            fake.post_error = error
            client = GroqClient(config=ClientConfig(provider="groq", model="m"))
            _wire(client, fake)
            if mode == "raise":
                with pytest.raises(expected):
                    await client.complete([_user()])
            else:
                result = await client.complete([_user()])
                assert result.is_err()
                assert isinstance(result.unwrap_err(), expected)

    @pytest.mark.asyncio
    async def test_http_500_becomes_sanitized_ai_error(self) -> None:
        secret = "GROQ_UPSTREAM_SECRET_SENTINEL"
        fake = _FakeCompatHTTP()
        fake.post_error = HttpStatusError(
            f"invalid {secret} (HTTP 500)",
            status=500,
            response=HttpResponse(status=500),
        )
        client = GroqClient(config=ClientConfig(provider="groq", model="m"))
        _wire(client, fake)
        with pytest.raises(AIError) as exc:
            await client.complete([_user()])
        assert secret not in str(exc.value)
        assert secret not in repr(exc.value.to_dict())

    @pytest.mark.asyncio
    async def test_health_check_healthy_and_unhealthy(self) -> None:
        fake = _FakeCompatHTTP()
        fake.get_result = HttpResponse(status=200, json={"data": [{"id": "m1"}]})
        client = GroqClient(config=ClientConfig(provider="groq", model="m"))
        _wire(client, fake)
        health = await client.health_check()
        assert health.status is HealthStatus.HEALTHY
        assert health.component == "llm.groq"

        models = await client.list_models()
        assert models == [{"id": "m1"}]

        fake.get_error = ConnectionError("down")
        health = await client.health_check()
        assert health.status is HealthStatus.UNHEALTHY
        assert "ConnectionError" in health.error
        assert "down" not in health.error

    @pytest.mark.asyncio
    async def test_close_releases_transport(self) -> None:
        fake = _FakeCompatHTTP()
        client = GroqClient(config=ClientConfig(provider="groq", model="m"))
        _wire(client, fake)
        await client.close()
        assert fake.closed is True


# ── Mistral ─────────────────────────────────────────────────────────────


class TestMistralClientScenarios:
    @pytest.mark.asyncio
    async def test_complete_success(self) -> None:
        fake = _FakeCompatHTTP()
        fake.post_result = HttpResponse(status=200, json=_openai_payload("hi mistral"))
        client = MistralClient(config=ClientConfig(provider="mistral", model="mistral-small"))
        _wire(client, fake)
        result = await client.complete([_user()])

        assert result.is_ok()
        completion = result.unwrap()
        assert completion.content == "hi mistral"
        assert completion.usage is not None
        assert completion.usage.total_tokens == 10
        assert fake.posts[0][0] == "/chat/completions"

    @pytest.mark.asyncio
    async def test_complete_with_tools_and_response_format(self) -> None:
        fake = _FakeCompatHTTP()
        fake.post_result = HttpResponse(status=200, json=_openai_payload("ok"))
        client = MistralClient(config=ClientConfig(provider="mistral", model="mistral-small"))
        _wire(client, fake)
        tools = [ToolDefinition(name="fn", description="d", parameters={})]
        await client.complete([_user()], tools=tools, response_format={"type": "json_object"})
        _, payload = fake.posts[0]
        assert "tools" in payload
        assert payload["response_format"] == {"type": "json_object"}

    @pytest.mark.asyncio
    async def test_error_matrix(self) -> None:
        cases = [
            (_aiohttp_error(401, "bad key"), LLMAuthenticationError, "raise"),
            (_aiohttp_error(429, "slow down"), LLMRateLimitError, "err"),
            (_aiohttp_error(402, "quota"), LLMQuotaExceededError, "err"),
            (_aiohttp_error(404, "missing model"), LLMModelNotFoundError, "err"),
        ]
        for error, expected, mode in cases:  # noqa: B007
            fake = _FakeCompatHTTP()
            fake.post_error = error
            client = MistralClient(config=ClientConfig(provider="mistral", model="m"))
            _wire(client, fake)
            if mode == "raise":
                with pytest.raises(expected):
                    await client.complete([_user()])
            else:
                result = await client.complete([_user()])
                assert result.is_err()
                assert isinstance(result.unwrap_err(), expected)

    @pytest.mark.asyncio
    async def test_stream_yields_deltas_and_finish(self) -> None:
        fake = _FakeCompatHTTP()
        fake.stream_lines = [
            'data: {"choices":[{"delta":{"content":"A"},"finish_reason":null}],"model":"m"}',
            'data: {"choices":[{"delta":{"content":"B"},"finish_reason":"stop"}],"model":"m"}',
            "data: [DONE]",
        ]
        client = MistralClient(config=ClientConfig(provider="mistral", model="m"))
        _wire(client, fake)
        stream = client.stream_chat([_user()])
        chunks = [c async for c in stream]
        assert [c.delta for c in chunks] == ["A", "B"]
        assert chunks[-1].finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        fake = _FakeCompatHTTP()
        fake.get_result = HttpResponse(status=200, json={})
        client = MistralClient(config=ClientConfig(provider="mistral", model="m"))
        _wire(client, fake)
        health = await client.health_check()
        assert health.status is HealthStatus.HEALTHY
        assert health.component == "llm.mistral"

        fake.get_error = ConnectionError("nope")
        health = await client.health_check()
        assert health.status is HealthStatus.UNHEALTHY
        assert "ConnectionError" in health.error
        assert "nope" not in health.error


# ── Cohere ──────────────────────────────────────────────────────────────


class TestCohereClientScenarios:
    @pytest.mark.asyncio
    async def test_complete_success_parses_cohere_shape(self) -> None:
        fake = _FakeCompatHTTP()
        fake.post_result = HttpResponse(
            status=200,
            json={
                "text": "hi cohere",
                "finish_reason": "COMPLETE",
                "meta": {
                    "tokens": {"input_tokens": 5, "output_tokens": 3}
                },
                "citations": [{"start": 0, "end": 3, "text": "hi "}],
            },
        )
        client = CohereClient(config=ClientConfig(provider="cohere", model="command-r"))
        _wire(client, fake)
        result = await client.complete([_user()])

        assert result.is_ok()
        completion = result.unwrap()
        assert completion.content == "hi cohere"
        assert completion.finish_reason == "COMPLETE"
        assert completion.usage is not None
        assert (completion.usage.prompt_tokens, completion.usage.completion_tokens) == (5, 3)
        assert completion.metadata == {
            "citations": [{"start": 0, "end": 3, "text": "hi "}]
        }
        assert fake.posts[0][0] == "/chat"

    @pytest.mark.asyncio
    async def test_complete_parses_cohere_tool_calls(self) -> None:
        fake = _FakeCompatHTTP()
        fake.post_result = HttpResponse(
            status=200,
            json={
                "text": "",
                "tool_calls": [
                    {"id": "tc1", "name": "fn", "args": {"a": 1}},
                    {"name": "fn2", "arguments": {"b": 2}},
                ],
            },
        )
        client = CohereClient(config=ClientConfig(provider="cohere", model="command-r"))
        _wire(client, fake)
        result = await client.complete([_user()])

        completion = result.unwrap()
        assert completion.tool_calls is not None
        assert len(completion.tool_calls) == 2
        assert completion.tool_calls[0].id == "tc1"
        assert completion.tool_calls[0].function is not None
        assert completion.tool_calls[0].function.arguments == {"a": 1}
        # id falls back to the function name.
        assert completion.tool_calls[1].id == "fn2"

    @pytest.mark.asyncio
    async def test_error_matrix(self) -> None:
        cases = [
            (_aiohttp_error(401, "invalid token"), LLMAuthenticationError, "raise"),
            (_aiohttp_error(429, "throttled"), LLMRateLimitError, "err"),
            (_aiohttp_error(402, "paid"), LLMQuotaExceededError, "err"),
            (_aiohttp_error(404, "absent"), LLMModelNotFoundError, "err"),
        ]
        for error, expected, mode in cases:  # noqa: B007
            fake = _FakeCompatHTTP()
            fake.post_error = error
            client = CohereClient(config=ClientConfig(provider="cohere", model="m"))
            _wire(client, fake)
            if mode == "raise":
                with pytest.raises(expected):
                    await client.complete([_user()])
            else:
                result = await client.complete([_user()])
                assert result.is_err()
                assert isinstance(result.unwrap_err(), expected)

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        fake = _FakeCompatHTTP()
        fake.get_result = HttpResponse(status=200, json={})
        client = CohereClient(config=ClientConfig(provider="cohere", model="m"))
        _wire(client, fake)
        health = await client.health_check()
        assert health.status is HealthStatus.HEALTHY
        assert health.component == "cohere"

        fake.get_error = ConnectionError("offline")
        health = await client.health_check()
        assert health.status is HealthStatus.UNHEALTHY
        assert "ConnectionError" in health.error
        assert "offline" not in health.error


# ── Gemini helpers ──────────────────────────────────────────────────────


class TestGeminiHelpers:
    def test_messages_to_gemini_prepends_system_and_round_trips_tools(self) -> None:
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
        tool_result = ChatMessage(role=Role.TOOL, content="42", tool_call_id="c1")
        contents = messages_to_gemini(
            [
                {"role": "system", "content": "be brief"},
                _user("hi"),
                assistant_tc,
                tool_result,
            ]
        )

        # system text is prepended to the first user turn.
        assert contents[0] == {
            "role": "user",
            "parts": [{"text": "be brief"}, {"text": "hi"}],
        }
        # assistant tool-call turn.
        assert contents[1] == {
            "role": "model",
            "parts": [{"functionCall": {"name": "f", "args": {"a": 1}}}],
        }
        # tool result as functionResponse.
        assert contents[2] == {
            "role": "user",
            "parts": [
                {"functionResponse": {"name": "c1", "response": {"content": "42"}}}
            ],
        }

    def test_messages_to_gemini_drops_orphan_system(self) -> None:
        contents = messages_to_gemini(
            [{"role": "system", "content": "sys"}, {"role": "assistant", "content": "a"}]
        )
        # System text has no following user turn → dropped, only model turn.
        assert contents == [{"role": "model", "parts": [{"text": "a"}]}]

    def test_parse_gemini_response_splits_thought_parts(self) -> None:
        data = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "thinking...", "thought": True},
                            {"text": "answer"},
                        ]
                    }
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 8,
                "candidatesTokenCount": 2,
                "totalTokenCount": 10,
                "thoughtsTokenCount": 5,
            },
        }
        completion = parse_gemini_response(data, "gemini-2.5")
        assert completion.content == "answer"
        assert completion.thinking is not None
        assert completion.thinking.content == "thinking..."
        assert completion.thinking.tokens == 5
        assert completion.usage is not None
        assert (completion.usage.prompt_tokens, completion.usage.completion_tokens) == (8, 2)

    def test_parse_gemini_response_no_candidates_hides_provider_detail(self) -> None:
        private_reason = "/srv/private/prompts/tenant-17.txt"
        with pytest.raises(AIError, match="Gemini returned no candidates") as exc_info:
            parse_gemini_response(
                {"promptFeedback": {"blockReason": private_reason}}, "gemini"
            )

        assert private_reason not in str(exc_info.value)

    def test_parse_gemini_response_with_tools(self) -> None:
        data = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "calling "},
                            {"functionCall": {"name": "get_time", "args": {"tz": "PHT"}}},
                        ]
                    }
                }
            ]
        }
        completion = parse_gemini_response_with_tools(data, "gemini")
        assert completion.content == "calling "
        assert completion.tool_calls is not None
        assert completion.tool_calls[0].id == "get_time"
        assert completion.tool_calls[0].function is not None
        assert completion.tool_calls[0].function.arguments == '{"tz":"PHT"}'

    def test_parse_gemini_sse_body(self) -> None:
        body = (
            'data: {"candidates":[{"content":{"parts":[{"text":"H"}]}}]}\n'
            "\n"
            'data: {"candidates":[{"content":{"parts":[{"text":"t","thought":true}]}}]}\n'
            "data: [DONE]\n"
            "data: garbage\n"
        )
        chunks = list(parse_gemini_sse_body(body, "gemini"))
        assert len(chunks) == 2
        assert chunks[0].delta == "H"
        assert chunks[1].thinking_delta == "t"
        assert chunks[1].is_thinking is True

    def test_tool_to_gemini_function_variants(self) -> None:
        class _SchemaTool:
            __tool_schema__ = {
                "name": "schema_fn",
                "description": "from schema",
                "parameters": {"type": "object"},
            }

        assert tool_to_gemini_function(_SchemaTool) == {
            "name": "schema_fn",
            "description": "from schema",
            "parameters": {"type": "object"},
        }
        assert tool_to_gemini_function(
            {"function": {"name": "dict_fn", "description": "d", "parameters": {}}}
        ) == {"name": "dict_fn", "description": "d", "parameters": {}}
        assert tool_to_gemini_function(SimpleNamespace(name="attr_fn", description=None)) == {
            "name": "attr_fn",
            "description": "",
            "parameters": {},
        }

    def test_inject_thinking_config_matrix(self) -> None:
        from quadkit.contracts.ai.thinking import ThinkingConfig

        config = ClientConfig()
        gen: dict[str, Any] = {}
        inject_thinking_config(gen, config)
        assert gen == {}  # no thinking config → no-op

        gen = {}
        inject_thinking_config(gen, ClientConfig(thinking=ThinkingConfig(suppress=True)))
        assert gen == {"thinkingConfig": {"thinkingBudget": 0}}

        gen = {}
        inject_thinking_config(
            gen, ClientConfig(thinking=ThinkingConfig(level="low"))
        )
        assert gen == {"thinkingConfig": {"thinkingLevel": "low"}}

        gen = {}
        inject_thinking_config(
            gen, ClientConfig(thinking=ThinkingConfig(budget_tokens=128))
        )
        assert gen == {"thinkingConfig": {"thinkingBudget": 128}}


# keep SimpleNamespace import used even if a branch changes
_ = SimpleNamespace
