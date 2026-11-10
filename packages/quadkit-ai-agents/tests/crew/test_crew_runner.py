"""Tests for CrewRunner."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.agents.crew import Crew, CrewBuilder, CrewTask, Process


class TestCrewRunner:
    """Test CrewRunner execution."""

    @pytest.fixture
    def mock_agent(self) -> MagicMock:
        """Create a mock agent."""
        agent = MagicMock()
        agent.name = "test_agent"
        return agent

    @pytest.mark.asyncio
    async def test_crew_builder_method(self, mock_agent: MagicMock) -> None:
        """Crew has a builder() classmethod."""
        crew = Crew.builder().add_agent(mock_agent).build()
        assert isinstance(crew, Crew)
        assert len(crew.agents) == 1

    @pytest.mark.asyncio
    async def test_sequential_runs_tasks_in_order(self) -> None:
        """Sequential process runs tasks one after another."""
        from quadkit.ai.agents.crew import CrewRunner

        agent = MagicMock()
        agent.name = "agent1"

        task1 = CrewTask(name="task1", description="First task")
        task2 = CrewTask(name="task2", description="Second task")

        crew = Crew(
            agents=[agent],
            tasks=[task1, task2],
            process=Process.SEQUENTIAL,
        )

        from quadkit.contracts.ai.agents import AgentResponse

        response1 = AgentResponse(message="task1 result")
        response2 = AgentResponse(message="task2 result")

        agent.run = AsyncMock(side_effect=[response1, response2])

        runner = CrewRunner()
        result = await runner.run(crew, "test input")

        assert result is not None
        assert len(result.task_results) == 2
        assert agent.run.call_count == 2

    @pytest.mark.asyncio
    async def test_task_logs_omit_agent_task_and_exception_details(
        self, monkeypatch
    ) -> None:
        """Crew logs retain exception type but not private identifiers or text."""
        from quadkit.ai.agents.crew import CrewRunner
        import quadkit.ai.agents.crew.runner as runner_module

        private_agent = "private-agent-tenant-42"
        private_task = "private-task-tenant-42"
        private_error = "token=secret at /srv/private/tenant-42"
        logger = MagicMock()
        monkeypatch.setattr(runner_module, "logger", logger)

        agent = MagicMock()
        agent.name = private_agent
        agent.run = AsyncMock(side_effect=RuntimeError(private_error))
        task = CrewTask(name=private_task, description="Private task input")
        crew = Crew(agents=[agent], tasks=[task], process=Process.SEQUENTIAL)

        result = await CrewRunner().run(crew, "private input")

        captured = repr(logger.mock_calls)
        assert "crew_task_started" in captured
        assert "crew_task_failed" in captured
        assert "RuntimeError" in captured
        for private_value in (
            private_agent,
            private_task,
            private_error,
            "/srv/private/tenant-42",
        ):
            assert private_value not in captured
        assert result.task_results[0].error == "Task failed (RuntimeError)"

    @pytest.mark.asyncio
    async def test_sequential_passes_context_to_later_tasks(self) -> None:
        """Sequential process passes prior task outputs to later tasks."""
        from quadkit.ai.agents.crew import CrewRunner

        agent = MagicMock()
        agent.name = "agent1"

        task1 = CrewTask(name="task1", description="First task")
        task2 = CrewTask(
            name="task2",
            description="Second task",
            context_tasks=["task1"],
        )

        crew = Crew(
            agents=[agent],
            tasks=[task1, task2],
            process=Process.SEQUENTIAL,
        )

        from quadkit.contracts.ai.agents import AgentResponse

        response1 = AgentResponse(message="task1 result")
        response2 = AgentResponse(message="task2 result")

        agent.run = AsyncMock(side_effect=[response1, response2])

        runner = CrewRunner()
        result = await runner.run(crew, "test input")

        assert result is not None
        call_args = agent.run.call_args_list[1]
        context = call_args[1].get("context", {})
        assert "task_results" in context
        assert "task1" in context["task_results"]


class TestCrewBuilderMethod:
    """Test Crew.builder() convenience method."""

    def test_builder_returns_builder_instance(self) -> None:
        """Crew.builder() returns a CrewBuilder instance."""
        builder = Crew.builder()
        from quadkit.ai.agents.crew.builder import CrewBuilder

        assert isinstance(builder, CrewBuilder)

    def test_builder_fluent_api(self) -> None:
        """Crew.builder() supports fluent API."""
        agent = MagicMock()
        agent.name = "test_agent"
        task = CrewTask(name="task1", description="Do something")

        crew = (
            Crew.builder()
            .add_agent(agent)
            .add_task(task)
            .process(Process.SEQUENTIAL)
            .build()
        )

        assert isinstance(crew, Crew)
        assert len(crew.agents) == 1
        assert len(crew.tasks) == 1
        assert crew.process == Process.SEQUENTIAL

    def test_builder_default_process_is_sequential(self) -> None:
        """Crew.builder() defaults to sequential process."""
        agent = MagicMock()
        agent.name = "test_agent"

        crew = Crew.builder().add_agent(agent).build()

        assert crew.process == Process.SEQUENTIAL
