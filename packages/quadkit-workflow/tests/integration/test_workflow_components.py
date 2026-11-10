"""Integration tests for quadkit-workflow package lifecycle."""

from __future__ import annotations

import pytest

from quadkit.workflow.config import BulkOperationConfig
from quadkit.workflow.di.provider import WorkflowProvider


class TestWorkflowProviderIntegration:
    """Integration tests for WorkflowProvider basic functionality."""

    @pytest.mark.integration
    def test_provider_initialization_default(self):
        """Test WorkflowProvider initialization with default config."""
        provider = WorkflowProvider()
        assert provider.name == "workflow"

    @pytest.mark.integration
    def test_provider_initialization_with_config(self):
        """Test WorkflowProvider initialization with custom config."""
        config = BulkOperationConfig()
        provider = WorkflowProvider(config=config)
        assert provider.name == "workflow"

    @pytest.mark.integration
    def test_provider_has_required_attributes(self):
        """Test provider has required attributes."""
        provider = WorkflowProvider()
        assert hasattr(provider, "name")

    @pytest.mark.integration
    def test_provider_priority(self):
        """Test provider has correct priority."""
        from quadkit.contracts.core.provider import ProviderPriority
        provider = WorkflowProvider()
        assert provider.priority == ProviderPriority.DOMAIN


class TestBulkOperationConfigIntegration:
    """Integration tests for BulkOperationConfig."""

    @pytest.mark.integration
    def test_config_creation(self):
        """Test BulkOperationConfig can be created."""
        config = BulkOperationConfig()
        assert config is not None

    @pytest.mark.integration
    def test_config_model_dump(self):
        """Test BulkOperationConfig model can be serialized."""
        config = BulkOperationConfig()
        config_dict = config.model_dump()
        assert isinstance(config_dict, dict)

    @pytest.mark.integration
    def test_config_has_batch_size(self):
        """Test BulkOperationConfig has batch_size field."""
        config = BulkOperationConfig(batch_size=100)
        assert config.batch_size == 100


class TestWorkflowModuleIntegration:
    """Integration tests for WorkflowModule."""

    @pytest.mark.integration
    def test_workflow_module_import(self):
        """Test WorkflowModule can be imported."""
        from quadkit.workflow.module import WorkflowModule
        assert WorkflowModule is not None


class TestWorkflowCoreIntegration:
    """Integration tests for workflow core components."""

    @pytest.mark.integration
    def test_transform_pipe_import(self):
        """Test TransformPipe can be imported."""
        from quadkit.workflow.core.pipe import TransformPipe
        assert TransformPipe is not None