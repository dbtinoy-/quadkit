"""Root hook payload surface for quadkit-workflow.

Defines canonical payload dataclasses for workflow orchestration lifecycle hook
points. Actual hook registration and invocation use the framework's string-keyed
``HookRegistryProtocol`` action/filter APIs.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "WorkflowCompletedHook",
    "WorkflowStartedHook",
    "WorkflowStateTransitionedHook",
]


@dataclass(frozen=True, kw_only=True)
class WorkflowStartedHook:
    """Payload fired when a workflow instance begins execution.

    Attributes:
        workflow_id: Unique identifier of the workflow instance.
        workflow_type: Type or name of the workflow definition.
    """

    workflow_id: str
    workflow_type: str


@dataclass(frozen=True, kw_only=True)
class WorkflowStateTransitionedHook:
    """Payload fired when a workflow instance transitions between states.

    Attributes:
        workflow_id: Unique identifier of the workflow instance.
        from_state: State name being exited.
        to_state: State name being entered.
    """

    workflow_id: str
    from_state: str
    to_state: str


@dataclass(frozen=True, kw_only=True)
class WorkflowCompletedHook:
    """Payload fired when a workflow instance reaches a terminal state.

    Attributes:
        workflow_id: Unique identifier of the workflow instance.
        workflow_type: Type or name of the workflow definition.
        succeeded: ``True`` if the workflow completed successfully.
    """

    workflow_id: str
    workflow_type: str
    succeeded: bool
