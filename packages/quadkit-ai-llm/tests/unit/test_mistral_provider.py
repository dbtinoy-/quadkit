"""Tests for Mistral provider."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.clients.mistral import MistralClient


@pytest.mark.asyncio
async def test_complete_and_streaming():
    client = MistralClient(ClientConfig(api_key="x"))

    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json = {
        "choices": [{"message": {"content": "ok", "role": "assistant"}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
    }

    fake_client = MagicMock()
    fake_client.post = AsyncMock(return_value=fake_resp)

    # patch _get_client
    client._client = fake_client

    res = await client.complete(model="m", messages=[{"role": "user", "content": "hi"}])
    assert res.is_ok()
    assert res.unwrap().content == "ok"

    # streaming: provide response with aiter_lines
    class Ctx:
        async def __aenter__(self):
            class Inner:
                def __init__(self):
                    self._it = iter(
                        [
                            'data: {"choices": [{"delta": {"content": "he"}}], "model": "m"}\n',
                            "data: [DONE]\n",
                        ],
                    )

                def raise_for_status(self):
                    return None

                async def aiter_lines(self):
                    for l in self._it:
                        yield l

            return Inner()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    fake_client.stream = MagicMock(return_value=Ctx())

    stream = client.stream_chat(model="m", messages=[])
    chunks = []
    async for c in stream:
        chunks.append(c.delta)

    assert "he" in chunks[0]
