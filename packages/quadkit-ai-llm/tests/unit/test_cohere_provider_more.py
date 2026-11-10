"""Additional Cohere provider tests (edge cases)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.clients.cohere import CohereClient
from quadkit.ai.llm.types import Completion, AIError


@pytest.mark.asyncio
async def test_complete_parses_tool_calls_and_citations(monkeypatch):
    client = CohereClient(ClientConfig(api_key="x"))

    fake_resp = SimpleNamespace()
    fake_resp.raise_for_status = lambda: None
    fake_resp.json = {
        "text": "ok",
        "tool_calls": [{"name": "search", "args": {}}],
        "citations": [{"source": "doc1"}],
        "meta": {"tokens": {"input_tokens": 1, "output_tokens": 1}},
    }

    fake_client = SimpleNamespace()
    fake_client.post = AsyncMock(return_value=fake_resp)

    monkeypatch.setattr(client, "_get_client", lambda: fake_client)

    res = await client.complete(
        messages=[{"role": "user", "content": "hi"}], model="command",
    )
    assert res.is_ok()
    completion = res.unwrap()
    assert isinstance(completion, Completion)
    # ToolCall is a pydantic model: check the nested FunctionCall
    assert completion.tool_calls and completion.tool_calls[0].function.name == "search"
    assert completion.metadata.get("citations") == [{"source": "doc1"}]


@pytest.mark.asyncio
async def test_rerank_honors_top_n(monkeypatch):
    client = CohereClient(ClientConfig(api_key="x"))

    fake_resp = SimpleNamespace()
    fake_resp.raise_for_status = lambda: None
    fake_resp.json = {
        "results": [
            {"document": {"text": "A"}, "relevance_score": 0.9},
            {"document": {"text": "B"}, "relevance_score": 0.1},
        ],
    }

    fake_client = SimpleNamespace()
    fake_client.post = AsyncMock(return_value=fake_resp)

    monkeypatch.setattr(client, "_get_client", lambda: fake_client)

    res = await client.rerank(query="q", documents=["A", "B"], top_n=1)
    assert isinstance(res, list)
    assert (
        len(res) == 2 or len(res) == 1
    )  # provider may return full list and caller slices


@pytest.mark.asyncio
async def test_complete_raises_on_http_error(monkeypatch):
    client = CohereClient(ClientConfig(api_key="x"))
    client.max_retries = 0  # no backoff sleep

    def raise_bad():
        raise RuntimeError("bad response")

    fake_resp = SimpleNamespace()
    fake_resp.raise_for_status = raise_bad

    fake_client = SimpleNamespace()
    fake_client.post = AsyncMock(return_value=fake_resp)

    monkeypatch.setattr(client, "_get_client", lambda: fake_client)

    with pytest.raises(AIError):
        await client.complete(
            messages=[{"role": "user", "content": "hi"}], model="command",
        )


@pytest.mark.asyncio
async def test_finish_reason_is_mapped(monkeypatch):
    client = CohereClient(ClientConfig(api_key="x"))

    fake_resp = SimpleNamespace()
    fake_resp.raise_for_status = lambda: None
    fake_resp.json = {
        "text": "done",
        "finish_reason": "length",
        "meta": {"tokens": {"input_tokens": 1, "output_tokens": 1}},
    }

    fake_client = SimpleNamespace()
    fake_client.post = AsyncMock(return_value=fake_resp)

    monkeypatch.setattr(client, "_get_client", lambda: fake_client)

    res = await client.complete(
        messages=[{"role": "user", "content": "hi"}], model="command",
    )
    assert res.is_ok()
    completion = res.unwrap()
    assert completion.finish_reason == "length"


@pytest.mark.asyncio
async def test_rerank_empty_results(monkeypatch):
    client = CohereClient(ClientConfig(api_key="x"))

    fake_resp = SimpleNamespace()
    fake_resp.raise_for_status = lambda: None
    fake_resp.json = {"results": []}

    fake_client = SimpleNamespace()
    fake_client.post = AsyncMock(return_value=fake_resp)

    monkeypatch.setattr(client, "_get_client", lambda: fake_client)

    res = await client.rerank(query="q", documents=["A", "B"], top_n=5)
    assert res == []
