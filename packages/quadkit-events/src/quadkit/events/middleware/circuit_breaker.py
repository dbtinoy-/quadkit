"""Circuit breaker middleware for CQRS buses (N-03).

Extracted from middleware/retry.py where it did not belong.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.events.messages.base import Message
from quadkit.events.middleware.base import AbstractMiddleware, NextHandler
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.infra.resilience import CircuitBreakerProtocol

logger = get_logger(__name__)


class CircuitBreakerMiddleware(AbstractMiddleware[Message, Any]):
    """Circuit breaker middleware to prevent cascading failures.

    Accepts an optional pre-built ``circuit_breaker`` (injected via DI when
    ``the optional provider`` is available).  When no breaker is provided the
    middleware is a no-op (fail-open), passing messages through unchanged.

    Example::

        circuit_breaker = CircuitBreakerMiddleware(
            circuit_breaker=container.resolve(CircuitBreakerProtocol),
        )
        bus.use(circuit_breaker)
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        success_threshold: int = 3,
        monitored_exceptions: tuple[type[Exception], ...] | None = None,
        circuit_breaker: CircuitBreakerProtocol | None = None,
    ) -> None:
        self._breaker = circuit_breaker

    @property
    def state(self) -> str:
        """Get current state of the circuit breaker."""
        if self._breaker is None:
            return "closed"
        return self._breaker.state

    async def __call__(self, message: Message, next_handler: NextHandler) -> Any:
        if self._breaker is None:
            return await next_handler(message)
        try:
            return await self._breaker.call(next_handler, message)
        except Exception as e:  # noqa: BLE001 — translates ContractsCircuitBreakerError to events CircuitBreakerError; re-raises all others
            from quadkit.contracts.exceptions.resilience import (
                CircuitBreakerError,
            )
            from quadkit.contracts.exceptions.resilience import (
                CircuitBreakerError as ContractsCircuitBreakerError,
            )

            if isinstance(e, ContractsCircuitBreakerError):
                raise CircuitBreakerError(f"Circuit breaker is {self.state}") from e
            raise


__all__ = ["CircuitBreakerMiddleware"]
