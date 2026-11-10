import pytest

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.registry.core import ProviderRegistry


@pytest.mark.asyncio
async def test_openrouter_instantiation(provider_registry):
    info = provider_registry.get_provider("openrouter")
    client_cls = info.client_class

    # Instantiate with minimal required fields
    client = client_cls(ClientConfig(api_key="fake", model="gpt-4o"))

    # Context manager should return the instance
    async with client as active:
        assert active is client
