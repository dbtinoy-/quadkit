import pytest

from quadkit.ai.llm.registry.core import ProviderInfo
from quadkit.contracts.ai.providers import ModelInfo
from quadkit.contracts.ai.types import ModelCapability


class DummyClient:
    pass


@pytest.mark.asyncio
async def test_get_existing_provider(provider_registry):
    info = provider_registry.get_provider("openai")
    assert isinstance(info, ProviderInfo)
    assert info.name == "openai"
    assert info.default_models


@pytest.mark.asyncio
async def test_register_and_unregister_custom_provider(provider_registry):
    name = "my-custom"
    # Ensure clean state
    if name in provider_registry.list_providers():
        provider_registry.unregister(name)

    provider_registry.register(
        name=name,
        client_class=DummyClient,
        default_models=["custom-1"],
        supports_streaming=False,
        supports_tools=False,
        supports_vision=False,
        base_url="https://api.custom.test",
        description="Test provider",
    )

    assert name in provider_registry.list_providers()
    info = provider_registry.get_provider(name)
    assert info.client_class is DummyClient
    assert info.default_models == ["custom-1"]

    provider_registry.unregister(name)
    assert name not in provider_registry.list_providers()
    with pytest.raises(KeyError):
        provider_registry.get_provider(name)


@pytest.mark.asyncio
async def test_register_invalid_name_raises(provider_registry):
    with pytest.raises(ValueError, match="lowercase"):
        provider_registry.register(name="Invalid Name", client_class=DummyClient)


@pytest.mark.asyncio
async def test_search_providers_filters(provider_registry):
    # There should be at least one provider that supports vision (openai)
    vision_providers = provider_registry.search_providers(supports_vision=True)
    assert any(info.name == "openai" for info in vision_providers)

    # Search by tools support
    tools_providers = provider_registry.search_providers(supports_tools=True)
    assert any(info.supports_tools for info in tools_providers)


@pytest.mark.asyncio
async def test_extended_builtin_providers_registered(provider_registry) -> None:
    expected = [
        "azure-openai",
        "aws-bedrock",
        "google-vertex",
        "deepseek",
        "together",
        "fireworks",
    ]

    available = provider_registry.list_providers()
    for provider_name in expected:
        assert provider_name in available
        info = provider_registry.get_provider(provider_name)
        assert info.default_models


@pytest.mark.asyncio
async def test_register_provider_stores_client_and_model_info(
    provider_registry,
) -> None:
    name = "runtime-custom"
    if name in provider_registry.list_providers():
        provider_registry.unregister(name)

    client = DummyClient()
    model = ModelInfo(
        model_id="runtime-custom-v1",
        provider=name,
        display_name="Runtime Custom V1",
        capabilities=frozenset(
            {
                ModelCapability.CHAT,
                ModelCapability.STREAMING,
                ModelCapability.FUNCTION_CALLING,
            }
        ),
        context_window=16384,
        max_output_tokens=2048,
        input_cost_per_million=0.5,
        output_cost_per_million=1.0,
    )

    await provider_registry.register_provider(name, client, [model])

    assert await provider_registry.get_client(name) is client
    assert provider_registry.get_model_info(model.model_id) == model
    matching_models = [
        candidate
        for candidate in provider_registry.list_models(
            {ModelCapability.FUNCTION_CALLING}
        )
        if candidate.provider == name
    ]
    assert matching_models == [model]

    info = provider_registry.get_provider(name)
    assert info.default_models == [model.model_id]
    assert info.supports_streaming is True
    assert info.supports_tools is True
    assert info.supports_vision is False

    provider_registry.unregister(name)


@pytest.mark.asyncio
async def test_register_provider_updates_existing_entry_without_wiping_defaults(
    provider_registry,
) -> None:
    name = "runtime-existing"
    if name in provider_registry.list_providers():
        provider_registry.unregister(name)

    provider_registry.register(
        name=name,
        client_class=DummyClient,
        default_models=["existing-model"],
        supports_streaming=False,
        supports_tools=True,
        supports_vision=True,
        base_url="https://example.test",
        description="Existing provider",
    )

    runtime_client = DummyClient()
    await provider_registry.register_provider(name, runtime_client, [])

    info = provider_registry.get_provider(name)
    assert info.default_models == ["existing-model"]
    assert info.supports_streaming is False
    assert info.supports_tools is True
    assert info.supports_vision is True
    assert info.base_url == "https://example.test"
    assert info.description == "Existing provider"
    assert await provider_registry.get_client(name) is runtime_client

    provider_registry.unregister(name)
