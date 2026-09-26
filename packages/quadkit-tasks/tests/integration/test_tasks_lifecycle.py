"""Integration tests for quadkit-tasks package."""

from __future__ import annotations

import pytest

from quadkit.tasks.backends.memory import MemoryTaskQueue
from quadkit.tasks.config import TaskConfig
from quadkit.tasks.di.provider import TaskProvider


class TestTasksProviderIntegration:
    """Integration tests for TaskProvider basic functionality."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_provider_initialization_default(self):
        """Test TaskProvider initialization with queue."""
        queue = MemoryTaskQueue()
        provider = TaskProvider(queue=queue)
        assert provider.name == "tasks"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_provider_initialization_from_config(self):
        """Test TaskProvider initialization from config."""
        config = TaskConfig()
        provider = TaskProvider.from_config(config)
        assert provider.name == "tasks"

    @pytest.mark.integration
    def test_provider_has_required_attributes(self):
        """Test provider has required attributes."""
        queue = MemoryTaskQueue()
        provider = TaskProvider(queue=queue)
        assert hasattr(provider, "name")
        assert hasattr(provider, "queue")

    @pytest.mark.integration
    def test_provider_priority(self):
        """Test provider has correct priority."""
        from quadkit.contracts.core.provider import ProviderPriority
        queue = MemoryTaskQueue()
        provider = TaskProvider(queue=queue)
        assert provider.priority == ProviderPriority.INFRASTRUCTURE


class TestTaskConfigIntegration:
    """Integration tests for TaskConfig."""

    @pytest.mark.integration
    def test_task_config_creation(self):
        """Test TaskConfig can be created."""
        config = TaskConfig()
        assert config is not None

    @pytest.mark.integration
    def test_task_config_model_dump(self):
        """Test TaskConfig model can be serialized."""
        config = TaskConfig()
        config_dict = config.model_dump()
        assert isinstance(config_dict, dict)


class TestTasksModuleIntegration:
    """Integration tests for TasksModule."""

    @pytest.mark.integration
    def test_tasks_module_import(self):
        """Test TasksModule can be imported."""
        from quadkit.tasks.module import TasksModule
        assert TasksModule is not None

    @pytest.mark.integration
    def test_tasks_module_has_configure_method(self):
        """Test TasksModule has configure method."""
        from quadkit.tasks.module import TasksModule
        assert hasattr(TasksModule, "configure")


class TestTasksBackendsIntegration:
    """Integration tests for tasks backends."""

    @pytest.mark.integration
    def test_memory_backend_import(self):
        """Test MemoryTaskQueue can be imported."""
        from quadkit.tasks.backends.memory import MemoryTaskQueue
        assert MemoryTaskQueue is not None