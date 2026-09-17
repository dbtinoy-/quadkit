"""Experiment tracking protocols and types for reproducible AI runs.

Defines the seed-stable run identity, metric/error records, checkpoints,
ablation results, and analysis reports consumed by evaluation and
experiment tooling across the framework.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class RunStatus(str, Enum):
    """Lifecycle status of an experiment run."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class MetricRecord:
    """A single scalar metric recorded during an experiment run.

    Attributes:
        step: Iteration or step index the metric was recorded at.
        name: Metric name (e.g. ``tokens``, ``latency_ms``, ``score``).
        value: Numeric metric value.
    """

    step: int
    name: str
    value: float


@dataclass(frozen=True)
class ErrorRecord:
    """One error observed during an experiment run.

    Attributes:
        kind: Error kind or code (e.g. ``LLM_RATE_LIMITED``).
        message: Human-readable error message.
        step: Iteration or step index the error occurred at.
    """

    kind: str
    message: str
    step: int


@dataclass(frozen=True)
class ExperimentConfig:
    """Seed-and-config descriptor driving a reproducible experiment run.

    Attributes:
        name: Experiment name; part of the derived run id.
        seed: Seed value; part of the derived run id.
        config: Knob configuration dict (canonical JSON order-insensitive).
        trials: Number of trials per run. Defaults to 1.
        metadata: Free-form run metadata.
    """

    name: str
    seed: int
    config: dict[str, Any]
    trials: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperimentRun:
    """A started experiment run with its identity and config digest.

    Attributes:
        run_id: Stable identifier derived from name, seed, and config.
        experiment: Experiment name.
        seed: Seed value used for this run.
        config: Knob configuration dict.
        config_hash: SHA-256 digest of the canonicalized config.
        status: Lifecycle status of the run.
        started_at: ISO-8601 start timestamp.
        finished_at: ISO-8601 finish timestamp, or ``None`` while running.
    """

    run_id: str
    experiment: str
    seed: int
    config: dict[str, Any]
    config_hash: str
    status: RunStatus
    started_at: str
    finished_at: str | None = None


@dataclass(frozen=True)
class Checkpoint:
    """Content-addressed checkpoint of run state.

    Attributes:
        run_id: Run the checkpoint belongs to.
        slug: Stable name of the checkpoint within the run.
        digest: SHA-256 digest of the canonicalized payload.
        payload: Checkpointed state.
        created_at: ISO-8601 creation timestamp.
    """

    run_id: str
    slug: str
    digest: str
    payload: dict[str, Any]
    created_at: str


@dataclass(frozen=True)
class AblationResult:
    """Delta comparison between a baseline and an ablated checkpoint.

    Attributes:
        run_id: Run the ablation was performed on.
        knob: The configuration knob that was ablated.
        baseline_slug: Checkpoint slug of the baseline run.
        ablated_slug: Checkpoint slug of the ablated run.
        deltas: Per-metric differences (ablated minus baseline).
        digest: SHA-256 digest of the ablation inputs and deltas.
    """

    run_id: str
    knob: str
    baseline_slug: str
    ablated_slug: str
    deltas: dict[str, float]
    digest: str


@dataclass(frozen=True)
class AnalysisReport:
    """Aggregated error and score analysis for a completed run.

    Attributes:
        total_records: Number of metric records analyzed.
        error_count: Number of error records analyzed.
        error_kinds: Error kind to occurrence count mapping.
        score_mean: Mean of records named ``score``, or ``None``.
        score_min: Minimum of records named ``score``, or ``None``.
        score_max: Maximum of records named ``score``, or ``None``.
        top_errors: Most frequent error records, most frequent first.
    """

    total_records: int
    error_count: int
    error_kinds: dict[str, int]
    score_mean: float | None
    score_min: float | None
    score_max: float | None
    top_errors: tuple[ErrorRecord, ...]


class ExperimentTrackerProtocol(Protocol):
    """Persistent, seed-stable tracking of experiment runs.

    Implementations must derive a stable run id from the experiment
    config so rerunning the same seed and knobs resumes (or reproduces)
    the same run.
    """

    async def start(self, config: ExperimentConfig) -> ExperimentRun:
        """Start (or resume) an experiment run for the given config.

        Args:
            config: Seed and knob configuration of the run.

        Returns:
            The started or resumed run.
        """

    async def log_metric(
        self, run_id: str, name: str, value: float, step: int = 0
    ) -> None:
        """Record a scalar metric for a run.

        Args:
            run_id: Run identifier.
            name: Metric name.
            value: Metric value.
            step: Step index the metric was recorded at. Defaults to 0.
        """

    async def log_error(
        self, run_id: str, kind: str, message: str, step: int = 0
    ) -> None:
        """Record an error for a run.

        Args:
            run_id: Run identifier.
            kind: Error kind or code.
            message: Human-readable error message.
            step: Step index the error occurred at. Defaults to 0.
        """

    async def metrics(self, run_id: str) -> list[MetricRecord]:
        """Return all metric records for a run.

        Args:
            run_id: Run identifier.

        Returns:
            Metric records in recording order.
        """

    async def errors(self, run_id: str) -> list[ErrorRecord]:
        """Return all error records for a run.

        Args:
            run_id: Run identifier.

        Returns:
            Error records in recording order.
        """

    async def snapshot(self, run_id: str) -> dict[str, Any]:
        """Return a compact summary of a run's current state.

        Args:
            run_id: Run identifier.

        Returns:
            Latest value per metric, error counts, and run metadata.
        """

    async def resume(self, run_id: str) -> ExperimentRun | None:
        """Return an already-started run, or ``None`` when unknown.

        Args:
            run_id: Run identifier.

        Returns:
            The existing run, or ``None``.
        """

    async def finish(
        self, run_id: str, status: RunStatus = RunStatus.COMPLETED
    ) -> None:
        """Mark a run finished.

        Args:
            run_id: Run identifier.
            status: Terminal status. Defaults to ``COMPLETED``.
        """


class CheckpointStoreProtocol(Protocol):
    """Digest-verified persistence of run checkpoints."""

    async def save(self, run_id: str, slug: str, payload: dict[str, Any]) -> Checkpoint:
        """Persist a checkpoint for a run.

        Args:
            run_id: Run identifier.
            slug: Stable name of the checkpoint within the run.
            payload: State to checkpoint.

        Returns:
            The stored checkpoint with its content digest.
        """

    async def load(self, run_id: str, slug: str) -> Checkpoint | None:
        """Load a checkpoint, verifying its content digest.

        Args:
            run_id: Run identifier.
            slug: Checkpoint name.

        Returns:
            The verified checkpoint, or ``None`` when absent or tampered.
        """

    async def list(self, run_id: str) -> list[Checkpoint]:
        """List all checkpoints for a run.

        Args:
            run_id: Run identifier.

        Returns:
            Checkpoints in creation order.
        """


__all__ = [
    "AblationResult",
    "AnalysisReport",
    "Checkpoint",
    "CheckpointStoreProtocol",
    "ErrorRecord",
    "ExperimentConfig",
    "ExperimentRun",
    "ExperimentTrackerProtocol",
    "MetricRecord",
    "RunStatus",
]
