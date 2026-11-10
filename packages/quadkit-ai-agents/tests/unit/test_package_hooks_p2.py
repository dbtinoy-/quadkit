"""P2 hook surface import verification for quadkit-ai-agents."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass

import pytest


def test_agents_hooks_root_module_exists() -> None:
    import quadkit.ai.agents
    from quadkit.ai.agents.hooks import (
        AgentCompletedHook,
        AgentStartedHook,
        AgentToolCalledHook,
    )

    assert AgentStartedHook.__name__ == "AgentStartedHook"
    assert AgentCompletedHook.__name__ == "AgentCompletedHook"
    assert AgentToolCalledHook.__name__ == "AgentToolCalledHook"
    assert quadkit.ai.agents.AgentStartedHook is AgentStartedHook
    assert quadkit.ai.agents.AgentCompletedHook is AgentCompletedHook
    assert quadkit.ai.agents.AgentToolCalledHook is AgentToolCalledHook


def test_agents_hook_payloads_are_frozen_and_keyword_only() -> None:
    from quadkit.ai.agents.hooks import (
        AgentCompletedHook,
        AgentStartedHook,
        AgentToolCalledHook,
    )

    started = AgentStartedHook(agent_name="order_agent")
    completed = AgentCompletedHook(agent_name="order_agent")
    called = AgentToolCalledHook(agent_name="order_agent", tool_name="lookup_order")

    assert is_dataclass(started)
    assert is_dataclass(completed)
    assert is_dataclass(called)

    with pytest.raises(TypeError):
        AgentStartedHook("order_agent")  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        started.agent_name = "other"  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        completed.agent_name = "other"  # type: ignore[misc]

    with pytest.raises(TypeError):
        AgentToolCalledHook("order_agent", "lookup_order")  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        called.tool_name = "other_tool"  # type: ignore[misc]
