"""Performance summary utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.monitor.profiling.models import PerformanceMetrics


async def get_performance_summary(metrics: PerformanceMetrics) -> dict[str, Any]:
    """Return a dictionary summary of performance metrics.

    Args:
        metrics: Accumulated :class:`PerformanceMetrics` to summarise.

    Returns:
        Dictionary containing duration, sample counts, CPU/memory averages,
        task counts, and a ``has_profile_data`` flag.
    """
    summary: dict[str, Any] = {
        "duration": metrics.duration,
        "total_samples": metrics.total_samples,
        "samples_per_second": metrics.samples_per_second,
        "average_cpu_percent": metrics.average_cpu_percent,
        "average_memory_usage": metrics.average_memory_usage,
        "peak_memory_usage": metrics.peak_memory_usage,
        "max_active_tasks": metrics.max_active_tasks,
        "has_profile_data": metrics.profile_data is not None,
    }

    if metrics.snapshots:
        last = metrics.snapshots[-1]
        summary["current_active_tasks"] = last.active_tasks
        summary["current_pending_tasks"] = last.pending_tasks
        summary["current_total_tasks"] = last.total_tasks
    else:
        summary["current_active_tasks"] = 0
        summary["current_pending_tasks"] = 0
        summary["current_total_tasks"] = 0

    return summary


__all__ = ["get_performance_summary"]
