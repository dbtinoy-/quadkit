"""Shared mutable workflow state passed between nodes."""

from __future__ import annotations

from typing import Any


class WorkflowState:
    """Shared, mutable state container for a workflow execution.

    All nodes read from and write to the same ``WorkflowState`` instance.
    Each node's ``execute()`` method receives the state as a plain
    ``dict[str, Any]`` and returns a partial update dict that is merged
    back via :meth:`merge`.

    Keys set by the engine:
    - ``"input"`` — the original user input string
    - ``"output"`` — the most recent node output (updated each step)
    - ``"_iteration"`` — current traversal step count
    - ``"_history"`` — ordered list of ``(node_name, output_dict)`` tuples

    Example::

        from quadkit.logging import get_logger

        logger = get_logger(__name__)
        state = WorkflowState(input="Summarise this document")
        state.merge({"summary": "...", "output": "..."})
        logger.info("workflow_output_ready")
    """

    def __init__(
        self,
        input: str = "",
        *,
        initial: dict[str, Any] | None = None,
    ) -> None:
        self._data: dict[str, Any] = {
            "input": input,
            "output": "",
            "_iteration": 0,
            "_history": [],
        }
        if initial:
            self._data.update(initial)

    # --- dict-like access ---------------------------------------------------

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __contains__(self, key: object) -> bool:
        return key in self._data

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for *key*, or *default* if absent."""
        return self._data.get(key, default)

    def as_dict(self) -> dict[str, Any]:
        """Return a shallow copy of the underlying state dict."""
        return dict(self._data)

    # --- mutation -----------------------------------------------------------

    def merge(self, update: dict[str, Any]) -> None:
        """Merge *update* into state, overwriting existing keys.

        Internal keys prefixed with ``_`` are skipped from external
        updates to prevent accidental manipulation of engine metadata.
        """
        for k, v in update.items():
            if k.startswith("_"):
                continue
            self._data[k] = v

    def record(self, node_name: str, output: dict[str, Any]) -> None:
        """Append a node execution record to the history list.

        Args:
            node_name: Name of the node that produced *output*.
            output: State update dict returned by the node.
        """
        self._data["_history"].append((node_name, output))
        self._data["_iteration"] += 1

    # --- convenience --------------------------------------------------------

    @property
    def iteration(self) -> int:
        """Current graph traversal step count."""
        return int(self._data["_iteration"])

    @property
    def history(self) -> list[tuple[str, dict[str, Any]]]:
        """Ordered list of ``(node_name, output_dict)`` tuples."""
        return list(self._data["_history"])

    def __repr__(self) -> str:
        keys = [k for k in self._data if not k.startswith("_")]
        return f"WorkflowState(iteration={self.iteration}, keys={keys!r})"


__all__ = ["WorkflowState"]
