"""Tests for workflow module."""

import pytest
from quadkit.workflow import WorkflowModule
from quadkit.di.module import DynamicModule


class TestWorkflowModule:
    def test_workflow_module_exists(self) -> None:
        assert WorkflowModule is not None

    def test_configure_returns_dynamic_module(self) -> None:
        result = WorkflowModule.configure()
        assert isinstance(result, DynamicModule)
        assert result.module is WorkflowModule

    def test_configure_exports_pipeline_protocol(self) -> None:
        from quadkit.contracts.workflow import PipelineProtocol

        result = WorkflowModule.configure()
        assert PipelineProtocol in result.exports

    def test_configure_exposes_application_state_machine(self) -> None:
        from quadkit.contracts.workflow import StateMachineProtocol

        state_machine = object()
        result = WorkflowModule.configure(state_machine=state_machine)

        assert StateMachineProtocol in result.exports
        provider = result.providers[0]
        assert provider._state_machine is state_machine

    def test_configure_does_not_export_absent_state_machine(self) -> None:
        from quadkit.contracts.workflow import StateMachineProtocol

        result = WorkflowModule.configure()
        assert StateMachineProtocol not in result.exports

    def test_configure_config_type_check(self) -> None:
        with pytest.raises(TypeError, match="must be BulkOperationConfig"):
            WorkflowModule.configure(config="invalid")
