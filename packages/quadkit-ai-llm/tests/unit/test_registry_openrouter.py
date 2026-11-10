
import pytest

from quadkit.ai.llm.clients.openrouter import OpenRouterClient
from quadkit.ai.llm.registry.core import ProviderRegistry


@pytest.mark.asyncio
async def test_openrouter_registered_in_registry(provider_registry):
    registry = provider_registry
    info = registry.get_provider("openrouter")

    assert info.name == "openrouter"
    assert info.client_class is OpenRouterClient
    assert "gpt-4o" in info.default_models
    assert info.supports_streaming is True
    assert info.supports_tools is True
    assert info.base_url is not None


@pytest.mark.asyncio
async def test_search_providers_filters_by_capability(provider_registry):
    registry = provider_registry

    # Find providers that support vision
    vision_providers = registry.search_providers(supports_vision=True)
    assert any(p.name == "openai" for p in vision_providers)

    # Find providers that support streaming and tools
    streaming_tools = registry.search_providers(
        supports_streaming=True, supports_tools=True,
    )
    assert any(p.name == "openrouter" for p in streaming_tools)
