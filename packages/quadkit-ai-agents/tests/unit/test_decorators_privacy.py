"""Privacy regressions for agent registration errors."""

from __future__ import annotations

import pytest

from quadkit.ai.agents import decorators as agent_decorators
from quadkit.ai.agents.decorators import strategy, tool


def test_duplicate_tool_error_omits_private_identifier(monkeypatch) -> None:
    monkeypatch.setattr(agent_decorators, "_TOOL_REGISTRY", {})
    private_name = "private_tool_tenant_42"

    @tool(private_name)
    class FirstTool:
        pass
    assert FirstTool._tool_name == private_name

    with pytest.raises(ValueError, match="already registered") as exc_info:

        @tool(private_name)
        class SecondTool:
            pass

    assert private_name not in str(exc_info.value)
    assert "FirstTool" not in str(exc_info.value)
    assert "SecondTool" not in str(exc_info.value)


def test_duplicate_strategy_error_omits_private_identifier(monkeypatch) -> None:
    monkeypatch.setattr(agent_decorators, "_STRATEGY_REGISTRY", {})
    private_name = "private_strategy_tenant_42"

    @strategy(private_name)
    class FirstStrategy:
        pass
    assert FirstStrategy._strategy_name == private_name

    with pytest.raises(ValueError, match="already registered") as exc_info:

        @strategy(private_name)
        class SecondStrategy:
            pass

    assert private_name not in str(exc_info.value)
    assert "FirstStrategy" not in str(exc_info.value)
    assert "SecondStrategy" not in str(exc_info.value)
