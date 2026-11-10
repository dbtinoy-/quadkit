"""CrewBuilder - fluent API for creating crews."""

from __future__ import annotations

from typing import Any, Self

from quadkit.ai.agents.crew.crew import Crew, CrewTask
from quadkit.ai.agents.crew.process import Process


class CrewBuilder:
    """Fluent builder for creating crews programmatically.

    Example::

        crew = (
            CrewBuilder()
            .add_agent(researcher)
            .add_agent(reporter)
            .add_task(CrewTask(name="research", description="Research X"))
            .add_task(CrewTask(name="report", description="Write report"))
            .process(Process.SEQUENTIAL)
            .build()
        )
    """

    def __init__(self) -> None:
        self._agents: list[Any] = []
        self._tasks: list[CrewTask] = []
        self._process: Process = Process.SEQUENTIAL

    def add_agent(self, agent: Any) -> Self:
        """Add an agent to the crew."""
        self._agents.append(agent)
        return self

    def add_task(self, task: CrewTask) -> Self:
        """Add a task to the crew."""
        self._tasks.append(task)
        return self

    def process(self, process: Process) -> Self:
        """Set the execution process."""
        self._process = process
        return self

    def build(self) -> Crew:
        """Build and return the crew."""
        return Crew(
            agents=list(self._agents),
            tasks=list(self._tasks),
            process=self._process,
        )
