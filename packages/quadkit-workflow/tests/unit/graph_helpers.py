"""Stub node implementations shared across quadkit-workflow graph test modules."""

from __future__ import annotations

from typing import Any

from quadkit.workflow.graph.node import AbstractWorkflowNode, NodeType


class EchoNode(AbstractWorkflowNode):
    """Returns {"output": state["input"], "visited": self.name}."""

    def __init__(self, name: str) -> None:
        super().__init__(name, NodeType.CUSTOM)

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        return {"output": state.get("input", ""), "visited": self.name}


class ConstantNode(AbstractWorkflowNode):
    """Always returns a fixed dict of keyword constants."""

    def __init__(self, name: str, **constants: Any) -> None:
        super().__init__(name, NodeType.CUSTOM)
        self._constants = constants

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        return dict(self._constants)


class AppendNode(AbstractWorkflowNode):
    """Appends self.name to state["path"] list and sets output=self.name."""

    def __init__(self, name: str) -> None:
        super().__init__(name, NodeType.CUSTOM)

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        path = list(state.get("path", []))
        path.append(self.name)
        return {"path": path, "output": self.name}


class CounterNode(AbstractWorkflowNode):
    """Increments state["count"] by 1 on each execution."""

    def __init__(self, name: str) -> None:
        super().__init__(name, NodeType.CUSTOM)

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        return {"count": state.get("count", 0) + 1, "output": "counted"}


class SlowNode(AbstractWorkflowNode):
    """Sleeps for a configurable duration (used for timeout tests)."""

    def __init__(self, name: str, delay: float = 5.0) -> None:
        import asyncio

        super().__init__(name, NodeType.CUSTOM)
        self._delay = delay
        self._asyncio = asyncio

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        await self._asyncio.sleep(self._delay)
        return {"output": "slow_done"}


class FailingNode(AbstractWorkflowNode):
    """Always raises ValueError with a configurable message."""

    def __init__(self, name: str, message: str = "node failed") -> None:
        super().__init__(name, NodeType.CUSTOM)
        self._message = message

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        raise ValueError(self._message)


__all__ = [
    "AppendNode",
    "ConstantNode",
    "CounterNode",
    "EchoNode",
    "FailingNode",
    "SlowNode",
]
