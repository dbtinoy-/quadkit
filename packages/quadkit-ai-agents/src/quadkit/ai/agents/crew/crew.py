"""Crew and CrewTask value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.ai.agents.crew.builder import CrewBuilder

from quadkit.ai.agents.crew.process import Process


@dataclass(frozen=True)
class CrewTask:
    """A task to be executed by a crew member.

    Attributes:
        name: Task identifier.
        description: What this task should accomplish.
        expected_output: Optional description of expected output format.
        context_tasks: List of task names whose outputs should be available
            as context when executing this task.
    """

    name: str
    description: str
    expected_output: str | None = None
    context_tasks: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Crew:
    """A crew of agents executing tasks.

    Attributes:
        agents: List of agents participating in this crew.
        tasks: List of tasks to be executed.
        process: Execution process (sequential or hierarchical). Defaults to SEQUENTIAL.
    """

    agents: list[Any]
    tasks: list[CrewTask]
    process: Process = Process.SEQUENTIAL

    @classmethod
    def builder(cls) -> CrewBuilder:
        """Create a CrewBuilder for fluent crew construction.

        Returns:
            A CrewBuilder instance.

        Example::

            crew = (
                Crew.builder()
                .add_agent(agent1)
                .add_task(task1)
                .process(Process.SEQUENTIAL)
                .build()
            )
        """
        from quadkit.ai.agents.crew.builder import CrewBuilder

        return CrewBuilder()
