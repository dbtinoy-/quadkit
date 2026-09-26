"""Dependency graph management and cycle detection for the task scheduler.

Provides :class:`DependencyResolver`, which maintains a DAG of job
dependencies and raises :exc:`~quadkit.tasks.exceptions.TaskDependencyCycleError`
at registration time if adding a new job's edges would create a cycle.

This prevents runtime deadlocks caused by circular task dependencies —
jobs that mutually wait for each other will never be executed.

Typical usage::

    resolver = DependencyResolver()
    resolver.register("job-a", depends_on=["job-b"])   # OK
    resolver.register("job-b", depends_on=["job-c"])   # OK
    resolver.register("job-c", depends_on=["job-a"])   # raises TaskDependencyCycleError
"""

from __future__ import annotations

from quadkit.tasks.exceptions import TaskDependencyCycleError

__all__ = ["DependencyResolver"]


class DependencyResolver:
    """Validates and tracks a directed acyclic graph (DAG) of job dependencies.

    Each call to :meth:`register` adds a node and its outgoing edges to the
    internal adjacency list, then runs a DFS-based cycle check.  If a cycle
    is found, :exc:`~quadkit.tasks.exceptions.TaskDependencyCycleError` is
    raised and the graph is **not** modified — keeping it permanently valid.

    The resolver is typically held by :class:`~quadkit.tasks.scheduling.scheduler.TaskScheduler`
    and consulted whenever a new job is scheduled.
    """

    def __init__(self) -> None:
        """Initialise an empty dependency graph."""
        self._graph: dict[str, list[str]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, node_id: str, depends_on: list[str]) -> None:
        """Register a job with its dependencies, raising on cycle detection.

        If the new edges would create a cycle, :exc:`TaskDependencyCycleError`
        is raised and the graph state is left unchanged.

        Args:
            node_id: Unique identifier for the job (job name or scheduled-job ID).
            depends_on: IDs of jobs that *node_id* requires to finish first.

        Raises:
            TaskDependencyCycleError: When adding the edges would create a cycle
                in the dependency graph.
        """
        # Snap-shot the pre-existing entry (if any) so we can roll back.
        previous = self._graph.get(node_id)

        # Apply the new edges speculatively.
        self._graph[node_id] = list(depends_on)
        # Ensure all dependency nodes are present even if they have no deps yet.
        for dep in depends_on:
            self._graph.setdefault(dep, [])

        # Run cycle detection; roll back and re-raise on failure.
        cycle = self._find_cycle()
        if cycle:
            # Restore previous state.
            if previous is None:
                del self._graph[node_id]
            else:
                self._graph[node_id] = previous
            raise TaskDependencyCycleError(
                cycle=cycle,
                details={"node_id": node_id, "depends_on": depends_on},
            )

    def remove(self, node_id: str) -> None:
        """Remove a node and its edges from the dependency graph.

        Args:
            node_id: Identifier of the job to remove.  No-op if absent.
        """
        self._graph.pop(node_id, None)

    def get_all(self) -> dict[str, list[str]]:
        """Return a snapshot of the current dependency graph.

        Returns:
            A shallow copy of the adjacency list (node_id → dependency IDs).
        """
        return {k: list(v) for k, v in self._graph.items()}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_cycle(self) -> list[str]:
        """Search for a cycle in the entire graph using iterative DFS.

        Returns:
            A non-empty list of node IDs forming the cycle (first == last) if
            a cycle is found, or an empty list when the graph is acyclic.
        """
        visited: set[str] = set()

        for start in list(self._graph):
            if start in visited:
                continue
            cycle = self._dfs_cycle(start, visited)
            if cycle:
                return cycle

        return []

    def _dfs_cycle(self, start: str, global_visited: set[str]) -> list[str]:
        """Run DFS from *start*, returning a cycle path or empty list.

        Uses an explicit stack to avoid Python recursion-depth limits.

        Args:
            start: Node to begin DFS from.
            global_visited: Set of nodes whose subtrees are fully explored
                across all previous DFS runs (black nodes in standard 3-colour DFS).

        Returns:
            Ordered cycle path (first == last) if found, otherwise ``[]``.
        """
        # Stack items: (node, iter_over_neighbours, path_to_node)
        stack: list[tuple[str, int, list[str]]] = [(start, 0, [start])]
        in_stack: set[str] = {start}

        while stack:
            node, idx, path = stack[-1]
            neighbours = self._graph.get(node, [])

            if idx < len(neighbours):
                stack[-1] = (node, idx + 1, path)
                neighbour = neighbours[idx]

                if neighbour in in_stack:
                    # Found a back edge — extract the cycle.
                    cycle_start = path.index(neighbour)
                    return [*path[cycle_start:], neighbour]

                if neighbour not in global_visited:
                    in_stack.add(neighbour)
                    stack.append((neighbour, 0, [*path, neighbour]))
            else:
                # Node fully explored (black).
                global_visited.add(node)
                in_stack.discard(node)
                stack.pop()

        return []
