"""AgentBuilder - fluent API for creating agents."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from quadkit.contracts.ai.agents import (
        AgentProtocol,
        MemoryProtocol,
        StrategyProtocol,
        ToolProtocol,
    )
    from quadkit.contracts.ai.guards import GuardPipelineProtocol


class AgentBuilder:
    """Fluent builder for creating agents programmatically.

    Produces a lightweight agent instance that can be passed straight to
    ``AgentExecutorImpl.run()``.

    Example::

        agent = (
            AgentBuilder("order_agent")
            .with_system_prompt("You are a helpful order support agent.")
            .with_tools(lookup_order, search_products)
            .with_strategy("react", max_iterations=10)
            .with_memory(memory_backend)
            .with_guards(pii_guard, toxicity_guard)
            .with_governance(budget_limit=10.0)
            .build()
        )
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._system_prompt = ""
        self._tools: list[ToolProtocol] = []
        self._strategy_name: str | None = None
        self._strategy_kwargs: dict[str, Any] = {}
        self._memory: MemoryProtocol | None = None
        self._guards: list[Any] = []
        self._guard_pipeline: GuardPipelineProtocol | None = None
        self._governance_kwargs: dict[str, Any] = {}
        self._temperature: float = 0.7

    def with_system_prompt(self, prompt: str) -> AgentBuilder:
        """Set the agent's system prompt."""
        self._system_prompt = prompt
        return self

    def with_tools(self, *tools: ToolProtocol) -> AgentBuilder:
        """Add tools to the agent."""
        self._tools.extend(tools)
        return self

    def with_strategy(
        self,
        strategy: str,
        **kwargs: Any,
    ) -> AgentBuilder:
        """Set the reasoning strategy by name.

        Args:
            strategy: Strategy name (e.g. ``"react"``, ``"simple"``).
            **kwargs: Keyword arguments forwarded to the strategy constructor
                (e.g. ``max_iterations=10``).
        """
        self._strategy_name = strategy
        self._strategy_kwargs = kwargs
        return self

    def with_memory(self, memory: MemoryProtocol) -> AgentBuilder:
        """Attach a memory backend to the agent.

        Args:
            memory: A memory backend instance implementing ``MemoryProtocol``.
        """
        self._memory = memory
        return self

    def with_guards(self, *guards: ToolProtocol) -> AgentBuilder:
        """Add content-safety guards to the agent.

        Args:
            *guards: Guard tool instances to evaluate on input/output.
        """
        self._guards.extend(guards)
        return self

    def with_guard_pipeline(
        self,
        pipeline: GuardPipelineProtocol,
    ) -> AgentBuilder:
        """Set a pre-built guard pipeline.

        Args:
            pipeline: A fully configured ``GuardPipelineProtocol``.
        """
        self._guard_pipeline = pipeline
        return self

    def with_governance(self, **kwargs: Any) -> AgentBuilder:
        """Configure governance parameters.

        Args:
            **kwargs: Governance options (e.g. ``budget_limit=10.0``).
        """
        self._governance_kwargs.update(kwargs)
        return self

    def with_temperature(self, temperature: float) -> AgentBuilder:
        """Set the LLM temperature for this agent.

        Args:
            temperature: Sampling temperature (0.0–2.0).
        """
        self._temperature = temperature
        return self

    def build(self) -> AgentProtocol:
        """Build and return the agent.

        Raises:
            ValueError: If the agent name is empty.
        """
        if not self._name:
            raise ValueError("Agent name is required")

        strategy = None
        if self._strategy_name:
            strategy = _resolve_strategy(
                self._strategy_name,
                **self._strategy_kwargs,
            )

        return _BuiltAgent(
            name=self._name,
            system_prompt=self._system_prompt,
            tools=list(self._tools),
            strategy=strategy,
            memory=self._memory,
            guards=list(self._guards),
            guard_pipeline=self._guard_pipeline,
            governance_kwargs=dict(self._governance_kwargs),
            temperature=self._temperature,
        )


def _resolve_strategy(name: str, **kwargs: Any) -> StrategyProtocol:
    """Resolve a strategy by name using the registry.

    Args:
        name: Strategy identifier (``"react"``, ``"plan-execute"``, ``"reflexion"``).
        **kwargs: Constructor arguments forwarded to the strategy.

    Returns:
        Strategy instance.

    Raises:
        ValueError: If the strategy name is unknown.
    """
    from quadkit.ai.agents.strategies.strategy_registry import AgentStrategyRegistry

    registry = AgentStrategyRegistry.with_defaults()
    strategy_class = registry.get(name.lower())
    if strategy_class is None:
        raise ValueError(
            f"Unknown strategy: {name!r}. Supported: {', '.join(registry.keys())}"
        )
    return cast("StrategyProtocol", strategy_class(**kwargs))


class _BuiltAgent:
    """Internal agent implementation created by AgentBuilder."""

    def __init__(
        self,
        name: str,
        system_prompt: str,
        tools: list[ToolProtocol],
        strategy: StrategyProtocol | None = None,
        memory: MemoryProtocol | None = None,
        guards: list[ToolProtocol] | None = None,
        guard_pipeline: GuardPipelineProtocol | None = None,
        governance_kwargs: dict[str, Any] | None = None,
        temperature: float = 0.7,
    ) -> None:
        self._name = name
        self._system_prompt = system_prompt
        self._tools = tools
        self._strategy = strategy
        self._memory = memory
        self._guards = guards or []
        self._guard_pipeline = guard_pipeline
        self._governance_kwargs = governance_kwargs or {}
        self._temperature = temperature

    @property
    def name(self) -> str:
        return self._name

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    @property
    def tools(self) -> list[ToolProtocol]:
        return self._tools

    @property
    def strategy(self) -> StrategyProtocol | None:
        return self._strategy

    @property
    def memory(self) -> MemoryProtocol | None:
        return self._memory

    @property
    def guards(self) -> list[ToolProtocol]:
        return self._guards

    @property
    def guard_pipeline(self) -> GuardPipelineProtocol | None:
        return self._guard_pipeline

    @property
    def governance_kwargs(self) -> dict[str, Any]:
        return self._governance_kwargs

    @property
    def temperature(self) -> float:
        return self._temperature

    def __repr__(self) -> str:
        return f"BuiltAgent(name={self._name!r}, tools={len(self._tools)})"
