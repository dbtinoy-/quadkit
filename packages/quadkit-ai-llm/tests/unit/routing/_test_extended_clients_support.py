"""Shared fixtures/stubs for test_extended_clients tests."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from quadkit.ai.llm.config import ClientConfig
from quadkit.contracts.web.http_models import HttpStatusError
from quadkit.validation import SecretStr


def _make_http_error(status: int) -> HttpStatusError:
    mock_response = MagicMock()
    mock_response.url = "https://example.com/fake"
    mock_response.method = "POST"
    return HttpStatusError(f"HTTP {status}", status=status, response=mock_response)


def _mock_http_response(data: dict) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    type(resp).json = property(lambda _self: data)
    resp.text = ""
    return resp


def _fake_openai_module(completion_text: str = "hello") -> SimpleNamespace:
    """Build a fake ``openai`` module for monkeypatching sys.modules."""

    class FakeChoiceMsg:
        def __init__(self) -> None:
            self.content = completion_text
            self.tool_calls = None

    class FakeUsage:
        prompt_tokens = 3
        completion_tokens = 5
        total_tokens = 8

    class FakeChoice:
        def __init__(self) -> None:
            self.message = FakeChoiceMsg()
            self.finish_reason = "stop"

    class FakeCompletion:
        def __init__(self) -> None:
            self.choices = [FakeChoice()]
            self.model = "fake-model"
            self.usage = FakeUsage()
            self.id = "cmpl-fake"
            self.created = 1
            self.system_fingerprint = None

    async def _create(**_kwargs: Any) -> FakeCompletion:
        return FakeCompletion()

    completions = SimpleNamespace(create=_create)
    chat = SimpleNamespace(completions=completions)

    class FakeModelsData:
        id = "test-model"

    class FakeModels:
        data = [FakeModelsData()]

        async def list(self) -> FakeModels:
            return self

    class AsyncOpenAI:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.chat = chat
            self.models = FakeModels()

        async def close(self) -> None:
            pass

    class AsyncAzureOpenAI(AsyncOpenAI):
        pass

    return SimpleNamespace(
        AsyncOpenAI=AsyncOpenAI,
        AsyncAzureOpenAI=AsyncAzureOpenAI,
    )


# ──────────────────────────────────────────────────────────────────────────────
# AzureOpenAIClient
# ──────────────────────────────────────────────────────────────────────────────


def _azure_config(**kwargs: Any) -> ClientConfig:
    return ClientConfig(
        provider="azure-openai",
        model="gpt-4o",
        api_key=SecretStr("azure-key"),
        extra={
            "azure_resource": "my-resource",
            "azure_deployment": "gpt-4o-deploy",
        },
        **kwargs,
    )


def _bedrock_config(**kwargs: Any) -> ClientConfig:
    return ClientConfig(
        provider="aws-bedrock",
        model="anthropic.claude-3-sonnet-20240229-v1:0",
        extra={
            "aws_region": "us-east-1",
            "aws_access_key_id": "unit-test-access-key",
            "aws_secret_access_key": "wJalrXUtnFEMI",
        },
        **kwargs,
    )


def _bedrock_converse_response(text: str = "Hello from Bedrock") -> dict:
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": text}],
            }
        },
        "usage": {"inputTokens": 5, "outputTokens": 10, "totalTokens": 15},
        "stopReason": "end_turn",
    }


def _bedrock_stream_response(text: str = "streamed") -> dict:
    return {
        "stream": iter(
            [
                {
                    "contentBlockDelta": {
                        "delta": {"text": text},
                        "contentBlockIndex": 0,
                    }
                },
                {"messageStop": {"stopReason": "end_turn"}},
            ]
        )
    }


def _inject_boto3(monkeypatch: Any, mock_bedrock: MagicMock | None = None) -> MagicMock:
    """Inject a fake boto3 into sys.modules; return the configured fake module."""
    fake_boto3 = MagicMock()
    if mock_bedrock is not None:
        fake_boto3.client.return_value = mock_bedrock
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    return fake_boto3


def _vertex_config(**kwargs: Any) -> ClientConfig:
    return ClientConfig(
        provider="google-vertex",
        model="gemini-1.5-pro",
        extra={
            "vertex_project": "my-gcp-project",
            "vertex_location": "us-central1",
        },
        **kwargs,
    )


def _gemini_api_response(text: str = "Hello from Vertex") -> dict:
    return {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": text}],
                    "role": "model",
                }
            }
        ],
        "usageMetadata": {"promptTokenCount": 4, "candidatesTokenCount": 8},
    }


def _inject_google_auth(monkeypatch: Any) -> None:
    """Inject fake google.auth modules so VertexAIClient.__init__ passes the ImportError guard."""
    fake_google = MagicMock()
    fake_google_auth = MagicMock()
    fake_google_auth_transport = MagicMock()
    fake_google_auth_transport_requests = MagicMock()
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.auth", fake_google_auth)
    monkeypatch.setitem(
        sys.modules, "google.auth.transport", fake_google_auth_transport
    )
    monkeypatch.setitem(
        sys.modules,
        "google.auth.transport.requests",
        fake_google_auth_transport_requests,
    )


def _compat_config(
    provider: str = "custom", model: str = "deepseek-chat"
) -> ClientConfig:
    return ClientConfig(
        provider=provider,
        model=model,
        api_key=SecretStr("sk-fake"),
    )
