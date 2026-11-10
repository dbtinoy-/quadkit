from __future__ import annotations

from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock

import pytest


class TestProcess:
    """Test Process enum."""

    def test_process_enum_values(self) -> None:
        """Process enum has sequential and hierarchical values."""
        from quadkit.ai.agents.crew import Process

        assert Process.SEQUENTIAL == "sequential"
        assert Process.HIERARCHICAL == "hierarchical"

    def test_process_is_str_enum(self) -> None:
        """Process is a string enum."""
        from quadkit.ai.agents.crew import Process

        assert isinstance(Process.SEQUENTIAL, str)


class TestCrewTask:
    """Test CrewTask value object."""

    def test_crewtask_required_fields(self) -> None:
        """CrewTask requires name and description."""
        from quadkit.ai.agents.crew import CrewTask

        task = CrewTask(name="task1", description="Do something")
        assert task.name == "task1"
        assert task.description == "Do something"

    def test_crewtask_optional_fields(self) -> None:
        """CrewTask accepts optional expected_output and context_tasks."""
        from quadkit.ai.agents.crew import CrewTask

        task = CrewTask(
            name="task1",
            description="Do something",
            expected_output="A summary",
            context_tasks=["prior_task_1", "prior_task_2"],
        )
        assert task.expected_output == "A summary"
        assert task.context_tasks == ["prior_task_1", "prior_task_2"]

    def test_crewtask_defaults(self) -> None:
        """CrewTask has sensible defaults."""
        from quadkit.ai.agents.crew import CrewTask

        task = CrewTask(name="task1", description="Do something")
        assert task.expected_output is None
        assert task.context_tasks == []

    def test_crewtask_is_frozen(self) -> None:
        """CrewTask is immutable."""
        from quadkit.ai.agents.crew import CrewTask

        task = CrewTask(name="task1", description="Do something")
        with pytest.raises((TypeError, FrozenInstanceError)):
            task.name = "new_name"  # type: ignore[assignment]

    def test_crewtask_is_dataclass(self) -> None:
        """CrewTask is a frozen dataclass."""
        from quadkit.ai.agents.crew import CrewTask

        assert hasattr(CrewTask, "__dataclass_fields__")


class TestCrew:
    """Test Crew value object."""

    @pytest.fixture
    def mock_agent(self) -> MagicMock:
        """Create a mock agent."""
        agent = MagicMock()
        agent.name = "test_agent"
        return agent

    def test_crew_required_fields(self, mock_agent: MagicMock) -> None:
        """Crew requires agents and tasks."""
        from quadkit.ai.agents.crew import Crew, CrewTask

        task = CrewTask(name="task1", description="Do something")
        crew = Crew(agents=[mock_agent], tasks=[task])
        assert len(crew.agents) == 1
        assert len(crew.tasks) == 1

    def test_crew_all_fields(self, mock_agent: MagicMock) -> None:
        """Crew accepts all fields including process."""
        from quadkit.ai.agents.crew import Crew, CrewTask, Process

        task = CrewTask(name="task1", description="Do something")
        crew = Crew(
            agents=[mock_agent],
            tasks=[task],
            process=Process.HIERARCHICAL,
        )
        assert crew.process == Process.HIERARCHICAL

    def test_crew_process_default(self, mock_agent: MagicMock) -> None:
        """Crew defaults to sequential process."""
        from quadkit.ai.agents.crew import Crew, CrewTask, Process

        task = CrewTask(name="task1", description="Do something")
        crew = Crew(agents=[mock_agent], tasks=[task])
        assert crew.process == Process.SEQUENTIAL

    def test_crew_is_frozen(self, mock_agent: MagicMock) -> None:
        """Crew is immutable."""
        from quadkit.ai.agents.crew import Crew, CrewTask

        task = CrewTask(name="task1", description="Do something")
        crew = Crew(agents=[mock_agent], tasks=[task])
        with pytest.raises((TypeError, FrozenInstanceError)):
            crew.agents = []  # type: ignore[assignment]


class TestCrewBuilder:
    """Test CrewBuilder fluent API."""

    def test_builder_create(self) -> None:
        """CrewBuilder can be created."""
        from quadkit.ai.agents.crew import CrewBuilder

        builder = CrewBuilder()
        assert builder is not None

    def test_builder_add_agent(self) -> None:
        """Builder can add an agent."""
        from quadkit.ai.agents.crew import CrewBuilder

        agent = MagicMock()
        agent.name = "test_agent"

        builder = CrewBuilder()
        result = builder.add_agent(agent)
        assert result is builder

    def test_builder_add_task(self) -> None:
        """Builder can add a task."""
        from quadkit.ai.agents.crew import CrewBuilder, CrewTask

        task = CrewTask(name="task1", description="Do something")

        builder = CrewBuilder()
        result = builder.add_task(task)
        assert result is builder

    def test_builder_process(self) -> None:
        """Builder can set process."""
        from quadkit.ai.agents.crew import CrewBuilder, Process

        builder = CrewBuilder()
        result = builder.process(Process.HIERARCHICAL)
        assert result is builder

    def test_builder_build(self) -> None:
        """Builder builds a Crew."""
        from quadkit.ai.agents.crew import Crew, CrewBuilder, CrewTask, Process

        agent = MagicMock()
        agent.name = "test_agent"
        task = CrewTask(name="task1", description="Do something")
        crew = (
            CrewBuilder()
            .add_agent(agent)
            .add_task(task)
            .process(Process.SEQUENTIAL)
            .build()
        )
        assert isinstance(crew, Crew)
        assert len(crew.agents) == 1
        assert len(crew.tasks) == 1
        assert crew.process == Process.SEQUENTIAL

    def test_builder_sequential_is_default(self) -> None:
        """Builder defaults to sequential process."""
        from quadkit.ai.agents.crew import CrewBuilder, Process

        agent = MagicMock()
        agent.name = "test_agent"
        crew = CrewBuilder().add_agent(agent).build()
        assert crew.process == Process.SEQUENTIAL


class TestCrewExecutionResult:
    """Test CrewExecutionResult value object."""

    def test_execution_result_basic(self) -> None:
        """CrewExecutionResult has required fields."""
        from quadkit.ai.agents.crew.runner import CrewExecutionResult

        result = CrewExecutionResult(
            task_results=[],
            final_output="result",
        )
        assert result.final_output == "result"
        assert result.task_results == []

    def test_execution_result_with_task_results(self) -> None:
        """CrewExecutionResult tracks task results."""
        from quadkit.ai.agents.crew.runner import CrewExecutionResult, TaskResult

        task_result = TaskResult(
            task_name="task1",
            output="output",
            agent_name="agent1",
            success=True,
        )
        result = CrewExecutionResult(
            task_results=[task_result],
            final_output="final",
        )
        assert len(result.task_results) == 1
        assert result.final_output == "final"


class TestTaskResult:
    """Test TaskResult value object."""

    def test_task_result_basic(self) -> None:
        """TaskResult has required fields."""
        from quadkit.ai.agents.crew.runner import TaskResult

        result = TaskResult(
            task_name="task1",
            output="task output",
            agent_name="agent1",
            success=True,
        )
        assert result.task_name == "task1"
        assert result.output == "task output"
        assert result.agent_name == "agent1"
        assert result.success is True

    def test_task_result_with_error(self) -> None:
        """TaskResult accepts error."""
        from quadkit.ai.agents.crew.runner import TaskResult

        result = TaskResult(
            task_name="task1",
            output="",
            agent_name="agent1",
            success=False,
            error="task failed",
        )
        assert result.error == "task failed"
        assert result.success is False
