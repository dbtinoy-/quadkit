"""Exceptions for the execution subsystem.

Re-exports pipeline exceptions from contracts and bulk-operation exceptions
from the bulk module so callers have a single import location.

Provides workflow-native exceptions for orchestration errors, state management,
and step execution failures.  Also provides the graph engine exception hierarchy
for directed-graph workflow execution.
"""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions.base import QuadkitError
from quadkit.contracts.exceptions.execution import (
    PipelineExecutionError as PipelineExecutionError,  # re-export
)
from quadkit.contracts.exceptions.execution import (
    PipelineStepError as PipelineStepError,  # re-export
)
from quadkit.workflow.bulk import (
    BulkOperationCancelledError as BulkOperationCancelledError,  # re-export
)
from quadkit.workflow.bulk import (
    BulkOperationError as BulkOperationError,  # re-export
)
from quadkit.workflow.bulk import (
    BulkOperationTimeoutError as BulkOperationTimeoutError,  # re-export
)

# --- Workflow-native leaf exceptions ---


class WorkflowError(PipelineExecutionError):
    """Base exception for workflow orchestration errors."""

    _code = "QK_ERR_WF_003"

    def __init__(self, message: str = "Workflow error", **kwargs: Any) -> None:
        if "step_name" not in kwargs:
            kwargs["step_name"] = "workflow"
        if "error" not in kwargs:
            kwargs["error"] = Exception(message)
        super().__init__(**kwargs)
        self.step_name = kwargs.get("step_name", "workflow")


class WorkflowNotFoundError(WorkflowError):
    """Raised when a workflow definition cannot be found."""

    _code = "QK_ERR_WF_004"

    def __init__(self, workflow_id: str) -> None:
        super().__init__("Workflow not found.")
        self.workflow_id = workflow_id


class WorkflowStateError(WorkflowError):
    """Raised when a workflow is in an invalid state for the requested operation."""

    _code = "QK_ERR_WF_005"


class WorkflowStepError(WorkflowError):
    """Raised when a workflow step fails to execute."""

    _code = "QK_ERR_WF_006"

    def __init__(self, step_name: str, reason: str) -> None:
        super().__init__("Workflow step failed.")
        self.step_name = step_name
        self.reason = "Workflow step failed."


class WorkflowTimeoutError(WorkflowError):
    """Raised when a workflow or step exceeds its timeout."""

    _code = "QK_ERR_WF_007"


class WorkflowCompensationError(WorkflowError):
    """Raised when workflow compensation/rollback fails."""

    _code = "QK_ERR_WF_008"


class WorkflowVersionMismatchError(WorkflowError):
    """Raised when resuming a workflow instance with a mismatched definition version.

    Resuming an in-flight instance with an incompatible definition version
    would silently execute stale steps or skip newly-added ones.  This error
    forces callers to either migrate the instance or restart it under the new
    definition.

    Args:
        workflow_name: Name of the workflow definition.
        expected_version: Version stored in the running instance (set at
            creation time).
        actual_version: Version of the definition currently being used to
            resume the instance.
    """

    _code = "QK_ERR_WF_010"

    def __init__(
        self,
        workflow_name: str,
        expected_version: int,
        actual_version: int,
    ) -> None:
        super().__init__(
            step_name="workflow",
            error=Exception(
                "Workflow definition changed; migrate or restart the instance."
            ),
        )
        self.workflow_name = workflow_name
        self.expected_version = expected_version
        self.actual_version = actual_version


# --- Graph Engine Exceptions ---


class GraphExecutionError(QuadkitError):
    """Base exception for graph workflow engine operations.

    Args:
        message: Human-readable error description.
        node: Optional name of the node where the error occurred.
    """

    _code: str = "QK_ERR_WF_011"

    def __init__(self, message: str, *, node: str | None = None) -> None:
        self.node = node
        super().__init__(message)


class NodeExecutionError(GraphExecutionError):
    """A graph node's execute() method failed.

    Args:
        message: Human-readable error description.
        node: Name of the failing node.
        cause: Optional underlying exception.
    """

    _code: str = "QK_ERR_WF_012"

    def __init__(
        self,
        message: str,
        *,
        node: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        self.cause = cause
        super().__init__(message, node=node)
        if cause is not None:
            self.__cause__ = cause


class CycleDetectedError(GraphExecutionError):
    """Graph engine exceeded max_iterations (likely cycle).

    Args:
        iterations: Number of iterations completed before the limit.
        node: Name of the node that was about to execute again.
    """

    _code: str = "QK_ERR_WF_013"

    def __init__(self, iterations: int, *, node: str | None = None) -> None:
        self.iterations = iterations
        super().__init__(
            "Workflow exceeded the maximum iteration limit.",
            node=node,
        )


class GraphTimeoutError(GraphExecutionError):
    """Graph workflow execution exceeded total timeout.

    Args:
        timeout: The configured timeout value in seconds.
    """

    _code: str = "QK_ERR_WF_014"

    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        super().__init__(f"Graph workflow timed out after {timeout}s")


class GraphValidationError(GraphExecutionError):
    """Graph structure validation failed."""

    _code: str = "QK_ERR_WF_015"


class HumanInputRequiredError(GraphExecutionError):
    """Raised by HumanNode to pause execution awaiting human input.

    Args:
        prompt: Text/question to display to the human operator.
        node: Node that triggered the pause.
        checkpoint_id: Identifier for the stored checkpoint.
    """

    _code: str = "QK_ERR_WF_016"

    def __init__(
        self,
        prompt: str,
        *,
        node: str | None = None,
        checkpoint_id: str | None = None,
    ) -> None:
        self.prompt = prompt
        self.checkpoint_id = checkpoint_id
        super().__init__("Human input is required.", node=node)


__all__ = [
    "BulkOperationCancelledError",
    "BulkOperationError",
    "BulkOperationTimeoutError",
    "CycleDetectedError",
    "GraphExecutionError",
    "GraphTimeoutError",
    "GraphValidationError",
    "HumanInputRequiredError",
    "NodeExecutionError",
    "PipelineExecutionError",
    "PipelineStepError",
    "WorkflowCompensationError",
    "WorkflowError",
    "WorkflowNotFoundError",
    "WorkflowStateError",
    "WorkflowStepError",
    "WorkflowTimeoutError",
    "WorkflowVersionMismatchError",
]
