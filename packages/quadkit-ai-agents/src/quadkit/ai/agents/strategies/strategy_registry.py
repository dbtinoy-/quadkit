"""Agent reasoning strategy registry.

Maps strategy names (``"react"``, ``"reflexion"``, ``"plan-execute"``)
to strategy *classes* and instantiates on demand via
:meth:`~quadkit.primitives.registry.StrategyRegistry.instantiate`.
"""

from __future__ import annotations

from quadkit.logging import (
    get_logger,
)
from quadkit.primitives.registry import StrategyRegistry

logger = get_logger(__name__)


class AgentStrategyRegistry(StrategyRegistry):
    """Registry of agent reasoning strategy implementations.

    Usage::

        registry = AgentStrategyRegistry.with_defaults()
        strategy = registry.instantiate("react", max_iterations=10)
    """

    def __init__(self) -> None:
        super().__init__(name="agent.strategies", allow_overwrite=True)

    # ------------------------------------------------------------------
    # Built-in strategies
    # ------------------------------------------------------------------

    @classmethod
    def default_strategies(cls) -> dict[str, type]:
        """Return built-in strategy key → class mapping.

        Returns:
            Dict mapping strategy name to its class.
        """
        from quadkit.ai.agents.strategies.function_calling import (
            FunctionCallingStrategy,
        )
        from quadkit.ai.agents.strategies.plan_execute import PlanAndExecuteStrategy
        from quadkit.ai.agents.strategies.react import ReActStrategy
        from quadkit.ai.agents.strategies.reflexion import ReflexionStrategy

        return {
            "react": ReActStrategy,
            "function_calling": FunctionCallingStrategy,
            "plan-execute": PlanAndExecuteStrategy,
            "reflexion": ReflexionStrategy,
        }
