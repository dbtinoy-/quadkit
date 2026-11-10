"""Execution history formatting for workflow runs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.logging import safe_error_type

if TYPE_CHECKING:
    from quadkit.workflow.types import GraphResult, NodeResult


class ExecutionHistory:
    """Formats and inspects the execution trace of a completed workflow run.

    Args:
        result: The completed GraphResult to inspect.
    """

    def __init__(self, result: GraphResult) -> None:
        self._result = result

    def as_dict(self) -> dict[str, Any]:
        """Return the full execution trace as a JSON-serialisable dict.

        Returns:
            Dict with keys iterations, duration_ms, terminated_at, and nodes.
        """
        return {
            "iterations": self._result.iterations,
            "duration_ms": self._result.duration_ms,
            "terminated_at": self._result.terminated_at,
            "nodes": [self._node_dict(nr) for nr in self._result.node_results],
        }

    @staticmethod
    def _node_dict(nr: NodeResult) -> dict[str, Any]:
        """Convert a single NodeResult to a plain dict.

        Args:
            nr: Node result entry to convert.

        Returns:
            Dict with node trace fields.
        """
        return {
            "node": nr.node_name,
            "succeeded": nr.succeeded,
            "duration_ms": nr.duration_ms,
            "skipped": nr.skipped,
            "output_keys": list(nr.output.keys()) if nr.output else [],
            "error_type": safe_error_type(nr.error) if nr.error else None,
        }

    def as_text(self) -> str:
        """Return a multi-line human-readable execution trace.

        Returns:
            A string with one line per node showing its outcome.
        """
        lines: list[str] = [
            (
                f"Workflow trace  ({self._result.iterations} iterations, "
                f"{self._result.duration_ms:.1f} ms total)"
            ),
            "-" * 60,
        ]
        for nr in self._result.node_results:
            status = "SKIP" if nr.skipped else ("OK" if nr.succeeded else "ERR")
            error_part = (
                f"  [error_type={safe_error_type(nr.error)}]" if nr.error else ""
            )
            lines.append(
                f"  [{status:4s}] {nr.node_name:<30s}  {nr.duration_ms:7.1f} ms{error_part}"
            )
        lines.append("-" * 60)
        return "\n".join(lines)

    def failed_nodes(self) -> list[NodeResult]:
        """Return node results that terminated with an error.

        Returns:
            Filtered list of failed NodeResult entries.
        """
        return [
            nr
            for nr in self._result.node_results
            if not nr.succeeded and not nr.skipped
        ]

    def succeeded_nodes(self) -> list[NodeResult]:
        """Return node results that completed successfully.

        Returns:
            Filtered list of successful NodeResult entries.
        """
        return [nr for nr in self._result.node_results if nr.succeeded]

    def total_node_time_ms(self) -> float:
        """Return cumulative node execution time in milliseconds."""
        return sum(nr.duration_ms for nr in self._result.node_results)

    def __repr__(self) -> str:
        n = len(self._result.node_results)
        return f"ExecutionHistory(nodes={n}, total_ms={self._result.duration_ms:.1f})"


__all__ = ["ExecutionHistory"]
