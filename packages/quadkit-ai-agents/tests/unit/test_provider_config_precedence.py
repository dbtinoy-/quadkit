"""Config precedence tests for the AgentsProvider."""

from __future__ import annotations

import pytest

from quadkit.ai.agents.config import AgentConfig
from quadkit.ai.agents.di.provider import AgentsProvider


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
async def test_config_section_matches_provider_key() -> None:
    assert AgentsProvider.config_key == "ai_agents"
    assert AgentConfig.config_section == "ai_agents"


@pytest.mark.asyncio
async def test_explicit_config_wins_over_injected() -> None:
    requested = AgentConfig(max_iterations=3)
    injected = AgentConfig(max_iterations=7)
    provider = AgentsProvider(config=requested)
    provider.config = injected
    registrar = _FakeRegistrar()
    await provider.register(registrar)
    assert registrar.bindings[AgentConfig] is requested


@pytest.mark.asyncio
async def test_injected_config_used_when_no_explicit() -> None:
    injected = AgentConfig(max_iterations=7)
    provider = AgentsProvider()
    provider.config = injected
    registrar = _FakeRegistrar()
    await provider.register(registrar)
    assert registrar.bindings[AgentConfig] is injected


@pytest.mark.asyncio
async def test_defaults_when_neither() -> None:
    provider = AgentsProvider()
    registrar = _FakeRegistrar()
    await provider.register(registrar)
    bound = registrar.bindings[AgentConfig]
    assert isinstance(bound, AgentConfig)
    assert bound.max_iterations == 10