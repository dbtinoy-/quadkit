"""quadkit-ai-agents — Agent system for Quadkit Framework.

Canonical import paths
-----------------------
AgentBase class:     from quadkit.ai.agents import AgentBase
Tool decorator:      from quadkit.ai.agents import tool
Tool registry:       from quadkit.ai.agents import ToolRegistryImpl
Agent executor:      from quadkit.ai.agents import AgentExecutorImpl
ReAct strategy:      from quadkit.ai.agents import ReActStrategy
Crew:                from quadkit.ai.agents import Crew
CrewTask:            from quadkit.ai.agents import CrewTask
CrewBuilder:         from quadkit.ai.agents import CrewBuilder
Process:             from quadkit.ai.agents import Process

Quick Start
-----------

    from quadkit.ai.agents import AgentBase, tool

    @tool
    async def lookup_order(order_id: str) -> dict:
        \"\"\"Look up an order by its ID.\"\"\"
        return {"order_id": order_id, "status": "shipped"}

    class OrderAgent(AgentBase):
        name = "order_agent"
        system_prompt = "You are a helpful order support agent."

        @property
        def tools(self):
            return [lookup_order]
"""

from __future__ import annotations

import importlib.metadata
import pkgutil
from typing import TYPE_CHECKING, Any

__path__ = pkgutil.extend_path(__path__, __name__)

from quadkit.ai.agents.constants import __version__ as __version__

if TYPE_CHECKING:
    from quadkit.ai.agents.agent import AgentBase, AgentBuilder
    from quadkit.ai.agents.config import AgentConfig
    from quadkit.ai.agents.crew import (
        Crew,
        CrewBuilder,
        CrewExecutionResult,
        CrewRunner,
        CrewTask,
        Process,
        TaskResult,
    )
    from quadkit.ai.agents.decorators import strategy
    from quadkit.ai.agents.delegation import AgentAsToolAdapter
    from quadkit.ai.agents.di.provider import AgentsProvider
    from quadkit.ai.agents.events import (
        AgentRunCompletedEvent,
        ToolExecutionCompletedEvent,
    )
    from quadkit.ai.agents.exceptions import (
        AgentConfigurationError,
        AgentError,
        AgentExecutionError,
        BudgetExceededError,
        MaxIterationsExceededError,
        StrategyError,
        ToolAccessDeniedError,
        ToolError,
        ToolExecutionError,
        ToolNotFoundError,
    )
    from quadkit.ai.agents.executor import AgentExecutorImpl
    from quadkit.ai.agents.hooks import (
        AgentCompletedHook,
        AgentStartedHook,
        AgentToolCalledHook,
    )
    from quadkit.ai.agents.module import AgentsModule
    from quadkit.ai.agents.protocols import ObserverProtocol, PlannerProtocol
    from quadkit.ai.agents.strategies import (
        AbstractStrategy,
        PlanAndExecuteStrategy,
        PlanStepStatus,
        ReActStrategy,
        ReflexionStrategy,
        SupervisorStrategy,
    )
    from quadkit.ai.agents.strategies.strategy_registry import AgentStrategyRegistry
    from quadkit.ai.agents.tools import AbstractTool, ToolRegistryImpl, tool
    from quadkit.ai.agents.types import (
        AgentResponse,
        ReasoningStep,
        ToolExecutionRecord,
    )

_LAZY_IMPORTS: dict[str, str] = {
    # Events
    "AgentRunCompletedEvent": "quadkit.ai.agents.events",
    # Hooks
    "AgentCompletedHook": "quadkit.ai.agents.hooks",
    "AgentStartedHook": "quadkit.ai.agents.hooks",
    "AgentToolCalledHook": "quadkit.ai.agents.hooks",
    "AbstractStrategy": "quadkit.ai.agents.strategies",
    "AbstractTool": "quadkit.ai.agents.tools",
    "AgentAsToolAdapter": "quadkit.ai.agents.delegation",
    "AgentBase": "quadkit.ai.agents.agent",
    "AgentBuilder": "quadkit.ai.agents.agent",
    "AgentConfig": "quadkit.ai.agents.config",
    "AgentStrategyRegistry": "quadkit.ai.agents.strategies.strategy_registry",
    "Crew": "quadkit.ai.agents.crew",
    "CrewBuilder": "quadkit.ai.agents.crew",
    "CrewExecutionResult": "quadkit.ai.agents.crew",
    "CrewRunner": "quadkit.ai.agents.crew",
    "CrewTask": "quadkit.ai.agents.crew",
    "Process": "quadkit.ai.agents.crew",
    "TaskResult": "quadkit.ai.agents.crew",
    "AgentConfigurationError": "quadkit.ai.agents.exceptions",
    "AgentError": "quadkit.ai.agents.exceptions",
    "AgentExecutionError": "quadkit.ai.agents.exceptions",
    "AgentExecutorImpl": "quadkit.ai.agents.executor",
    "AgentResponse": "quadkit.ai.agents.types",
    "AgentsModule": "quadkit.ai.agents.module",
    "AgentsProvider": "quadkit.ai.agents.di.provider",
    "BudgetExceededError": "quadkit.ai.agents.exceptions",
    "MaxIterationsExceededError": "quadkit.ai.agents.exceptions",
    "PlanAndExecuteStrategy": "quadkit.ai.agents.strategies",
    "PlanStepStatus": "quadkit.ai.agents.strategies",
    "ReActStrategy": "quadkit.ai.agents.strategies",
    "ReflexionStrategy": "quadkit.ai.agents.strategies",
    "SupervisorStrategy": "quadkit.ai.agents.strategies",
    "ReasoningStep": "quadkit.ai.agents.types",
    "strategy": "quadkit.ai.agents.decorators",
    "StrategyError": "quadkit.ai.agents.exceptions",
    "ToolAccessDeniedError": "quadkit.ai.agents.exceptions",
    "ToolExecutionCompletedEvent": "quadkit.ai.agents.events",
    "ToolExecutionRecord": "quadkit.ai.agents.types",
    "ToolError": "quadkit.ai.agents.exceptions",
    "ToolExecutionError": "quadkit.ai.agents.exceptions",
    "ToolNotFoundError": "quadkit.ai.agents.exceptions",
    "ToolRegistryImpl": "quadkit.ai.agents.tools",
    "tool": "quadkit.ai.agents.tools",
    # Internal protocols
    "PlannerProtocol": "quadkit.ai.agents.protocols",
    "ObserverProtocol": "quadkit.ai.agents.protocols",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        import importlib as _importlib

        module = _importlib.import_module(_LAZY_IMPORTS[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(_LAZY_IMPORTS.keys()))


__all__ = [
    "AbstractStrategy",
    "AbstractTool",
    "AgentAsToolAdapter",
    "AgentBase",
    "AgentBuilder",
    "AgentCompletedHook",
    "AgentConfig",
    "AgentConfigurationError",
    "AgentError",
    "AgentExecutionError",
    "AgentExecutorImpl",
    "AgentResponse",
    "AgentRunCompletedEvent",
    "AgentStartedHook",
    "AgentStrategyRegistry",
    "AgentToolCalledHook",
    "AgentsModule",
    "AgentsProvider",
    "BudgetExceededError",
    "Crew",
    "CrewBuilder",
    "CrewExecutionResult",
    "CrewRunner",
    "CrewTask",
    "MaxIterationsExceededError",
    "ObserverProtocol",
    "PlanAndExecuteStrategy",
    "PlanStepStatus",
    "PlannerProtocol",
    "Process",
    "ReActStrategy",
    "ReasoningStep",
    "ReflexionStrategy",
    "StrategyError",
    "SupervisorStrategy",
    "TaskResult",
    "ToolAccessDeniedError",
    "ToolError",
    "ToolExecutionCompletedEvent",
    "ToolExecutionError",
    "ToolExecutionRecord",
    "ToolNotFoundError",
    "ToolRegistryImpl",
    "strategy",
    "tool",
]
