"""CLI contributor exports for the quadkit-tasks package."""

from __future__ import annotations

from quadkit.tasks.cli.contributor import TasksCliContributor
from quadkit.tasks.cli.generators.task import TaskGenerator

__all__ = ["TaskGenerator", "TasksCliContributor"]
