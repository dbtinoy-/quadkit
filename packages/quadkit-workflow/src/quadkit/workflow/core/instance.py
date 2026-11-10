"""Workflow instance — tracks a running workflow against a specific definition version.

A :class:`WorkflowInstance` is created at workflow-start time and records the
:attr:`WorkflowDefinition.version` it was started under.  Before resuming
execution the runner calls :meth:`WorkflowInstance.validate_definition_version`
to detect incompatible definition changes before any step executes.

Example::

    from quadkit.workflow.core.definition import WorkflowDefinition
    from quadkit.workflow.core.instance import WorkflowInstance

    defn = WorkflowDefinition(name="onboarding", steps=[], version=1)
    instance = WorkflowInstance.create(definition=defn)

    # Later, on resume:
    new_defn = WorkflowDefinition(name="onboarding", steps=[], version=2)
    instance.validate_definition_version(new_defn)  # raises WorkflowVersionMismatchError
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from quadkit.workflow.core.definition import WorkflowDefinition


@dataclass
class WorkflowInstance:
    """A single running (or paused) execution of a workflow definition.

    Args:
        instance_id: Unique identifier for this execution.
        workflow_name: Name of the workflow definition this instance belongs to.
        definition_version: The :attr:`WorkflowDefinition.version` recorded at
            instance-creation time.  Used to detect incompatible definition
            changes on resume.
    """

    instance_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_name: str = ""
    definition_version: int = 1

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(cls, definition: WorkflowDefinition) -> WorkflowInstance:
        """Create a new instance stamped with *definition*'s version.

        Args:
            definition: The workflow definition being started.

        Returns:
            A new :class:`WorkflowInstance` whose
            :attr:`definition_version` matches ``definition.version``.
        """
        return cls(
            instance_id=str(uuid.uuid4()),
            workflow_name=definition.name,
            definition_version=definition.version,
        )

    # ------------------------------------------------------------------
    # Version guard
    # ------------------------------------------------------------------

    def validate_definition_version(self, definition: WorkflowDefinition) -> None:
        """Raise if *definition*'s version differs from the one this instance was started under.

        Call this before executing any step when resuming a non-new instance
        to prevent silently running stale or incompatible steps.

        Args:
            definition: The workflow definition being used to resume this
                instance.

        Raises:
            WorkflowVersionMismatchError: If ``definition.version`` differs
                from the version recorded at instance creation.
        """
        if definition.version != self.definition_version:
            from quadkit.workflow.exceptions import WorkflowVersionMismatchError

            raise WorkflowVersionMismatchError(
                workflow_name=definition.name,
                expected_version=self.definition_version,
                actual_version=definition.version,
            )


__all__ = ["WorkflowInstance"]
