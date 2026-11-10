"""Workflow definition — versioned descriptor for a workflow graph.

A :class:`WorkflowDefinition` is an immutable, named, versioned descriptor
that describes the shape of a workflow.  The ``version`` field must be
incremented whenever the definition structure changes in a way that would be
incompatible with already-running instances.

Example::

    from quadkit.workflow.core.definition import WorkflowDefinition

    defn = WorkflowDefinition(name="onboarding", steps=[], version=2)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class WorkflowDefinition:
    """Immutable, versioned descriptor for a workflow.

    Args:
        name: Unique workflow name.
        steps: Ordered list of step descriptors (opaque; interpreted by the
            executor).  Defaults to an empty list for graph-based workflows
            where nodes/edges are the canonical step representation.
        version: Definition schema version.  Increment this whenever the
            definition structure changes incompatibly.  Defaults to ``1``.
    """

    name: str
    steps: list[Any] = field(default_factory=list)
    version: int = 1


__all__ = ["WorkflowDefinition"]
