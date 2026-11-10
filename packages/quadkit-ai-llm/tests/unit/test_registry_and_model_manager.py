"""Smoke tests for ProviderRegistry and AbstractModelManager fallbacks."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.llm.model_manager import (
    LMStudioModelManager,
    ModelLoadResult,
    OllamaModelManager,
)


@pytest.mark.asyncio
async def test_registry_list_and_register_unregister(provider_registry):
    reg = provider_registry

    providers = reg.list_providers()
    assert "groq" in providers

    class DummyClient:
        pass

    reg.register(
        name="dummy",
        client_class=DummyClient,
        default_models=["d1"],
        supports_streaming=False,
    )
    assert "dummy" in reg.list_providers()

    info = reg.get_provider("dummy")
    assert info.name == "dummy"
    assert info.default_models == ["d1"]
    assert info.supports_streaming is False

    reg.unregister("dummy")
    assert "dummy" not in reg.list_providers()

    with pytest.raises(KeyError):
        reg.get_provider("nonexistent-provider")


@pytest.mark.asyncio
async def test_ollama_list_and_load_fallback(monkeypatch):
    mm = OllamaModelManager(base_url="http://example")
    mm.client = None  # Ensure we use the fallback path

    # Fake client returned by _get_client
    fake_client = MagicMock()

    fake_tags_resp = MagicMock()
    fake_tags_resp.raise_for_status = MagicMock()
    fake_tags_resp.json = MagicMock(return_value={"models": [{"name": "m1"}]})

    fake_client.get = AsyncMock(return_value=fake_tags_resp)

    async def fake_post(path, json=None):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value={})
        return resp

    fake_client.post = AsyncMock(side_effect=fake_post)

    async def get_client_override():
        return fake_client

    monkeypatch.setattr(mm, "_get_client", get_client_override)

    models = await mm.list_models()
    # Fallback may return an empty list if the API client is unavailable; ensure we get a list
    assert isinstance(models, list)

    # Attempt to load a model not present -> should call pull and generate and return success
    result = await mm.load_model("missing-model")
    assert isinstance(result, ModelLoadResult)
    assert result.success is True


@pytest.mark.asyncio
async def test_model_manager_failures_do_not_expose_provider_exception_text(
    monkeypatch, capsys
):
    secret = "MODEL_MANAGER_SECRET_SENTINEL"

    ollama_manager = OllamaModelManager(base_url="http://example")
    ollama_manager.client = None
    ollama_client = MagicMock()
    ollama_client.post = AsyncMock(side_effect=RuntimeError(secret))

    async def get_ollama_client():
        return ollama_client

    monkeypatch.setattr(ollama_manager, "_get_client", get_ollama_client)
    ollama_result = await ollama_manager.load_model("test-model")
    assert ollama_result.success is False
    assert secret not in (ollama_result.error or "")

    lmstudio_manager = LMStudioModelManager(base_url="http://lmstudio")
    lmstudio_client = MagicMock()
    lmstudio_client.post = AsyncMock(side_effect=RuntimeError(secret))

    async def get_lmstudio_client():
        return lmstudio_client

    monkeypatch.setattr(lmstudio_manager, "_get_client", get_lmstudio_client)
    lmstudio_result = await lmstudio_manager.load_model("test-model")
    assert lmstudio_result.success is False
    assert secret not in (lmstudio_result.error or "")

    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err


@pytest.mark.asyncio
async def test_lmstudio_load_model_fallback(monkeypatch):
    mm = LMStudioModelManager(base_url="http://lmstudio")

    fake_client = MagicMock()

    fake_test_resp = MagicMock()
    fake_test_resp.raise_for_status = MagicMock()
    fake_test_resp.json = MagicMock(return_value={})

    fake_client.post = AsyncMock(return_value=fake_test_resp)

    async def get_client_override():
        return fake_client

    monkeypatch.setattr(mm, "_get_client", get_client_override)

    res = await mm.load_model("model-x")
    assert isinstance(res, ModelLoadResult)
    assert res.success is True
