"""Human-in-the-loop workflow node."""

from __future__ import annotations

from typing import Any

from quadkit.logging.factory import get_logger
from quadkit.workflow.exceptions import HumanInputRequiredError
from quadkit.workflow.graph.node import AbstractWorkflowNode, NodeType

logger = get_logger(__name__)


class HumanNode(AbstractWorkflowNode):
    """Pause the workflow to collect a human response.

    Args:
        name: Node identifier (doubles as checkpoint_id).
        prompt: Question or instruction to display to the operator.
            Supports {key} substitution from state.
        output_key: State key where the human response will be stored.
        resume_key: State key the engine populates with the human answer
            when WorkflowEngine.resume() is called.
    """

    def __init__(
        self,
        name: str,
        *,
        prompt: str = "Human input required.",
        output_key: str = "human_response",
        resume_key: str | None = None,
    ) -> None:
        super().__init__(name, NodeType.HUMAN)
        self._prompt = prompt
        self._output_key = output_key
        self._resume_key = resume_key if resume_key is not None else output_key

    @property
    def resume_key(self) -> str:
        """State key ``WorkflowEngine.resume`` populates with the answer."""
        return self._resume_key

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Return human response if resumed, otherwise pause execution.

        Args:
            state: Current workflow state.

        Returns:
            Dict with {output_key: human_response} when resumed.

        Raises:
            HumanInputRequiredError: When no prior human response is in state.
        """
        if self._resume_key in state and state[self._resume_key] is not None:
            response = state[self._resume_key]
            logger.debug("human_node_resumed")
            return {self._output_key: response}

        rendered_prompt = self._prompt.format_map(
            {k: v for k, v in state.items() if isinstance(v, (str, int, float, bool))}
        )
        logger.info("human_node_pausing")
        raise HumanInputRequiredError(rendered_prompt, node=self.name)


__all__ = ["HumanNode"]
