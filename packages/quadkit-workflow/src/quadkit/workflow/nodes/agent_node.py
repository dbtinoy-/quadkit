"""Agent workflow node."""

from __future__ import annotations

from typing import Any

from quadkit.logging import get_logger, safe_error_type
from quadkit.workflow.graph.node import AbstractWorkflowNode, NodeType

logger = get_logger(__name__)


class AgentNode(AbstractWorkflowNode):
    """Workflow node that executes a Quadkit agent.

    Args:
        name: Node identifier.
        agent: Object implementing AgentProtocol.
        executor: Optional AgentExecutorProtocol instance.
        input_key: State key to read the agent input from.
        output_key: State key where the agent response is stored.
    """

    def __init__(
        self,
        name: str,
        *,
        agent: Any,
        executor: Any | None = None,
        input_key: str = "input",
        output_key: str = "output",
    ) -> None:
        super().__init__(name, NodeType.AGENT)
        self._agent = agent
        self._executor = executor
        self._input_key = input_key
        self._output_key = output_key

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Run the agent with the value of state[input_key].

        Args:
            state: Current workflow state.

        Returns:
            Dict with {output_key: agent_response_text}.
        """
        message = str(state.get(self._input_key, ""))

        if self._executor is not None:
            result = await self._executor.execute(self._agent, message)
            if result.is_ok():
                response = result.unwrap()
                text = getattr(response, "message", str(response))
            else:
                error = result.unwrap_err()
                logger.warning(
                    "agent_node_error",
                    error_type=safe_error_type(error),
                )
                text = "Agent execution failed."
        else:
            run_fn = getattr(self._agent, "run", None)
            if run_fn is None:
                text = "Agent execution is not configured."
            else:
                raw = await run_fn(message)
                text = str(raw)

        logger.debug("agent_node_done", output_len=len(text))
        return {self._output_key: text}


__all__ = ["AgentNode"]
