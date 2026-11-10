"""Subworkflow node — embeds a nested WorkflowEngine."""

from __future__ import annotations

from typing import Any

from quadkit.logging import get_logger, safe_error_type
from quadkit.workflow.graph.node import AbstractWorkflowNode, NodeType

logger = get_logger(__name__)


class SubworkflowNode(AbstractWorkflowNode):
    """Embed a nested WorkflowEngine as a single node in a parent workflow.

    Args:
        name: Node identifier.
        workflow: A WorkflowEngine instance to nest.
        input_key: State key to read as the subworkflow input value.
        output_key: State key where the subworkflow result is stored.
    """

    def __init__(
        self,
        name: str,
        *,
        workflow: Any,
        input_key: str = "input",
        output_key: str = "output",
    ) -> None:
        super().__init__(name, NodeType.SUBWORKFLOW)
        self._workflow = workflow
        self._input_key = input_key
        self._output_key = output_key

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute the nested workflow with the current parent state.

        Args:
            state: Current parent workflow state.

        Returns:
            Dict with {output_key: subworkflow_output} on success
            or {output_key: "Subworkflow error: ..."} on failure.
        """
        sub_input = state.get(self._input_key, "")
        logger.debug("subworkflow_node_start")
        try:
            result = await self._workflow.execute(sub_input, state=state)
        except Exception as exc:  # noqa: BLE001 — node degrades, workflow continues
            logger.warning(
                "subworkflow_node_error",
                error_type=safe_error_type(exc),
            )
            return {self._output_key: "Subworkflow execution failed."}

        if result.is_err():
            error = result.unwrap_err()
            logger.warning(
                "subworkflow_node_err",
                error_type=safe_error_type(error),
            )
            return {self._output_key: "Subworkflow execution failed."}

        sub_result = result.unwrap()
        output = sub_result.output
        logger.debug("subworkflow_node_done")
        return {self._output_key: output}


__all__ = ["SubworkflowNode"]
