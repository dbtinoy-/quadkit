"""Strategies module for agent reasoning strategies."""

from __future__ import annotations

from quadkit.ai.agents.strategies.base import AbstractStrategy
from quadkit.ai.agents.strategies.function_calling import FunctionCallingStrategy
from quadkit.ai.agents.strategies.plan_execute import (
    PlanAndExecuteStrategy,
    PlanStepStatus,
)
from quadkit.ai.agents.strategies.react import ReActStrategy
from quadkit.ai.agents.strategies.reflexion import ReflexionStrategy
from quadkit.ai.agents.strategies.supervisor import SupervisorStrategy

__all__ = [
    "AbstractStrategy",
    "FunctionCallingStrategy",
    "PlanAndExecuteStrategy",
    "PlanStepStatus",
    "ReActStrategy",
    "ReflexionStrategy",
    "SupervisorStrategy",
]
