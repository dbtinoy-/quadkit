"""Config binding tests for the LLM routing provider."""

from __future__ import annotations

import pytest

from quadkit.ai.llm.di.routing_provider import LLMRoutingProvider
from quadkit.ai.llm.routing.config import LLMConfig


class _FakeRegistrar:
    """Minimal registrar recording singleton bindings."""

    def __init__(self) -> None:
        self.bindings: dict[object, object] = {}

    def singleton(
        self, key: object, instance: object | None = None, **kwargs: object
    ) -> None:
        resolved = instance if instance is not None else kwargs.get("instance", key)
        self.bindings[key] = resolved


@pytest.mark.asyncio
async def test_llm_config_bound_into_container() -> None:
    config = LLMConfig()
    provider = LLMRoutingProvider(config=config)
    registrar = _FakeRegistrar()
    await provider.register(registrar)
    assert registrar.bindings[LLMConfig] is config