"""Unit tests for workflow definition versioning (FAANG fix 08.C-01).

Covers:
- WorkflowDefinition carries a version field (defaults to 1).
- WorkflowInstance.create() stamps definition_version from the definition.
- WorkflowInstance.validate_definition_version() raises WorkflowVersionMismatchError
  on mismatch and is silent on match.
- WorkflowEngine stamps _definition_version into state on execute().
- WorkflowEngine.resume() raises WorkflowVersionMismatchError when the
  checkpoint's definition version differs from the engine's version.
"""

from __future__ import annotations

import pytest

from quadkit.workflow.core.definition import WorkflowDefinition
from quadkit.workflow.core.instance import WorkflowInstance
from quadkit.workflow.exceptions import WorkflowVersionMismatchError


class TestWorkflowDefinitionVersion:
    def test_workflow_definition_has_version_field(self) -> None:
        """WorkflowDefinition must carry a version."""
        defn = WorkflowDefinition(name="my-workflow", steps=[], version=1)
        assert defn.version == 1

    def test_default_version_is_one(self) -> None:
        """Version defaults to 1 for backward compatibility."""
        defn = WorkflowDefinition(name="my-workflow", steps=[])
        assert defn.version == 1

    def test_explicit_version_stored(self) -> None:
        """An explicitly-set version is stored verbatim."""
        defn = WorkflowDefinition(name="my-workflow", steps=[], version=42)
        assert defn.version == 42

    def test_definition_is_frozen(self) -> None:
        """WorkflowDefinition is a frozen dataclass — mutation must raise."""
        defn = WorkflowDefinition(name="my-workflow", steps=[], version=1)
        with pytest.raises((AttributeError, TypeError)):
            defn.version = 2  # type: ignore[misc]

    def test_steps_default_to_empty_list(self) -> None:
        """Omitting steps gives an empty list."""
        defn = WorkflowDefinition(name="my-workflow")
        assert defn.steps == []

    def test_steps_can_carry_arbitrary_data(self) -> None:
        """Steps list is opaque — accepts any payload."""
        payload = [{"id": "step1"}, {"id": "step2"}]
        defn = WorkflowDefinition(name="my-workflow", steps=payload)
        assert defn.steps == payload


class TestWorkflowInstanceVersioning:
    def test_version_stored_in_instance(self) -> None:
        """The workflow instance records the definition version at creation."""
        defn = WorkflowDefinition(name="my-workflow", steps=[], version=3)
        instance = WorkflowInstance.create(definition=defn)
        assert instance.definition_version == 3

    def test_create_default_version(self) -> None:
        """Instance created from a v1 definition stores version 1."""
        defn = WorkflowDefinition(name="my-workflow", steps=[])
        instance = WorkflowInstance.create(definition=defn)
        assert instance.definition_version == 1

    def test_create_stamps_workflow_name(self) -> None:
        """WorkflowInstance.create() records the workflow name."""
        defn = WorkflowDefinition(name="order-workflow", steps=[], version=2)
        instance = WorkflowInstance.create(definition=defn)
        assert instance.workflow_name == "order-workflow"

    def test_create_assigns_unique_instance_id(self) -> None:
        """Each call to create() produces a different instance_id."""
        defn = WorkflowDefinition(name="my-workflow", steps=[])
        a = WorkflowInstance.create(definition=defn)
        b = WorkflowInstance.create(definition=defn)
        assert a.instance_id != b.instance_id

    def test_version_mismatch_raises(self) -> None:
        """Resuming an instance with a different definition version must raise."""
        defn_v1 = WorkflowDefinition(name="my-workflow", steps=[], version=1)
        instance = WorkflowInstance.create(definition=defn_v1)

        defn_v2 = WorkflowDefinition(name="my-workflow", steps=[], version=2)
        with pytest.raises(WorkflowVersionMismatchError) as exc_info:
            instance.validate_definition_version(defn_v2)

        err = exc_info.value
        assert err.expected_version == 1
        assert err.actual_version == 2
        assert err.workflow_name == "my-workflow"

    def test_matching_version_does_not_raise(self) -> None:
        """validate_definition_version is silent when versions match."""
        defn = WorkflowDefinition(name="my-workflow", steps=[], version=5)
        instance = WorkflowInstance.create(definition=defn)
        # Must not raise
        instance.validate_definition_version(defn)

    def test_version_mismatch_error_message(self) -> None:
        """Error message is static and does not disclose workflow identifiers."""
        defn_v1 = WorkflowDefinition(name="checkout", steps=[], version=1)
        instance = WorkflowInstance.create(definition=defn_v1)

        defn_v3 = WorkflowDefinition(name="checkout", steps=[], version=3)
        with pytest.raises(WorkflowVersionMismatchError) as exc_info:
            instance.validate_definition_version(defn_v3)

        msg = str(exc_info.value)
        assert "checkout" not in msg
        assert "v1" not in msg
        assert "v3" not in msg
        assert "Workflow definition changed" in msg


class TestWorkflowVersionMismatchError:
    def test_error_inherits_from_workflow_error(self) -> None:
        """WorkflowVersionMismatchError must extend WorkflowError."""
        from quadkit.workflow.exceptions import WorkflowError

        err = WorkflowVersionMismatchError(
            workflow_name="w", expected_version=1, actual_version=2
        )
        assert isinstance(err, WorkflowError)

    def test_error_attributes(self) -> None:
        """All three constructor args are stored as attributes."""
        err = WorkflowVersionMismatchError(
            workflow_name="pipeline-a",
            expected_version=4,
            actual_version=7,
        )
        assert err.workflow_name == "pipeline-a"
        assert err.expected_version == 4
        assert err.actual_version == 7


class TestWorkflowEngineVersioning:
    """WorkflowEngine stamps _definition_version into state and validates on resume."""

    def _make_engine(self, version: int = 1) -> object:
        from quadkit.workflow.graph.builder import WorkflowBuilder
        from quadkit.workflow.graph.node import AbstractWorkflowNode, NodeType

        class _EchoNode(AbstractWorkflowNode):
            def __init__(self, name: str) -> None:
                super().__init__(name, NodeType.CUSTOM)

            async def execute(self, state: dict) -> dict:  # type: ignore[override]
                return {"output": state.get("input", "")}

        return (
            WorkflowBuilder(name="test-wf", version=version)
            .add_node("start", node=_EchoNode("start"))
            .set_entry("start")
            .set_terminal("start")
            .build()
        )

    @pytest.mark.asyncio
    async def test_engine_has_version_property(self) -> None:
        """WorkflowEngine exposes its version via a property."""
        engine = self._make_engine(version=3)
        assert engine.version == 3  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_engine_default_version_is_one(self) -> None:
        """WorkflowEngine defaults to version 1."""
        from quadkit.workflow.graph.builder import WorkflowBuilder
        from quadkit.workflow.graph.node import AbstractWorkflowNode, NodeType

        class _EchoNode(AbstractWorkflowNode):
            def __init__(self, name: str) -> None:
                super().__init__(name, NodeType.CUSTOM)

            async def execute(self, state: dict) -> dict:  # type: ignore[override]
                return {}

        engine = (
            WorkflowBuilder(name="test-wf")
            .add_node("start", node=_EchoNode("start"))
            .set_entry("start")
            .set_terminal("start")
            .build()
        )
        assert engine.version == 1  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_execute_stamps_definition_version_in_state(self) -> None:
        """execute() stores _definition_version in workflow state."""
        engine = self._make_engine(version=5)
        result = await engine.execute("hello")  # type: ignore[attr-defined]
        assert result.is_ok()
        final_state = result.unwrap().final_state
        assert final_state.get("_definition_version") == 5

    @pytest.mark.asyncio
    async def test_resume_raises_on_version_mismatch(self) -> None:
        """resume() raises WorkflowVersionMismatchError when checkpoint version differs."""
        engine_v2 = self._make_engine(version=2)
        # Simulate a checkpoint that was created when the definition was v1
        checkpoint_state = {
            "input": "hello",
            "_definition_version": 1,
            "_paused_at": "start",
            "human_response": "",
        }
        with pytest.raises(WorkflowVersionMismatchError) as exc_info:
            await engine_v2.resume(checkpoint_state, "operator reply")  # type: ignore[attr-defined]

        err = exc_info.value
        assert err.expected_version == 1
        assert err.actual_version == 2

    @pytest.mark.asyncio
    async def test_resume_passes_on_matching_version(self) -> None:
        """resume() proceeds normally when checkpoint version matches engine version."""
        engine_v1 = self._make_engine(version=1)
        checkpoint_state = {
            "input": "hello",
            "_definition_version": 1,
            "human_response": "",
        }
        # Should not raise — versions match
        result = await engine_v1.resume(checkpoint_state, "operator reply")  # type: ignore[attr-defined]
        # Result is Ok or Err depending on execution; the important thing is
        # no WorkflowVersionMismatchError was raised.
        assert result is not None

    @pytest.mark.asyncio
    async def test_resume_passes_when_no_version_in_checkpoint(self) -> None:
        """resume() is permissive for old checkpoints that predate versioning."""
        engine_v2 = self._make_engine(version=2)
        # Checkpoint has no _definition_version — should not raise
        checkpoint_state = {
            "input": "hello",
            "human_response": "",
        }
        result = await engine_v2.resume(checkpoint_state, "operator reply")  # type: ignore[attr-defined]
        assert result is not None
