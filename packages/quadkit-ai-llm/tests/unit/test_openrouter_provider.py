"""Unit tests for the OpenRouter provider."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.clients.openrouter import OpenRouterClient
from quadkit.ai.llm.types import AIError, ChatMessage


@pytest.mark.asyncio
async def test_complete_sync_success():
    client = OpenRouterClient(ClientConfig(api_key="x", model="test", api_base="http://example"))

    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.json = {
        "choices": [{"message": {"content": "hi", "role": "assistant"}}],
        "model": "test-model",
    }

    with patch.object(
        client,
        "_get_client",
        AsyncMock(return_value=MagicMock(post=AsyncMock(return_value=fake_response))),
    ):
        res = await client.complete([ChatMessage(role="user", content="hello")])
        assert res.is_ok()
        completion = res.unwrap()
        assert completion.content == "hi"
        assert completion.model == "test-model"


@pytest.mark.asyncio
async def test_embeddings_success():
    client = OpenRouterClient(
        ClientConfig(api_key="x", model="embed-test", api_base="http://example"),
    )

    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.json = {
        "data": [
            {"index": 0, "embedding": [0.1, 0.2]},
            {"index": 1, "embedding": [0.3, 0.4]},
        ],
    }

    with patch.object(
        client,
        "_get_client",
        AsyncMock(return_value=MagicMock(post=AsyncMock(return_value=fake_response))),
    ):
        embs = await client.embeddings(["hello", "world"])
        assert isinstance(embs, list)
        assert embs[0] == [0.1, 0.2]
        assert embs[1] == [0.3, 0.4]


@pytest.mark.asyncio
async def test_complete_parses_tool_calls_and_handles_errors():
    client = OpenRouterClient(ClientConfig(api_key="x", model="test", api_base="http://example"))

    # Tool calls parsing
    fake_resp_tool = MagicMock()
    fake_resp_tool.raise_for_status = MagicMock()
    fake_resp_tool.json = {
        "choices": [
            {
                "message": {
                    "content": "",
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "1",
                            "type": "function",
                            "function": {"name": "f", "arguments": {"x": 1}},
                        },
                    ],
                },
            },
        ],
        "model": "test-model",
    }

    with patch.object(
        client,
        "_get_client",
        AsyncMock(return_value=MagicMock(post=AsyncMock(return_value=fake_resp_tool))),
    ):
        res = await client.complete([ChatMessage(role="user", content="call")])
        assert res.is_ok()
        completion = res.unwrap()
        assert completion.tool_calls is not None
        assert completion.tool_calls[0].id == "1"

    # HTTP error path (error on POST)
    fake_client_err = MagicMock()
    fake_client_err.post = AsyncMock(
        side_effect=aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=500, message="err",
        ),
    )

    with patch.object(client, "_get_client", AsyncMock(return_value=fake_client_err)):
        with pytest.raises(AIError):
            await client.complete([ChatMessage(role="user", content="hello")])


@pytest.mark.asyncio
async def test_embeddings_empty_returns_empty():
    client = OpenRouterClient(
        ClientConfig(api_key="x", model="embed-test", api_base="http://example"),
    )

    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.json = {"data": []}

    with patch.object(
        client,
        "_get_client",
        AsyncMock(return_value=MagicMock(post=AsyncMock(return_value=fake_response))),
    ):
        embs = await client.embeddings([])
        assert embs == []
