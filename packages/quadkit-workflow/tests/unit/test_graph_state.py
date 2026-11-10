"""Unit tests for WorkflowState shared state container."""

from __future__ import annotations

import pytest

from quadkit.workflow.graph.state import WorkflowState


class TestWorkflowStateConstruction:
    def test_default_construction_sets_input(self) -> None:
        state = WorkflowState(input="hello")
        assert state["input"] == "hello"

    def test_default_construction_initializes_output(self) -> None:
        state = WorkflowState(input="hello")
        assert state["output"] == ""

    def test_default_construction_starts_at_zero_iteration(self) -> None:
        state = WorkflowState(input="hello")
        assert state.iteration == 0

    def test_default_construction_empty_history(self) -> None:
        state = WorkflowState(input="hello")
        assert state.history == []

    def test_initial_dict_merges_into_state(self) -> None:
        state = WorkflowState(input="x", initial={"user": "alice", "count": 3})
        assert state["user"] == "alice"
        assert state["count"] == 3

    def test_initial_dict_overrides_default_output(self) -> None:
        state = WorkflowState(input="x", initial={"output": "pre-loaded"})
        assert state["output"] == "pre-loaded"

    def test_no_initial_leaves_defaults_intact(self) -> None:
        state = WorkflowState(input="y")
        assert state.get("user") is None


class TestWorkflowStateDictAccess:
    def test_getitem_returns_value(self) -> None:
        state = WorkflowState(input="test")
        assert state["input"] == "test"

    def test_getitem_raises_key_error_for_missing(self) -> None:
        state = WorkflowState(input="test")
        with pytest.raises(KeyError):
            _ = state["nonexistent"]

    def test_setitem_stores_value(self) -> None:
        state = WorkflowState(input="test")
        state["custom_key"] = "custom_value"
        assert state["custom_key"] == "custom_value"

    def test_contains_returns_true_for_existing_key(self) -> None:
        state = WorkflowState(input="test")
        assert "input" in state

    def test_contains_returns_false_for_missing_key(self) -> None:
        state = WorkflowState(input="test")
        assert "nonexistent" not in state

    def test_get_returns_value_for_existing_key(self) -> None:
        state = WorkflowState(input="test")
        assert state.get("input") == "test"

    def test_get_returns_default_for_missing_key(self) -> None:
        state = WorkflowState(input="test")
        assert state.get("missing", "fallback") == "fallback"

    def test_get_returns_none_default_when_not_specified(self) -> None:
        state = WorkflowState(input="test")
        assert state.get("missing") is None


class TestWorkflowStateMerge:
    def test_merge_updates_regular_keys(self) -> None:
        state = WorkflowState(input="test")
        state.merge({"output": "result", "score": 42})
        assert state["output"] == "result"
        assert state["score"] == 42

    def test_merge_skips_underscore_prefixed_keys(self) -> None:
        state = WorkflowState(input="test")
        state.merge({"_history": ["fake"], "_iteration": 99})
        assert state.iteration == 0
        assert state.history == []

    def test_merge_empty_dict_changes_nothing(self) -> None:
        state = WorkflowState(input="test")
        state.merge({})
        assert state["input"] == "test"
        assert state.iteration == 0

    def test_merge_overwrites_existing_key(self) -> None:
        state = WorkflowState(input="test")
        state.merge({"output": "first"})
        state.merge({"output": "second"})
        assert state["output"] == "second"


class TestWorkflowStateRecord:
    def test_record_appends_to_history(self) -> None:
        state = WorkflowState(input="test")
        state.record("node_a", {"result": "x"})
        assert len(state.history) == 1
        assert state.history[0] == ("node_a", {"result": "x"})

    def test_record_increments_iteration(self) -> None:
        state = WorkflowState(input="test")
        state.record("node_a", {})
        assert state.iteration == 1
        state.record("node_b", {})
        assert state.iteration == 2

    def test_multiple_records_ordered(self) -> None:
        state = WorkflowState(input="test")
        state.record("a", {"step": 1})
        state.record("b", {"step": 2})
        state.record("c", {"step": 3})
        names = [name for name, _ in state.history]
        assert names == ["a", "b", "c"]


class TestWorkflowStateAsDict:
    def test_as_dict_returns_shallow_copy(self) -> None:
        state = WorkflowState(input="test")
        d = state.as_dict()
        assert isinstance(d, dict)
        assert d["input"] == "test"

    def test_as_dict_copy_does_not_mutate_state(self) -> None:
        state = WorkflowState(input="test")
        d = state.as_dict()
        d["input"] = "mutated"
        assert state["input"] == "test"

    def test_as_dict_includes_internal_keys(self) -> None:
        state = WorkflowState(input="test")
        d = state.as_dict()
        assert "_iteration" in d
        assert "_history" in d


class TestWorkflowStateRepr:
    def test_repr_includes_iteration(self) -> None:
        state = WorkflowState(input="test")
        r = repr(state)
        assert "iteration=0" in r

    def test_repr_includes_user_keys(self) -> None:
        state = WorkflowState(input="test")
        state.merge({"score": 1})
        r = repr(state)
        assert "score" in r

    def test_repr_excludes_internal_underscore_keys(self) -> None:
        state = WorkflowState(input="test")
        r = repr(state)
        assert "_iteration" not in r
        assert "_history" not in r
