"""Unit tests for quadkit-workflow exceptions.

These tests verify the exception hierarchy in quadkit.workflow.exceptions.
"""

import pytest
from quadkit.contracts.workflow import SagaVersionMismatchError
from quadkit.workflow.exceptions import (
    BulkOperationCancelledError,
    BulkOperationError,
    BulkOperationTimeoutError,
    CycleDetectedError,
    GraphExecutionError,
    GraphTimeoutError,
    GraphValidationError,
    HumanInputRequiredError,
    NodeExecutionError,
    PipelineExecutionError,
    PipelineStepError,
    WorkflowCompensationError,
    WorkflowError,
    WorkflowNotFoundError,
    WorkflowStateError,
    WorkflowStepError as WorkflowStepErrorException,
    WorkflowTimeoutError,
    WorkflowVersionMismatchError,
)


class TestPipelineExecutionError:
    """Tests for PipelineExecutionError."""

    def test_pipeline_execution_error_exists(self) -> None:
        assert PipelineExecutionError is not None


class TestPipelineStepError:
    """Tests for PipelineStepError."""

    def test_pipeline_step_error_exists(self) -> None:
        assert PipelineStepError is not None


class TestBulkOperationError:
    """Tests for BulkOperationError."""

    def test_bulk_operation_error_exists(self) -> None:
        assert BulkOperationError is not None


class TestBulkOperationCancelledError:
    """Tests for BulkOperationCancelledError."""

    def test_bulk_operation_cancelled_error_exists(self) -> None:
        assert BulkOperationCancelledError is not None


class TestBulkOperationTimeoutError:
    """Tests for BulkOperationTimeoutError."""

    def test_bulk_operation_timeout_error_exists(self) -> None:
        assert BulkOperationTimeoutError is not None


class TestWorkflowError:
    """Tests for WorkflowError base exception."""

    def test_workflow_error_message(self) -> None:
        err = WorkflowError("test error")
        assert "test error" in str(err)

    def test_workflow_error_step_name(self) -> None:
        err = WorkflowError()
        assert err.step_name == "workflow"

    def test_workflow_error_code(self) -> None:
        err = WorkflowError()
        assert err._code == "QK_ERR_WF_003"


class TestWorkflowNotFoundError:
    """Tests for WorkflowNotFoundError."""

    def test_workflow_not_found_message(self) -> None:
        err = WorkflowNotFoundError("test-workflow")
        assert err.message == (
            "Pipeline step 'workflow' failed: Workflow not found."
        )
        assert "test-workflow" not in err.message

    def test_workflow_not_found_workflow_id(self) -> None:
        err = WorkflowNotFoundError("test-workflow")
        assert err.workflow_id == "test-workflow"

    def test_workflow_not_found_code(self) -> None:
        err = WorkflowNotFoundError("test-workflow")
        assert err._code == "QK_ERR_WF_004"


class TestWorkflowStateError:
    """Tests for WorkflowStateError."""

    def test_workflow_state_error_message(self) -> None:
        err = WorkflowStateError("invalid state")
        assert "invalid state" in str(err)

    def test_workflow_state_error_code(self) -> None:
        err = WorkflowStateError()
        assert err._code == "QK_ERR_WF_005"


class TestWorkflowStepError:
    """Tests for WorkflowStepError."""

    def test_workflow_step_error_message(self) -> None:
        err = WorkflowStepErrorException("step1", "something went wrong")
        assert err.message == (
            "Pipeline step 'workflow' failed: Workflow step failed."
        )
        assert "step1" not in err.message
        assert "something went wrong" not in err.message

    def test_workflow_step_error_attributes(self) -> None:
        err = WorkflowStepErrorException("step1", "something went wrong")
        assert err.step_name == "step1"
        assert err.reason == "Workflow step failed."

    def test_workflow_step_error_code(self) -> None:
        err = WorkflowStepErrorException("step1", "reason")
        assert err._code == "QK_ERR_WF_006"


class TestWorkflowTimeoutError:
    """Tests for WorkflowTimeoutError."""

    def test_workflow_timeout_error_exists(self) -> None:
        err = WorkflowTimeoutError()
        assert err is not None

    def test_workflow_timeout_error_code(self) -> None:
        err = WorkflowTimeoutError()
        assert err._code == "QK_ERR_WF_007"


class TestWorkflowCompensationError:
    """Tests for WorkflowCompensationError."""

    def test_workflow_compensation_error_exists(self) -> None:
        err = WorkflowCompensationError()
        assert err is not None

    def test_workflow_compensation_error_code(self) -> None:
        err = WorkflowCompensationError()
        assert err._code == "QK_ERR_WF_008"


class TestSagaVersionMismatchError:
    """Tests for SagaVersionMismatchError."""

    def test_saga_version_mismatch_message(self) -> None:
        err = SagaVersionMismatchError("saga-123", expected_version=2, stored_version=1)
        assert err.message == "Saga state version is incompatible with the current definition."
        assert "saga-123" not in err.message
        assert "v2" not in err.message
        assert "v1" not in err.message

    def test_saga_version_mismatch_attributes(self) -> None:
        err = SagaVersionMismatchError("saga-123", expected_version=2, stored_version=1)
        assert err.saga_id == "saga-123"
        assert err.expected_version == 2
        assert err.stored_version == 1

    def test_saga_version_mismatch_code(self) -> None:
        err = SagaVersionMismatchError("saga-123", expected_version=2, stored_version=1)
        assert err._code == "QK_ERR_WF_009"


class TestWorkflowVersionMismatchError:
    """Tests for WorkflowVersionMismatchError."""

    def test_workflow_version_mismatch_message(self) -> None:
        err = WorkflowVersionMismatchError(
            "my-workflow", expected_version=3, actual_version=5
        )
        message = str(err)
        assert "my-workflow" not in message
        assert "v3" not in message
        assert "v5" not in message
        assert "Workflow definition changed" in message

    def test_workflow_version_mismatch_attributes(self) -> None:
        err = WorkflowVersionMismatchError(
            "my-workflow", expected_version=3, actual_version=5
        )
        assert err.workflow_name == "my-workflow"
        assert err.expected_version == 3
        assert err.actual_version == 5

    def test_workflow_version_mismatch_code(self) -> None:
        err = WorkflowVersionMismatchError(
            "my-workflow", expected_version=3, actual_version=5
        )
        assert err._code == "QK_ERR_WF_010"


class TestGraphExecutionError:
    """Tests for GraphExecutionError base exception."""

    def test_graph_execution_error_message(self) -> None:
        err = GraphExecutionError("graph error")
        assert "graph error" in str(err)

    def test_graph_execution_error_node(self) -> None:
        err = GraphExecutionError("error", node="node1")
        assert err.node == "node1"

    def test_graph_execution_error_node_none(self) -> None:
        err = GraphExecutionError("error")
        assert err.node is None

    def test_graph_execution_error_code(self) -> None:
        err = GraphExecutionError("error")
        assert err._code == "QK_ERR_WF_011"


class TestNodeExecutionError:
    """Tests for NodeExecutionError."""

    def test_node_execution_error_message(self) -> None:
        err = NodeExecutionError("node failed", node="node1")
        assert "node failed" in str(err)

    def test_node_execution_error_node(self) -> None:
        err = NodeExecutionError("error", node="node1")
        assert err.node == "node1"

    def test_node_execution_error_code(self) -> None:
        err = NodeExecutionError("error", node="node1")
        assert err._code == "QK_ERR_WF_012"


class TestCycleDetectedError:
    """Tests for CycleDetectedError."""

    def test_cycle_detected_error_message(self) -> None:
        err = CycleDetectedError(100, node="loop-node")
        assert err.message == "Workflow exceeded the maximum iteration limit."
        assert "100" not in err.message
        assert "loop-node" not in err.message

    def test_cycle_detected_error_iterations(self) -> None:
        err = CycleDetectedError(100, node="loop-node")
        assert err.iterations == 100

    def test_cycle_detected_error_node(self) -> None:
        err = CycleDetectedError(100, node="loop-node")
        assert err.node == "loop-node"

    def test_cycle_detected_error_code(self) -> None:
        err = CycleDetectedError(100, node="loop-node")
        assert err._code == "QK_ERR_WF_013"


class TestGraphTimeoutError:
    """Tests for GraphTimeoutError."""

    def test_graph_timeout_error_message(self) -> None:
        err = GraphTimeoutError(60.0)
        assert "60" in str(err)
        assert "timed out" in str(err).lower()

    def test_graph_timeout_error_timeout(self) -> None:
        err = GraphTimeoutError(60.0)
        assert err.timeout == 60.0

    def test_graph_timeout_error_code(self) -> None:
        err = GraphTimeoutError(60.0)
        assert err._code == "QK_ERR_WF_014"


class TestGraphValidationError:
    """Tests for GraphValidationError."""

    def test_graph_validation_error_message(self) -> None:
        err = GraphValidationError("invalid graph")
        assert "invalid graph" in str(err)

    def test_graph_validation_error_code(self) -> None:
        err = GraphValidationError("error")
        assert err._code == "QK_ERR_WF_015"


class TestHumanInputRequiredError:
    """Tests for HumanInputRequiredError."""

    def test_human_input_required_error_message(self) -> None:
        err = HumanInputRequiredError("Please confirm", node="human-node")
        assert err.message == "Human input is required."
        assert "Please confirm" not in err.message
        assert "human-node" not in err.message

    def test_human_input_required_error_attributes(self) -> None:
        err = HumanInputRequiredError("Please confirm", node="human-node", checkpoint_id="cp-123")
        assert err.prompt == "Please confirm"
        assert err.node == "human-node"
        assert err.checkpoint_id == "cp-123"

    def test_human_input_required_error_checkpoint_id_none(self) -> None:
        err = HumanInputRequiredError("Please confirm", node="human-node")
        assert err.checkpoint_id is None

    def test_human_input_required_error_code(self) -> None:
        err = HumanInputRequiredError("prompt", node="node")
        assert err._code == "QK_ERR_WF_016"


class TestExceptionHierarchy:
    """Tests for exception hierarchy."""

    def test_workflow_error_inherits_from_pipeline_execution_error(self) -> None:
        assert issubclass(WorkflowError, PipelineExecutionError)

    def test_workflow_not_found_error_inherits_from_workflow_error(self) -> None:
        assert issubclass(WorkflowNotFoundError, WorkflowError)

    def test_workflow_state_error_inherits_from_workflow_error(self) -> None:
        assert issubclass(WorkflowStateError, WorkflowError)

    def test_workflow_step_error_inherits_from_workflow_error(self) -> None:
        assert issubclass(WorkflowStepErrorException, WorkflowError)

    def test_workflow_timeout_error_inherits_from_workflow_error(self) -> None:
        assert issubclass(WorkflowTimeoutError, WorkflowError)

    def test_workflow_compensation_error_inherits_from_workflow_error(self) -> None:
        assert issubclass(WorkflowCompensationError, WorkflowError)

    def test_saga_version_mismatch_error_inherits_from_quadkit_error(self) -> None:
        from quadkit.contracts.exceptions.base import QuadkitError

        assert issubclass(SagaVersionMismatchError, QuadkitError)

    def test_workflow_version_mismatch_error_inherits_from_workflow_error(self) -> None:
        assert issubclass(WorkflowVersionMismatchError, WorkflowError)

    def test_graph_execution_error_inherits_from_quadkit_error(self) -> None:
        from quadkit.contracts.exceptions.base import QuadkitError

        assert issubclass(GraphExecutionError, QuadkitError)

    def test_node_execution_error_inherits_from_graph_execution_error(self) -> None:
        assert issubclass(NodeExecutionError, GraphExecutionError)

    def test_cycle_detected_error_inherits_from_graph_execution_error(self) -> None:
        assert issubclass(CycleDetectedError, GraphExecutionError)

    def test_graph_timeout_error_inherits_from_graph_execution_error(self) -> None:
        assert issubclass(GraphTimeoutError, GraphExecutionError)

    def test_graph_validation_error_inherits_from_graph_execution_error(self) -> None:
        assert issubclass(GraphValidationError, GraphExecutionError)

    def test_human_input_required_error_inherits_from_graph_execution_error(self) -> None:
        assert issubclass(HumanInputRequiredError, GraphExecutionError)


class TestExceptionAllExports:
    """Tests to verify __all__ exports."""

    def test_all_contains_all_exceptions(self) -> None:
        from quadkit.workflow import exceptions as exc_module

        expected = [
            "BulkOperationCancelledError",
            "BulkOperationError",
            "BulkOperationTimeoutError",
            "CycleDetectedError",
            "GraphExecutionError",
            "GraphTimeoutError",
            "GraphValidationError",
            "HumanInputRequiredError",
            "NodeExecutionError",
            "PipelineExecutionError",
            "PipelineStepError",
        
            "WorkflowCompensationError",
            "WorkflowError",
            "WorkflowNotFoundError",
            "WorkflowStateError",
            "WorkflowStepError",
            "WorkflowTimeoutError",
            "WorkflowVersionMismatchError",
        ]
        for item in expected:
            assert item in exc_module.__all__, f"{item} not in __all__"