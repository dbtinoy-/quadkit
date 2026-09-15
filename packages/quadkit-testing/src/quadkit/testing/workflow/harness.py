"""Workflow test helpers for integration testing.

Provides utilities for testing workflow definitions and step
execution without requiring a real workflow engine.
"""

from __future__ import annotations

from typing import Any


class WorkflowTestHarness:
    """Test harness for workflow step execution.

    Enables running workflow steps in isolation, capturing inputs/outputs
    for assertion.

    Usage::

        harness = WorkflowTestHarness()
        result = await harness.run_step(my_step, input_data={"order_id": "123"})
        assert result.status == "completed"
    """

    def __init__(self) -> None:
        """Initialize the workflow test harness."""
        self._step_results: list[dict[str, Any]] = []
        self._context: dict[str, Any] = {}

    @property
    def step_results(self) -> list[dict[str, Any]]:
        """All recorded step results."""
        return list(self._step_results)

    @property
    def context(self) -> dict[str, Any]:
        """The shared workflow context that persists between steps."""
        return self._context

    async def run_step(
        self,
        step_fn: Any,
        *,
        input_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a single workflow step.

        Args:
            step_fn: The step function or callable to execute.
            input_data: Optional input data for the step.

        Returns:
            A result dict with ``status`` and ``output`` keys.
        """
        merged_input = {**self._context, **(input_data or {})}
        try:
            output = await step_fn(merged_input)
            result = {"status": "completed", "output": output}
        except Exception as exc:  # noqa: BLE001
            result = {"status": "failed", "error": str(exc)}
        self._step_results.append(result)
        if result["status"] == "completed" and isinstance(result.get("output"), dict):
            self._context.update(result["output"])
        return result

    def reset(self) -> None:
        """Reset the harness for a new workflow run."""
        self._step_results.clear()
        self._context.clear()


__all__ = ["WorkflowTestHarness"]
