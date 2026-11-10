from __future__ import annotations

import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.exceptions import (
    LLMAuthenticationError,
    LLMModelNotFoundError,
    LLMRateLimitError,
)
from quadkit.ai.llm.types import ChatMessage, Role
from quadkit.contracts.core import HealthStatus
from quadkit.validation import SecretStr

from ._test_extended_clients_support import (  # noqa: TID252
    _azure_config,
    _bedrock_config,
    _bedrock_converse_response,
    _bedrock_stream_response,
    _fake_openai_module,
    _inject_boto3,
)


class TestAzureOpenAIClient:
    def test_missing_azure_resource_raises_value_error(self, monkeypatch: Any) -> None:
        monkeypatch.setitem(sys.modules, "openai", _fake_openai_module())
        from quadkit.ai.llm.clients.azure_openai import AzureOpenAIClient

        with pytest.raises(ValueError, match="azure_resource"):
            AzureOpenAIClient(
                ClientConfig(
                    provider="azure-openai",
                    model="gpt-4o",
                    api_key=SecretStr("key"),
                    extra={"azure_deployment": "dep"},
                )
            )

    def test_model_falls_back_to_deployment_in_extra(self, monkeypatch: Any) -> None:
        monkeypatch.setitem(sys.modules, "openai", _fake_openai_module())
        from quadkit.ai.llm.clients.azure_openai import AzureOpenAIClient

        client = AzureOpenAIClient(_azure_config())
        assert client._azure_deployment == "gpt-4o-deploy"

    def test_model_from_config_used_when_deployment_missing(
        self, monkeypatch: Any
    ) -> None:
        monkeypatch.setitem(sys.modules, "openai", _fake_openai_module())
        from quadkit.ai.llm.clients.azure_openai import AzureOpenAIClient

        client = AzureOpenAIClient(
            ClientConfig(
                provider="azure-openai",
                model="gpt-4o",
                api_key=SecretStr("key"),
                extra={"azure_resource": "res"},
            )
        )
        assert client._azure_deployment == "gpt-4o"

    @pytest.mark.asyncio
    async def test_complete_success(self, monkeypatch: Any) -> None:
        monkeypatch.setitem(
            sys.modules, "openai", _fake_openai_module("Azure response")
        )
        from quadkit.ai.llm.clients.azure_openai import AzureOpenAIClient

        client = AzureOpenAIClient(_azure_config())
        res = await client.complete(
            messages=[ChatMessage(role=Role.USER, content="hi")]
        )

        assert res.is_ok()
        assert res.unwrap().content == "Azure response"

    @pytest.mark.asyncio
    async def test_health_check_returns_healthy_on_success(
        self, monkeypatch: Any
    ) -> None:
        monkeypatch.setitem(sys.modules, "openai", _fake_openai_module())
        from quadkit.ai.llm.clients.azure_openai import AzureOpenAIClient

        client = AzureOpenAIClient(_azure_config())
        result = await client.health_check()

        assert result.status == HealthStatus.HEALTHY
        assert "resource" in result.details
        assert result.details["resource"] == "my-resource"

    @pytest.mark.asyncio
    async def test_health_check_returns_unhealthy_on_error(
        self, monkeypatch: Any
    ) -> None:
        monkeypatch.setitem(sys.modules, "openai", _fake_openai_module())
        from quadkit.ai.llm.clients.azure_openai import AzureOpenAIClient

        client = AzureOpenAIClient(_azure_config())
        client.client.models.list = AsyncMock(
            side_effect=Exception("connection refused")
        )

        result = await client.health_check()

        assert result.status == HealthStatus.UNHEALTHY
        assert "Exception" in (result.error or "")
        assert "connection refused" not in (result.error or "")

    @pytest.mark.asyncio
    async def test_context_manager(self, monkeypatch: Any) -> None:
        monkeypatch.setitem(sys.modules, "openai", _fake_openai_module())
        from quadkit.ai.llm.clients.azure_openai import AzureOpenAIClient

        client = AzureOpenAIClient(_azure_config())
        async with client as c:
            assert c is client


# ──────────────────────────────────────────────────────────────────────────────
# BedrockClient
# ──────────────────────────────────────────────────────────────────────────────


class TestBedrockClient:
    def test_missing_aws_region_raises_value_error(self, monkeypatch: Any) -> None:
        _inject_boto3(monkeypatch)
        from quadkit.ai.llm.clients.aws_bedrock import BedrockClient

        with pytest.raises(ValueError, match="aws_region"):
            BedrockClient(
                ClientConfig(
                    provider="aws-bedrock",
                    model="anthropic.claude",
                    extra={},
                )
            )

    @pytest.mark.asyncio
    async def test_complete_success(self, monkeypatch: Any) -> None:
        mock_bedrock = MagicMock()
        mock_bedrock.converse.return_value = _bedrock_converse_response("Bedrock hi")
        _inject_boto3(monkeypatch, mock_bedrock)
        from quadkit.ai.llm.clients.aws_bedrock import BedrockClient

        client = BedrockClient(_bedrock_config())
        res = await client.complete(messages=[{"role": "user", "content": "hi"}])

        assert res.is_ok()
        assert res.unwrap().content == "Bedrock hi"
        assert res.unwrap().usage.prompt_tokens == 5
        assert res.unwrap().usage.completion_tokens == 10

    @pytest.mark.asyncio
    async def test_complete_returns_err_on_throttling(self, monkeypatch: Any) -> None:
        mock_bedrock = MagicMock()

        class _ThrottleError(Exception):
            def __init__(self) -> None:
                super().__init__("ThrottlingException")
                self.response = {"Error": {"Code": "ThrottlingException"}}

        mock_bedrock.converse.side_effect = _ThrottleError()
        _inject_boto3(monkeypatch, mock_bedrock)
        from quadkit.ai.llm.clients.aws_bedrock import BedrockClient

        client = BedrockClient(_bedrock_config())
        client.max_retries = 0
        res = await client.complete(messages=[{"role": "user", "content": "hi"}])

        assert res.is_err()
        assert isinstance(res.unwrap_err(), LLMRateLimitError)

    @pytest.mark.asyncio
    async def test_complete_raises_auth_error_on_access_denied(
        self, monkeypatch: Any
    ) -> None:
        mock_bedrock = MagicMock()

        class _AuthError(Exception):
            def __init__(self) -> None:
                super().__init__("AccessDeniedException")
                self.response = {"Error": {"Code": "AccessDeniedException"}}

        mock_bedrock.converse.side_effect = _AuthError()
        _inject_boto3(monkeypatch, mock_bedrock)
        from quadkit.ai.llm.clients.aws_bedrock import BedrockClient

        client = BedrockClient(_bedrock_config())
        with pytest.raises(LLMAuthenticationError):
            await client.complete(messages=[{"role": "user", "content": "hi"}])

    @pytest.mark.asyncio
    async def test_complete_returns_err_on_model_not_found(
        self, monkeypatch: Any
    ) -> None:
        mock_bedrock = MagicMock()

        class _NotFoundError(Exception):
            def __init__(self) -> None:
                super().__init__("ModelNotFoundException")
                self.response = {"Error": {"Code": "ModelNotFoundException"}}

        mock_bedrock.converse.side_effect = _NotFoundError()
        _inject_boto3(monkeypatch, mock_bedrock)
        from quadkit.ai.llm.clients.aws_bedrock import BedrockClient

        client = BedrockClient(_bedrock_config())
        client.max_retries = 0
        res = await client.complete(messages=[{"role": "user", "content": "hi"}])

        assert res.is_err()
        assert isinstance(res.unwrap_err(), LLMModelNotFoundError)

    @pytest.mark.asyncio
    async def test_stream_chat_yields_chunks(self, monkeypatch: Any) -> None:
        mock_bedrock = MagicMock()
        mock_bedrock.converse_stream.return_value = _bedrock_stream_response(
            "streamed chunk"
        )
        _inject_boto3(monkeypatch, mock_bedrock)
        from quadkit.ai.llm.clients.aws_bedrock import BedrockClient

        client = BedrockClient(_bedrock_config())
        stream = client.stream_chat(messages=[{"role": "user", "content": "hi"}])

        chunks = [c async for c in stream]
        assert any("streamed chunk" in (c.delta or "") for c in chunks)

    @pytest.mark.asyncio
    async def test_tool_call_includes_tool_config(self, monkeypatch: Any) -> None:
        mock_bedrock = MagicMock()
        mock_bedrock.converse.return_value = _bedrock_converse_response("tool result")
        _inject_boto3(monkeypatch, mock_bedrock)
        from quadkit.ai.llm.clients.aws_bedrock import BedrockClient

        client = BedrockClient(_bedrock_config())

        class MyTool:
            __tool_schema__ = {
                "name": "my_tool",
                "description": "A tool",
                "parameters": {
                    "type": "object",
                    "properties": {"input": {"type": "string"}},
                    "required": ["input"],
                },
            }

        res = await client.chat(
            messages=[{"role": "user", "content": "use tool"}],
            tools=[MyTool()],
        )

        assert res.is_ok()
        call_kwargs = mock_bedrock.converse.call_args[1]
        assert "toolConfig" in call_kwargs

    @pytest.mark.asyncio
    async def test_health_check_returns_healthy_on_success(
        self, monkeypatch: Any
    ) -> None:
        mock_bedrock = MagicMock()
        mgmt_mock = MagicMock()
        mgmt_mock.list_foundation_models.return_value = {"modelSummaries": []}
        fake_boto3 = _inject_boto3(monkeypatch, mock_bedrock)
        fake_boto3.client.side_effect = lambda service, **_kw: (
            mgmt_mock if service == "bedrock" else mock_bedrock
        )
        from quadkit.ai.llm.clients.aws_bedrock import BedrockClient

        client = BedrockClient(_bedrock_config())
        result = await client.health_check()

        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_health_check_returns_unhealthy_on_error(
        self, monkeypatch: Any
    ) -> None:
        mock_bedrock = MagicMock()
        mgmt_mock = MagicMock()
        mgmt_mock.list_foundation_models.side_effect = Exception("no connection")
        fake_boto3 = _inject_boto3(monkeypatch, mock_bedrock)
        fake_boto3.client.side_effect = lambda service, **_kw: (
            mgmt_mock if service == "bedrock" else mock_bedrock
        )
        from quadkit.ai.llm.clients.aws_bedrock import BedrockClient

        client = BedrockClient(_bedrock_config())
        result = await client.health_check()

        assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_close_releases_client(self, monkeypatch: Any) -> None:
        mock_bedrock = MagicMock()
        _inject_boto3(monkeypatch, mock_bedrock)
        from quadkit.ai.llm.clients.aws_bedrock import BedrockClient

        client = BedrockClient(_bedrock_config())
        await client.close()

        mock_bedrock.close.assert_called_once()
        assert client._client is None


# ──────────────────────────────────────────────────────────────────────────────
# VertexAIClient
# ──────────────────────────────────────────────────────────────────────────────
