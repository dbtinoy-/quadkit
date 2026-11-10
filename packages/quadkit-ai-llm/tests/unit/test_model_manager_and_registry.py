import asyncio

import pytest

from quadkit.ai.llm.model_manager import LLMModelManager, OllamaModelManager


class FakeResp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class FakeHTTPClient:
    def __init__(self, response_data):
        self._response_data = response_data

    async def get(self, path):
        return FakeResp(self._response_data)


class FakeClientWithPs:
    def __init__(self, data):
        self._data = data

    def ps(self):
        return self._data


class FakeClientWithAsyncPs:
    def __init__(self, data):
        self._data = data

    async def ps(self):
        await asyncio.sleep(0)
        return self._data


@pytest.mark.asyncio
async def test_ollama_get_loaded_models_client_ps_sync():
    mgr = OllamaModelManager()
    mgr.client = FakeClientWithPs({"models": [{"name": "foo"}, {"name": "bar"}]})

    models = await mgr.get_loaded_models()
    assert models == ["foo", "bar"]


@pytest.mark.asyncio
async def test_ollama_get_loaded_models_client_ps_coroutine():
    mgr = OllamaModelManager()
    mgr.client = FakeClientWithAsyncPs(
        {"models": [{"name": "async1"}, {"name": "async2"}]},
    )

    models = await mgr.get_loaded_models()
    assert models == ["async1", "async2"]


@pytest.mark.asyncio
async def test_ollama_get_loaded_models_fallback_api_sync():
    mgr = OllamaModelManager()
    mgr.client = None

    # Patch _get_client to return our fake HTTP client synchronously
    async def _get_client():
        return FakeHTTPClient({"models": [{"name": "x"}, {"name": "y"}]})

    mgr._get_client = _get_client

    models = await mgr.get_loaded_models()
    assert models == ["x", "y"]


@pytest.mark.asyncio
async def test_ollama_get_loaded_models_fallback_api_coroutine_json():
    mgr = OllamaModelManager()
    mgr.client = None

    async def _get_client():
        # Return fake client whose json() returns a coroutine
        async def coro():
            await asyncio.sleep(0)
            return {"models": [{"name": "z"}]}

        class RespWithCoro(FakeResp):
            def json(self):
                return coro()

        class ClientWithCoro:
            async def get(self, path):
                return RespWithCoro(None)

        return ClientWithCoro()

    mgr._get_client = _get_client

    models = await mgr.get_loaded_models()
    assert models == ["z"]


@pytest.mark.asyncio
async def test_llm_model_manager_unloads_other_providers_on_switch():
    class FakeManager:
        def __init__(self, models):
            self.models = models
            self.unloaded = []

        async def get_loaded_models(self):
            return list(self.models)

        async def unload_model(self, model):
            self.unloaded.append(model)
            return True

        async def close(self):
            return None

    mm = LLMModelManager.with_defaults()
    mm.managers.clear()  # Clear default managers (ollama, lm-studio, etc.)
    m1 = FakeManager(["a", "b"])
    m2 = FakeManager(["x"])

    mm.register_provider("p1", m1)
    mm.register_provider("p2", m2)

    # Set active provider to p2 and then switch to p1
    mm.active_provider = "p2"
    result = await mm.switch_provider("p1")

    assert result is True
    # Ensure p2 had its models unloaded
    assert m2.unloaded == ["x"]
    assert mm.get_current_provider() == "p1"


@pytest.mark.asyncio
async def test_load_model_no_provider_returns_error():
    from quadkit.ai.llm.model_manager import LLMModelManager

    mm = LLMModelManager.with_defaults()

    result = await mm.load_model("nope")
    assert result.success is False
    assert "No provider available" in result.error


@pytest.mark.asyncio
async def test_switch_provider_unknown_returns_false():
    from quadkit.ai.llm.model_manager import LLMModelManager

    mm = LLMModelManager.with_defaults()
    res = await mm.switch_provider("does-not-exist")
    assert res is False
