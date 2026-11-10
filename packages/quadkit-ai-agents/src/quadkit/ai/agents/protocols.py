from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PlannerProtocol(Protocol):
    """Generates an execution plan from a goal."""

    async def plan(self, goal: str, context: dict[str, Any]) -> list[str]: ...


@runtime_checkable
class ObserverProtocol(Protocol):
    """Observes agent execution steps for logging and monitoring."""

    async def on_step(self, step: int, action: str, result: Any) -> None: ...
    async def on_complete(self, total_steps: int, final_result: Any) -> None: ...
