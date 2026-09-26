"""SagaProtocol context and result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SagaContext:
    """Mutable context passed through all saga steps."""

    saga_id: str
    saga_name: str
    data: dict[str, Any] = field(default_factory=dict)
    step_results: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SagaStepResult:
    """Result returned from a single saga step."""

    success: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @classmethod
    def Ok(cls, output: dict[str, Any] | None = None) -> SagaStepResult:
        """Create a successful result."""
        return cls(success=True, output=output or {})

    @classmethod
    def fail(cls, error: str) -> SagaStepResult:
        """Create a failed result."""
        return cls(success=False, error=error)
