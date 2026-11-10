"""Unit tests for WorkflowCheckpoint in-memory checkpoint store."""

from __future__ import annotations

import pytest

from quadkit.workflow.execution.checkpoint import WorkflowCheckpoint
from quadkit.workflow.graph.state import WorkflowState


class TestWorkflowCheckpointSaveLoad:
    def test_save_and_load_returns_snapshot(self) -> None:
        cp = WorkflowCheckpoint()
        state = WorkflowState(input="test")
        state.merge({"score": 42})
        cp.save("cp1", state)
        loaded = cp.load("cp1")
        assert loaded is not None
        assert loaded["score"] == 42
        assert loaded["input"] == "test"

    def test_load_returns_none_for_missing_id(self) -> None:
        cp = WorkflowCheckpoint()
        assert cp.load("nonexistent") is None

    def test_save_returns_copy_not_reference(self) -> None:
        cp = WorkflowCheckpoint()
        state = WorkflowState(input="test")
        cp.save("cp1", state)
        state.merge({"mutated": "after_save"})
        loaded = cp.load("cp1")
        assert loaded is not None
        assert "mutated" not in loaded

    def test_save_same_id_overwrites_snapshot(self) -> None:
        cp = WorkflowCheckpoint()
        state_v1 = WorkflowState(input="version_1")
        state_v2 = WorkflowState(input="version_2")
        cp.save("cp1", state_v1)
        cp.save("cp1", state_v2)
        loaded = cp.load("cp1")
        assert loaded is not None
        assert loaded["input"] == "version_2"

    def test_save_preserves_all_state_keys(self) -> None:
        cp = WorkflowCheckpoint()
        state = WorkflowState(input="x", initial={"a": 1, "b": "hello", "c": [1, 2, 3]})
        cp.save("cp1", state)
        loaded = cp.load("cp1")
        assert loaded is not None
        assert loaded["a"] == 1
        assert loaded["b"] == "hello"
        assert loaded["c"] == [1, 2, 3]


class TestWorkflowCheckpointDelete:
    def test_delete_removes_stored_entry(self) -> None:
        cp = WorkflowCheckpoint()
        state = WorkflowState(input="test")
        cp.save("cp1", state)
        cp.delete("cp1")
        assert cp.load("cp1") is None

    def test_delete_returns_true_when_entry_existed(self) -> None:
        cp = WorkflowCheckpoint()
        state = WorkflowState(input="test")
        cp.save("cp1", state)
        assert cp.delete("cp1") is True

    def test_delete_returns_false_for_nonexistent_id(self) -> None:
        cp = WorkflowCheckpoint()
        assert cp.delete("nonexistent") is False

    def test_delete_does_not_affect_other_entries(self) -> None:
        cp = WorkflowCheckpoint()
        s1 = WorkflowState(input="s1")
        s2 = WorkflowState(input="s2")
        cp.save("cp1", s1)
        cp.save("cp2", s2)
        cp.delete("cp1")
        assert cp.load("cp2") is not None


class TestWorkflowCheckpointCapacity:
    def test_len_returns_number_of_stored_checkpoints(self) -> None:
        cp = WorkflowCheckpoint()
        assert len(cp) == 0
        cp.save("a", WorkflowState(input="1"))
        assert len(cp) == 1
        cp.save("b", WorkflowState(input="2"))
        assert len(cp) == 2

    def test_contains_returns_true_for_saved_id(self) -> None:
        cp = WorkflowCheckpoint()
        cp.save("cp1", WorkflowState(input="test"))
        assert "cp1" in cp

    def test_contains_returns_false_for_missing_id(self) -> None:
        cp = WorkflowCheckpoint()
        assert "cp1" not in cp

    def test_max_size_evicts_oldest_entry(self) -> None:
        cp = WorkflowCheckpoint(max_size=2)
        cp.save("a", WorkflowState(input="a"))
        cp.save("b", WorkflowState(input="b"))
        cp.save("c", WorkflowState(input="c"))
        assert len(cp) == 2
        assert cp.load("a") is None
        assert cp.load("b") is not None
        assert cp.load("c") is not None

    def test_zero_max_size_means_unlimited(self) -> None:
        cp = WorkflowCheckpoint(max_size=0)
        for i in range(100):
            cp.save(f"cp{i}", WorkflowState(input=str(i)))
        assert len(cp) == 100

    def test_overwriting_existing_id_does_not_increment_len(self) -> None:
        cp = WorkflowCheckpoint()
        s = WorkflowState(input="test")
        cp.save("cp1", s)
        cp.save("cp1", WorkflowState(input="updated"))
        assert len(cp) == 1
