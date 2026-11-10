"""Tests that LLM provider startup logs do not expose raw SDK errors."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from structlog.testing import capture_logs

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.di import provider as provider_module
from quadkit.ai.llm.exceptions import LLMError
from quadkit.ai.llm.di.provider import LLMProvider


class _FakeRegistrar:
    def singleton(self, _key: object, _instance: object) -> None:
        pass


@pytest.mark.asyncio
async def test_register_logs_only_exception_type_for_client_creation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_detail = "api_key=sk-provider-private /srv/private/tenant-42/model.json"
    config = ClientConfig(
        provider="openai",
        model="private-model-id",
        api_key="sk-provider-private",
    )
    monkeypatch.setattr(
        provider_module,
        "create_llm_client",
        AsyncMock(side_effect=LLMError(private_detail)),
    )
    provider = LLMProvider(config=config)

    with capture_logs() as logs:
        await provider.register(_FakeRegistrar())

    serialized_logs = repr(logs)
    assert private_detail not in serialized_logs
    assert "sk-provider-private" not in serialized_logs
    assert "/srv/private/tenant-42/model.json" not in serialized_logs
    assert "private-model-id" not in serialized_logs
    assert any(
        log["event"] == "llm_client_skipped" and log["error_type"] == "LLMError"
        for log in logs
    )
