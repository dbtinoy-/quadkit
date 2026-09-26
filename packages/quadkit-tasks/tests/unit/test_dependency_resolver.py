"""Unit tests for DependencyResolver (task dependency cycle detection)."""

from __future__ import annotations

import pytest

from quadkit.tasks.exceptions import TaskDependencyCycleError
from quadkit.tasks.scheduling.dependency_resolver import DependencyResolver


class TestDependencyResolver:
    """Tests for DependencyResolver cycle detection."""

    # ------------------------------------------------------------------
    # Happy-path (acyclic graphs)
    # ------------------------------------------------------------------

    def test_register_single_node_no_deps(self) -> None:
        """A node with no dependencies is always valid."""
        resolver = DependencyResolver()
        resolver.register("job-a", depends_on=[])
        assert resolver.get_all() == {"job-a": []}

    def test_register_linear_chain(self) -> None:
        """A → B → C is a valid DAG."""
        resolver = DependencyResolver()
        resolver.register("job-c", depends_on=[])
        resolver.register("job-b", depends_on=["job-c"])
        resolver.register("job-a", depends_on=["job-b"])
        graph = resolver.get_all()
        assert graph["job-a"] == ["job-b"]
        assert graph["job-b"] == ["job-c"]

    def test_register_diamond_dependency(self) -> None:
        """A → B, A → C, B → D, C → D forms a valid diamond DAG."""
        resolver = DependencyResolver()
        resolver.register("job-d", depends_on=[])
        resolver.register("job-b", depends_on=["job-d"])
        resolver.register("job-c", depends_on=["job-d"])
        resolver.register("job-a", depends_on=["job-b", "job-c"])
        # No exception expected.

    def test_register_multiple_roots(self) -> None:
        """Multiple independent root nodes are fine."""
        resolver = DependencyResolver()
        resolver.register("job-x", depends_on=[])
        resolver.register("job-y", depends_on=[])
        resolver.register("job-z", depends_on=["job-x", "job-y"])

    def test_register_unknown_dependency_is_allowed(self) -> None:
        """Registering a dep that hasn't been registered yet is acceptable."""
        resolver = DependencyResolver()
        resolver.register("job-a", depends_on=["job-b"])
        # job-b is added as an empty node; this is not a cycle.

    # ------------------------------------------------------------------
    # Cycle detection
    # ------------------------------------------------------------------

    def test_direct_self_cycle_raises(self) -> None:
        """A job that depends on itself must raise immediately."""
        resolver = DependencyResolver()
        with pytest.raises(TaskDependencyCycleError) as exc_info:
            resolver.register("job-a", depends_on=["job-a"])
        assert "job-a" in exc_info.value.cycle

    def test_two_node_cycle_raises(self) -> None:
        """A → B and B → A forms a 2-node cycle."""
        resolver = DependencyResolver()
        resolver.register("job-a", depends_on=["job-b"])
        with pytest.raises(TaskDependencyCycleError) as exc_info:
            resolver.register("job-b", depends_on=["job-a"])
        error = exc_info.value
        assert "job-a" in error.cycle
        assert "job-b" in error.cycle

    def test_three_node_cycle_raises(self) -> None:
        """A → B → C → A forms a 3-node cycle."""
        resolver = DependencyResolver()
        resolver.register("job-a", depends_on=["job-b"])
        resolver.register("job-b", depends_on=["job-c"])
        with pytest.raises(TaskDependencyCycleError) as exc_info:
            resolver.register("job-c", depends_on=["job-a"])
        error = exc_info.value
        assert len(error.cycle) >= 4  # start == end, so at least 4 nodes
        assert error.cycle[0] == error.cycle[-1]

    def test_cycle_error_message_contains_path(self) -> None:
        """Error message includes the cycle path in human-readable form."""
        resolver = DependencyResolver()
        resolver.register("job-a", depends_on=["job-b"])
        with pytest.raises(TaskDependencyCycleError) as exc_info:
            resolver.register("job-b", depends_on=["job-a"])
        assert "→" in str(exc_info.value)

    def test_graph_not_modified_after_cycle_detected(self) -> None:
        """Graph is rolled back to its pre-registration state on cycle."""
        resolver = DependencyResolver()
        resolver.register("job-a", depends_on=["job-b"])
        snapshot_before = resolver.get_all()

        with pytest.raises(TaskDependencyCycleError):
            resolver.register("job-b", depends_on=["job-a"])

        # job-b should NOT have been committed to the graph.
        graph_after = resolver.get_all()
        assert graph_after.get("job-b", []) == snapshot_before.get("job-b", [])

    # ------------------------------------------------------------------
    # remove / get_all
    # ------------------------------------------------------------------

    def test_remove_existing_node(self) -> None:
        """Removing a node cleans it from the graph."""
        resolver = DependencyResolver()
        resolver.register("job-a", depends_on=[])
        resolver.remove("job-a")
        assert "job-a" not in resolver.get_all()

    def test_remove_nonexistent_node_is_noop(self) -> None:
        """Removing a node that was never registered is a no-op."""
        resolver = DependencyResolver()
        resolver.remove("ghost-job")  # must not raise

    def test_get_all_returns_copy(self) -> None:
        """Mutations to get_all() return value do not affect internal state."""
        resolver = DependencyResolver()
        resolver.register("job-a", depends_on=["job-b"])
        snapshot = resolver.get_all()
        snapshot["job-a"].append("job-c")  # mutate the copy
        assert resolver.get_all()["job-a"] == ["job-b"]  # internal unchanged

    # ------------------------------------------------------------------
    # TaskDependencyCycleError attributes
    # ------------------------------------------------------------------

    def test_cycle_error_has_cycle_attribute(self) -> None:
        """TaskDependencyCycleError exposes .cycle with the path."""
        resolver = DependencyResolver()
        resolver.register("job-a", depends_on=["job-b"])
        with pytest.raises(TaskDependencyCycleError) as exc_info:
            resolver.register("job-b", depends_on=["job-a"])
        assert isinstance(exc_info.value.cycle, list)
        assert len(exc_info.value.cycle) >= 2

    def test_cycle_error_code(self) -> None:
        """TaskDependencyCycleError has the expected error code."""
        resolver = DependencyResolver()
        with pytest.raises(TaskDependencyCycleError) as exc_info:
            resolver.register("job-a", depends_on=["job-a"])
        assert exc_info.value._code == "QK_ERR_TASK_010"
