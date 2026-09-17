"""Evaluation protocols and types for AI evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from quadkit.contracts.ai.exceptions import EvaluationError
from quadkit.contracts.core.result import Result


class EvaluationScoreType(str, Enum):
    """Type of evaluation score."""

    EXACT_MATCH = "exact_match"
    PARTIAL_MATCH = "partial_match"
    SEMANTIC_SIMILARITY = "semantic_similarity"
    STRING_DISTANCE = "string_distance"
    TRAJECTORY_FIDELITY = "trajectory_fidelity"
    CUSTOM = "custom"


@dataclass(frozen=True)
class EvaluationResult:
    """Result of an evaluation run on a single sample.

    Attributes:
        score: The evaluation score (0.0 to 1.0).
        score_type: The type of scoring method used.
        feedback: Human-readable feedback about the evaluation.
        metrics: Additional metrics computed during evaluation.
    """

    score: float
    score_type: EvaluationScoreType
    feedback: str
    metrics: dict[str, Any]


@dataclass(frozen=True)
class EvaluationSample:
    """A single sample in an evaluation dataset.

    Attributes:
        id: Unique identifier for this sample.
        input: The input prompt or query.
        reference: The expected reference output.
        metadata: Additional metadata for this sample.
        output: The pre-computed model output being evaluated. Offline
            datasets carry the generated output here; leave empty for
            datasets that only compare against the reference.
    """

    id: str
    input: str
    reference: str
    metadata: dict[str, Any]
    output: str = ""


@dataclass(frozen=True)
class EvaluationDataset:
    """A collection of evaluation samples.

    Attributes:
        name: Name of the dataset.
        samples: List of evaluation samples.
        metadata: Additional dataset metadata.
    """

    name: str
    samples: list[EvaluationSample]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class RunReport:
    """Report from running an evaluator on a dataset.

    Attributes:
        dataset_name: Name of the evaluated dataset.
        evaluator_name: Name of the evaluator used.
        total_samples: Total number of samples evaluated.
        passed_samples: Number of samples that passed the evaluation.
        average_score: Average score across all samples.
        results: Individual sample results.
        metadata: Additional report metadata.
    """

    dataset_name: str
    evaluator_name: str
    total_samples: int
    passed_samples: int
    average_score: float
    results: list[EvaluationResult]
    metadata: dict[str, Any]


class EvaluatorProtocol(Protocol):
    """Protocol for evaluation implementations.

    An evaluator takes an input, output, and reference and produces
    an evaluation result with a score and feedback.
    """

    @property
    def name(self) -> str:
        """Return the evaluator name."""

    async def evaluate(
        self,
        input: str,
        output: str,
        reference: str,
    ) -> Result[EvaluationResult, Exception]:
        """Evaluate a single sample.

        Args:
            input: The input prompt or query.
            output: The generated output to evaluate.
            reference: The expected reference output.

        Returns:
            Ok(EvaluationResult) on success, Err(error) on failure.
        """


class EvaluationHarnessProtocol(Protocol):
    """Protocol for evaluation harness implementations.

    A harness runs an evaluator against a dataset and produces
    a run report with aggregated results.
    """

    @property
    def name(self) -> str:
        """Return the harness name."""

    async def run(
        self,
        dataset: EvaluationDataset,
        evaluator: EvaluatorProtocol,
    ) -> Result[RunReport, Exception]:
        """Run an evaluator against a dataset.

        Args:
            dataset: The evaluation dataset.
            evaluator: The evaluator to use.

        Returns:
            Ok(RunReport) on success, Err(error) on failure.
        """


__all__ = [
    "EvaluationDataset",
    "EvaluationError",
    "EvaluationHarnessProtocol",
    "EvaluationResult",
    "EvaluationSample",
    "EvaluationScoreType",
    "EvaluatorProtocol",
    "RunReport",
]
