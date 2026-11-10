"""Fluent workflow graph builder."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.workflow.config import GraphConfig
from quadkit.workflow.exceptions import GraphValidationError
from quadkit.workflow.graph.edge import WorkflowEdge
from quadkit.workflow.graph.engine import WorkflowEngine
from quadkit.workflow.nodes.agent_node import AgentNode
from quadkit.workflow.nodes.gate_node import GateNode
from quadkit.workflow.nodes.human_node import HumanNode
from quadkit.workflow.nodes.llm_node import LLMNode
from quadkit.workflow.nodes.subworkflow_node import SubworkflowNode
from quadkit.workflow.nodes.tool_node import ToolNode

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.workflow.graph.node import AbstractWorkflowNode


class WorkflowBuilder:
    """Fluent builder for :class:`~quadkit.workflow.graph.engine.WorkflowEngine`.

    Args:
        name: Workflow identifier used in logs and checkpoints.
        config: Default runtime configuration.
    """

    def __init__(
        self,
        name: str,
        config: GraphConfig | None = None,
        version: int = 1,
    ) -> None:
        self._name = name
        self._config = config or GraphConfig()
        self._version = version
        self._nodes: dict[str, AbstractWorkflowNode] = {}
        self._edges: list[WorkflowEdge] = []
        self._entry_node: str | None = None
        self._terminal_conditions: dict[
            str, Callable[[dict[str, Any]], bool] | None
        ] = {}

    def add_node(
        self,
        name: str,
        *,
        node: AbstractWorkflowNode | None = None,
        agent: Any | None = None,
        tool: Any | None = None,
        llm: Any | None = None,
        prompt: str = "",
        human_prompt: str = "",
        subworkflow: Any | None = None,
        executor: Any | None = None,
        output_key: str = "output",
    ) -> WorkflowBuilder:
        """Register a node in the workflow graph.

        Args:
            name: Unique node identifier.
            node: Pre-built AbstractWorkflowNode instance.
            agent: AgentProtocol wrapped in AgentNode.
            tool: ToolProtocol wrapped in ToolNode.
            llm: LLMClientProtocol wrapped in LLMNode.
            prompt: Prompt template for llm nodes.
            human_prompt: Prompt shown to the human for human nodes.
            subworkflow: Nested workflow for SubworkflowNode.
            executor: Agent executor required for agent nodes.
            output_key: State key to store the node primary output under.

        Returns:
            self for chaining.

        Raises:
            ValueError: If name is already registered or no node type is given.
        """
        if name in self._nodes:
            raise ValueError("Workflow node is already registered.")

        if node is not None:
            self._nodes[name] = node
        elif agent is not None:
            self._nodes[name] = AgentNode(
                name, agent=agent, executor=executor, output_key=output_key
            )
        elif tool is not None:
            self._nodes[name] = ToolNode(name, tool=tool, output_key=output_key)
        elif llm is not None:
            self._nodes[name] = LLMNode(
                name, llm=llm, prompt_template=prompt, output_key=output_key
            )
        elif human_prompt:
            self._nodes[name] = HumanNode(
                name, prompt=human_prompt, output_key=output_key
            )
        elif subworkflow is not None:
            self._nodes[name] = SubworkflowNode(
                name, workflow=subworkflow, output_key=output_key
            )
        else:
            raise ValueError("A supported workflow node implementation is required.")
        return self

    def add_gate(
        self,
        name: str,
        routes: dict[str, Callable[[dict[str, Any]], bool]],
    ) -> WorkflowBuilder:
        """Add a GateNode with conditional outgoing edges.

        Args:
            name: Gate node identifier.
            routes: Mapping of target-node-name to condition callable.

        Returns:
            self for chaining.
        """
        gate = GateNode(name, routes=routes)
        self._nodes[name] = gate
        for target, condition in routes.items():
            self._edges.append(
                WorkflowEdge(source=name, target=target, condition=condition)
            )
        return self

    def add_edge(
        self,
        source: str,
        target: str,
        *,
        condition: Callable[[dict[str, Any]], bool] | None = None,
        label: str = "",
    ) -> WorkflowBuilder:
        """Add a directed edge from source to target.

        Args:
            source: Source node name.
            target: Target node name.
            condition: Optional guard callable (state: dict) -> bool.
            label: Optional human-readable label.

        Returns:
            self for chaining.
        """
        self._edges.append(
            WorkflowEdge(source=source, target=target, condition=condition, label=label)
        )
        return self

    def set_entry(self, node: str) -> WorkflowBuilder:
        """Set node as the workflow entry point.

        Args:
            node: Node name to start execution from.

        Returns:
            self for chaining.
        """
        self._entry_node = node
        return self

    def set_terminal(
        self,
        node: str,
        *,
        condition: Callable[[dict[str, Any]], bool] | None = None,
    ) -> WorkflowBuilder:
        """Mark node as a terminal node.

        Args:
            node: Node name to mark as terminal.
            condition: Optional guard callable.

        Returns:
            self for chaining.
        """
        self._terminal_conditions[node] = condition
        return self

    def configure(self, config: GraphConfig) -> WorkflowBuilder:
        """Replace the default GraphConfig.

        Args:
            config: New configuration.

        Returns:
            self for chaining.
        """
        self._config = config
        return self

    def build(self) -> WorkflowEngine:
        """Validate and build the WorkflowEngine.

        Returns:
            Ready-to-execute workflow engine.

        Raises:
            GraphValidationError: If entry node is not set or graph has
                structural errors.
        """
        if self._entry_node is None:
            raise GraphValidationError("Workflow has no entry node.")
        if not self._terminal_conditions:
            raise GraphValidationError("Workflow has no terminal nodes.")

        engine = WorkflowEngine(
            name=self._name,
            nodes=dict(self._nodes),
            edges=list(self._edges),
            entry_node=self._entry_node,
            terminal_conditions=dict(self._terminal_conditions),
            config=self._config,
            version=self._version,
        )
        engine.validate()
        return engine


__all__ = ["WorkflowBuilder"]
