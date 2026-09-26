"""Local circuit breaker backend types for quadkit-cache.

This module provides local type definitions to avoid cross-package imports
from the optional provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class CircuitBreakerState:
    """Serialized circuit breaker state for distributed storage."""

    name: str
    state: CircuitState
    failure_count: int
    success_count: int
    last_failure_time: float | None
    last_success_time: float | None
    last_state_change: float


class CircuitBreakerBackend(Protocol):
    """Protocol for circuit breaker state backends.

    Implement this to enable distributed circuit breakers
    across multiple processes or containers.
    """

    async def get_state(self, name: str) -> CircuitBreakerState | None:
        """Get circuit breaker state by name.

        Args:
            name: Circuit breaker name.

        Returns:
            State if exists, None otherwise.
        """
        ...

    async def set_state(self, name: str, state: CircuitBreakerState) -> None:
        """Set circuit breaker state.

        Args:
            name: Circuit breaker name.
            state: State to store.
        """
        ...

    async def delete_state(self, name: str) -> None:
        """Delete circuit breaker state.

        Args:
            name: Circuit breaker name.
        """
        ...


from quadkit.contracts.infra.resilience import (
    CircuitState as CircuitState,  # re-export
)

__all__ = [
    "CircuitBreakerBackend",
    "CircuitBreakerState",
    "CircuitState",
]
