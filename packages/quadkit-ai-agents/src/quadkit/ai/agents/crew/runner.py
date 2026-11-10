"""CrewRunner - executes crew tasks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quadkit.ai.agents.crew.crew import Crew, CrewTask
from quadkit.ai.agents.crew.process import Process
from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)


@dataclass
class TaskResult:
    """Result of executing a single crew task."""

    task_name: str
    output: str
    agent_name: str
    success: bool
    error: str | None = None


@dataclass
class CrewExecutionResult:
    """Result of executing a crew."""

    task_results: list[TaskResult] = field(default_factory=list)
    final_output: str | None = None


class CrewRunner:
    """Executes crew tasks using the specified process.

    Supports sequential (tasks run one after another) and hierarchical
    (manager assigns tasks to workers) execution modes.
    """

    async def run(
        self,
        crew: Crew,
        input_text: str,
        context: dict[str, Any] | None = None,
    ) -> CrewExecutionResult:
        """Execute the crew with the given input.

        Args:
            crew: The crew to execute.
            input_text: The input query or task description.
            context: Optional context dict for passing prior task outputs.

        Returns:
            CrewExecutionResult containing all task results.
        """
        context = context or {}

        if crew.process == Process.SEQUENTIAL:
            return await self._run_sequential(crew, input_text, context)
        if crew.process == Process.HIERARCHICAL:
            return await self._run_hierarchical(crew, input_text, context)
        raise ValueError(f"Unknown process type: {crew.process}")

    async def _run_sequential(
        self,
        crew: Crew,
        input_text: str,
        initial_context: dict[str, Any],
    ) -> CrewExecutionResult:
        """Execute tasks sequentially.

        Each task runs after the previous one completes, with access to
        prior task outputs through the context.
        """
        task_results: list[TaskResult] = []
        context = dict(initial_context)

        for task in crew.tasks:
            logger.info("crew_task_started")

            agent = self._select_agent_for_task(crew.agents, task)

            try:
                task_context = self._build_task_context(task, context)

                response = await agent.run(
                    input=task.description,
                    context=task_context,
                )

                task_result = TaskResult(
                    task_name=task.name,
                    output=response.message,
                    agent_name=agent.name,
                    success=True,
                )
                task_results.append(task_result)

                context[task.name] = response.message

                logger.info("crew_task_completed")

            except Exception as exc:
                error_type = type(exc).__name__
                logger.error(
                    "crew_task_failed",
                    error_type=error_type,
                )
                task_results.append(
                    TaskResult(
                        task_name=task.name,
                        output="",
                        agent_name=agent.name,
                        success=False,
                        error=f"Task failed ({error_type})",
                    )
                )

        final_output = task_results[-1].output if task_results else None

        return CrewExecutionResult(
            task_results=task_results,
            final_output=final_output,
        )

    async def _run_hierarchical(
        self,
        crew: Crew,
        input_text: str,
        initial_context: dict[str, Any],
    ) -> CrewExecutionResult:
        """Execute tasks hierarchically with a manager agent.

        The first agent is used as the manager to assign tasks to worker agents.
        """
        if not crew.agents:
            raise ValueError("Crew must have at least one agent")

        manager = crew.agents[0]
        workers = crew.agents[1:] if len(crew.agents) > 1 else crew.agents
        task_results: list[TaskResult] = []

        logger.info("crew_hierarchical_start")

        response = await manager.run(
            input=input_text,
            context=initial_context,
        )

        for task in crew.tasks:
            worker = self._select_agent_for_task(workers, task)

            try:
                task_response = await worker.run(
                    input=task.description,
                    context={"input": input_text, "manager_response": response.message},
                )

                task_results.append(
                    TaskResult(
                        task_name=task.name,
                        output=task_response.message,
                        agent_name=worker.name,
                        success=True,
                    )
                )

            except Exception as exc:
                error_type = type(exc).__name__
                logger.error(
                    "crew_task_failed",
                    error_type=error_type,
                )
                task_results.append(
                    TaskResult(
                        task_name=task.name,
                        output="",
                        agent_name=worker.name,
                        success=False,
                        error=f"Task failed ({error_type})",
                    )
                )

        final_output = task_results[-1].output if task_results else None

        return CrewExecutionResult(
            task_results=task_results,
            final_output=final_output,
        )

    def _select_agent_for_task(
        self,
        agents: list[Any],
        task: CrewTask,
    ) -> Any:
        """Select an agent to execute a task.

        For now, returns the first available agent. A more sophisticated
        implementation could use task requirements to select the best agent.
        """
        if not agents:
            raise ValueError("No agents available for task execution")
        return agents[0]

    def _build_task_context(
        self,
        task: CrewTask,
        prior_outputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Build context for a task based on its context_tasks.

        Args:
            task: The task to build context for.
            prior_outputs: Dict of prior task outputs by name.

        Returns:
            Context dict including prior task outputs.
        """
        context: dict[str, Any] = {}

        if task.context_tasks:
            context["task_results"] = {
                name: output
                for name, output in prior_outputs.items()
                if name in task.context_tasks
            }

        return context
