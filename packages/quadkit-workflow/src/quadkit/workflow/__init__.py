"""Workflow orchestration package for Quadkit Framework.

Provides pipeline execution, transformation pipes, bulk operations,
saga coordination, and directed-graph workflow execution.
"""

from __future__ import annotations

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

import importlib
import importlib.metadata
from typing import TYPE_CHECKING, Any

from quadkit.workflow.constants import __version__ as __version__

if TYPE_CHECKING:
    from quadkit.workflow.bulk.models import (
        BulkBatchResult,
        BulkItemError,
        BulkOperationMetrics,
        BulkOperationState,
    )
    from quadkit.workflow.bulk.operation import BulkOperation
    from quadkit.workflow.checkpoint.store_cache import CacheContentCheckpointStore
    from quadkit.workflow.checkpoint.store_database import (
        DatabaseContentCheckpointStore,
    )
    from quadkit.workflow.checkpoint.store_memory import InMemoryContentCheckpointStore
    from quadkit.workflow.config import (
        BulkOperationConfig,
        ContentCheckpointConfig,
        GraphConfig,
    )
    from quadkit.workflow.core.definition import WorkflowDefinition
    from quadkit.workflow.core.instance import WorkflowInstance
    from quadkit.workflow.core.pipe import TransformPipe
    from quadkit.workflow.decorators import saga_step, workflow
    from quadkit.workflow.di.provider import WorkflowProvider
    from quadkit.workflow.exceptions import (
        BulkOperationCancelledError,
        BulkOperationError,
        BulkOperationTimeoutError,
        CycleDetectedError,
        GraphExecutionError,
        GraphTimeoutError,
        GraphValidationError,
        HumanInputRequiredError,
        NodeExecutionError,
        PipelineExecutionError,
        PipelineStepError,
        WorkflowCompensationError,
        WorkflowError,
        WorkflowNotFoundError,
        WorkflowStateError,
        WorkflowStepError,
        WorkflowTimeoutError,
        WorkflowVersionMismatchError,
    )
    from quadkit.workflow.execution.checkpoint import WorkflowCheckpoint
    from quadkit.workflow.execution.history import ExecutionHistory
    from quadkit.workflow.execution.runner import WorkflowRunner
    from quadkit.workflow.graph.builder import WorkflowBuilder
    from quadkit.workflow.graph.edge import WorkflowEdge
    from quadkit.workflow.graph.engine import WorkflowEngine
    from quadkit.workflow.graph.node import AbstractWorkflowNode, NodeType
    from quadkit.workflow.graph.state import WorkflowState
    from quadkit.workflow.module import WorkflowModule
    from quadkit.workflow.nodes.agent_node import AgentNode
    from quadkit.workflow.nodes.gate_node import GateNode
    from quadkit.workflow.nodes.human_node import HumanNode
    from quadkit.workflow.nodes.llm_node import LLMNode
    from quadkit.workflow.nodes.subworkflow_node import SubworkflowNode
    from quadkit.workflow.nodes.tool_node import ToolNode
    from quadkit.workflow.pipeline import (
        ConditionalStep,
        FunctionStep,
        ParallelStep,
        Pipeline,
        PipelineContext,
        PipelineStep,
        conditional,
        parallel,
        pipeline_step,
        step,
    )
    from quadkit.workflow.saga import (
        AbstractSaga,
        ContentAddressedSaga,
        ContentAddressedStage,
    )
    from quadkit.workflow.types import GraphResult, NodeResult

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # Bulk
    "BulkOperation": ("quadkit.workflow.bulk.operation", "BulkOperation"),
    "BulkBatchResult": ("quadkit.workflow.bulk.models", "BulkBatchResult"),
    "BulkItemError": ("quadkit.workflow.bulk.models", "BulkItemError"),
    "BulkOperationMetrics": ("quadkit.workflow.bulk.models", "BulkOperationMetrics"),
    "BulkOperationState": ("quadkit.workflow.bulk.models", "BulkOperationState"),
    # Pipeline
    "TransformPipe": ("quadkit.workflow.core.pipe", "TransformPipe"),
    # Core
    "WorkflowDefinition": ("quadkit.workflow.core.definition", "WorkflowDefinition"),
    "WorkflowInstance": ("quadkit.workflow.core.instance", "WorkflowInstance"),
    "ConditionalStep": ("quadkit.workflow.pipeline", "ConditionalStep"),
    "FunctionStep": ("quadkit.workflow.pipeline", "FunctionStep"),
    "ParallelStep": ("quadkit.workflow.pipeline", "ParallelStep"),
    "Pipeline": ("quadkit.workflow.pipeline", "Pipeline"),
    "PipelineContext": ("quadkit.workflow.pipeline", "PipelineContext"),
    "PipelineStep": ("quadkit.workflow.pipeline", "PipelineStep"),
    "conditional": ("quadkit.workflow.pipeline", "conditional"),
    "parallel": ("quadkit.workflow.pipeline", "parallel"),
    "pipeline_step": ("quadkit.workflow.pipeline", "pipeline_step"),
    "step": ("quadkit.workflow.pipeline", "step"),
    # SagaProtocol
    "AbstractSaga": ("quadkit.workflow.saga", "AbstractSaga"),
    "ContentAddressedSaga": ("quadkit.workflow.saga", "ContentAddressedSaga"),
    "ContentAddressedStage": ("quadkit.workflow.saga", "ContentAddressedStage"),
    # Types
    "SagaStep": ("quadkit.workflow.types", "SagaStep"),
    "StepExecutionResult": ("quadkit.workflow.types", "StepExecutionResult"),
    "StepStatus": ("quadkit.workflow.types", "StepStatus"),
    # Graph types
    "NodeResult": ("quadkit.workflow.types", "NodeResult"),
    "GraphResult": ("quadkit.workflow.types", "GraphResult"),
    # Graph config
    "GraphConfig": ("quadkit.workflow.config", "GraphConfig"),
    "BulkOperationConfig": ("quadkit.workflow.config", "BulkOperationConfig"),
    "ContentCheckpointConfig": ("quadkit.workflow.config", "ContentCheckpointConfig"),
    # Exceptions (existing)
    "BulkOperationCancelledError": (
        "quadkit.workflow.exceptions",
        "BulkOperationCancelledError",
    ),
    "BulkOperationError": ("quadkit.workflow.exceptions", "BulkOperationError"),
    "BulkOperationTimeoutError": (
        "quadkit.workflow.exceptions",
        "BulkOperationTimeoutError",
    ),
    "PipelineExecutionError": (
        "quadkit.workflow.exceptions",
        "PipelineExecutionError",
    ),
    "PipelineStepError": ("quadkit.workflow.exceptions", "PipelineStepError"),
    "WorkflowError": ("quadkit.workflow.exceptions", "WorkflowError"),
    "WorkflowNotFoundError": (
        "quadkit.workflow.exceptions",
        "WorkflowNotFoundError",
    ),
    "WorkflowStateError": ("quadkit.workflow.exceptions", "WorkflowStateError"),
    "WorkflowStepError": ("quadkit.workflow.exceptions", "WorkflowStepError"),
    "WorkflowTimeoutError": (
        "quadkit.workflow.exceptions",
        "WorkflowTimeoutError",
    ),
    "WorkflowCompensationError": (
        "quadkit.workflow.exceptions",
        "WorkflowCompensationError",
    ),
    # Graph exceptions
    "GraphExecutionError": ("quadkit.workflow.exceptions", "GraphExecutionError"),
    "NodeExecutionError": ("quadkit.workflow.exceptions", "NodeExecutionError"),
    "CycleDetectedError": ("quadkit.workflow.exceptions", "CycleDetectedError"),
    "GraphTimeoutError": ("quadkit.workflow.exceptions", "GraphTimeoutError"),
    "GraphValidationError": ("quadkit.workflow.exceptions", "GraphValidationError"),
    "HumanInputRequiredError": (
        "quadkit.workflow.exceptions",
        "HumanInputRequiredError",
    ),
    "WorkflowVersionMismatchError": (
        "quadkit.workflow.exceptions",
        "WorkflowVersionMismatchError",
    ),
    # Graph engine
    "WorkflowEngine": ("quadkit.workflow.graph.engine", "WorkflowEngine"),
    "WorkflowBuilder": ("quadkit.workflow.graph.builder", "WorkflowBuilder"),
    "WorkflowState": ("quadkit.workflow.graph.state", "WorkflowState"),
    "WorkflowEdge": ("quadkit.workflow.graph.edge", "WorkflowEdge"),
    "AbstractWorkflowNode": ("quadkit.workflow.graph.node", "AbstractWorkflowNode"),
    "NodeType": ("quadkit.workflow.graph.node", "NodeType"),
    # Nodes
    "AgentNode": ("quadkit.workflow.nodes.agent_node", "AgentNode"),
    "LLMNode": ("quadkit.workflow.nodes.llm_node", "LLMNode"),
    "ToolNode": ("quadkit.workflow.nodes.tool_node", "ToolNode"),
    "HumanNode": ("quadkit.workflow.nodes.human_node", "HumanNode"),
    "GateNode": ("quadkit.workflow.nodes.gate_node", "GateNode"),
    "SubworkflowNode": ("quadkit.workflow.nodes.subworkflow_node", "SubworkflowNode"),
    # Execution
    "WorkflowRunner": ("quadkit.workflow.execution.runner", "WorkflowRunner"),
    "WorkflowCheckpoint": (
        "quadkit.workflow.execution.checkpoint",
        "WorkflowCheckpoint",
    ),
    "ExecutionHistory": ("quadkit.workflow.execution.history", "ExecutionHistory"),
    # Checkpoint
    "InMemoryContentCheckpointStore": (
        "quadkit.workflow.checkpoint.store_memory",
        "InMemoryContentCheckpointStore",
    ),
    "CacheContentCheckpointStore": (
        "quadkit.workflow.checkpoint.store_cache",
        "CacheContentCheckpointStore",
    ),
    "DatabaseContentCheckpointStore": (
        "quadkit.workflow.checkpoint.store_database",
        "DatabaseContentCheckpointStore",
    ),
    # Decorators
    "workflow": ("quadkit.workflow.decorators", "workflow"),
    "saga_step": ("quadkit.workflow.decorators", "saga_step"),
    # DI
    "WorkflowModule": ("quadkit.workflow.module", "WorkflowModule"),
    "WorkflowProvider": ("quadkit.workflow.di.provider", "WorkflowProvider"),
    # Events
    "WorkflowStartedEvent": ("quadkit.workflow.events", "WorkflowStartedEvent"),
    "WorkflowCompletedEvent": ("quadkit.workflow.events", "WorkflowCompletedEvent"),
    "WorkflowFailedEvent": ("quadkit.workflow.events", "WorkflowFailedEvent"),
    # Hooks
    "WorkflowCompletedHook": ("quadkit.workflow.hooks", "WorkflowCompletedHook"),
    "WorkflowStartedHook": ("quadkit.workflow.hooks", "WorkflowStartedHook"),
    "WorkflowStateTransitionedHook": (
        "quadkit.workflow.hooks",
        "WorkflowStateTransitionedHook",
    ),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path)
        value = getattr(module, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(_LAZY_IMPORTS.keys()))


__all__ = [
    "AbstractSaga",
    "AbstractWorkflowNode",
    "AgentNode",
    "BulkBatchResult",
    "BulkItemError",
    "BulkOperation",
    "BulkOperationCancelledError",
    "BulkOperationConfig",
    "BulkOperationError",
    "BulkOperationMetrics",
    "BulkOperationState",
    "BulkOperationTimeoutError",
    "CacheContentCheckpointStore",
    "ConditionalStep",
    "ContentAddressedSaga",
    "ContentAddressedStage",
    "ContentCheckpointConfig",
    "CycleDetectedError",
    "DatabaseContentCheckpointStore",
    "ExecutionHistory",
    "FunctionStep",
    "GateNode",
    "GraphConfig",
    "GraphExecutionError",
    "GraphResult",
    "GraphTimeoutError",
    "GraphValidationError",
    "HumanInputRequiredError",
    "HumanNode",
    "InMemoryContentCheckpointStore",
    "LLMNode",
    "NodeExecutionError",
    "NodeResult",
    "NodeType",
    "ParallelStep",
    "Pipeline",
    "PipelineContext",
    "PipelineExecutionError",
    "PipelineStep",
    "PipelineStepError",
    "SagaStep",
    "StepExecutionResult",
    "StepStatus",
    "SubworkflowNode",
    "ToolNode",
    "TransformPipe",
    "WorkflowBuilder",
    "WorkflowCheckpoint",
    "WorkflowCompensationError",
    "WorkflowCompletedEvent",
    "WorkflowCompletedHook",
    "WorkflowDefinition",
    "WorkflowEdge",
    "WorkflowEngine",
    "WorkflowError",
    "WorkflowFailedEvent",
    "WorkflowInstance",
    "WorkflowModule",
    "WorkflowNotFoundError",
    "WorkflowProvider",
    "WorkflowRunner",
    "WorkflowStartedEvent",
    "WorkflowStartedHook",
    "WorkflowState",
    "WorkflowStateError",
    "WorkflowStateTransitionedHook",
    "WorkflowStepError",
    "WorkflowTimeoutError",
    "WorkflowVersionMismatchError",
    "conditional",
    "parallel",
    "pipeline_step",
    "saga_step",
    "step",
    "workflow",
]
