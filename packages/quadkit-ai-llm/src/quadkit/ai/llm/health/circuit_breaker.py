"""Circuit breaker pattern for provider health management."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from quadkit.logging import get_logger, safe_error_type

logger = get_logger(__name__)


class CircuitState(StrEnum):
    """Circuit breaker state enumeration."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, block requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for provider circuit breaker.

    Attributes:
        failure_threshold: Errors before opening circuit
        success_threshold: Successes before closing from half-open
        timeout_seconds: Time in open state before half-open
        window_size: Number of recent requests to track
    """

    failure_threshold: int = 5
    success_threshold: int = 2
    timeout_seconds: int = 60
    window_size: int = 20


class ProviderCircuitBreaker:
    """Implements circuit breaker pattern for provider failures.

    Automatically stops requests to a provider after repeated failures,
    and gradually recovers when it becomes healthy again.

    Recovery semantics (single-probe half-open):

    - CLOSED → OPEN once ``failure_threshold`` failures accumulate.
    - OPEN blocks all requests until ``timeout_seconds`` elapse.
    - OPEN → HALF_OPEN after the timeout, admitting **at most one probe
      request at a time** — concurrent callers are blocked until the
      probe resolves, so a failing provider is never flooded during
      recovery.
    - A failed probe re-opens the circuit **immediately** (back to the
      full timeout); successful probes count toward
      ``success_threshold``, and reaching it closes the circuit.
    """

    def __init__(
        self,
        provider_name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            provider_name: Provider identifier
            config: Circuit breaker configuration
        """
        self.provider_name = provider_name
        self.config = config or CircuitBreakerConfig()

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: datetime | None = None
        self.opened_at: datetime | None = None
        self.request_times: list[datetime] = []
        self._probe_in_flight = False

    async def record_success(self) -> None:
        """Record a successful request.

        In HALF_OPEN the request is the in-flight probe: it resolves the
        probe and counts toward ``success_threshold`` (CLOSED on reach).
        """
        now = datetime.now(UTC)
        self.request_times.append(now)

        # Prune old requests
        cutoff = now - timedelta(seconds=self.config.timeout_seconds)
        self.request_times = [t for t in self.request_times if t > cutoff]

        self._probe_in_flight = False
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._close()
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    async def record_failure(self, error: Exception) -> None:
        """Record a failed request.

        In HALF_OPEN a failed probe re-opens the circuit immediately; in
        CLOSED failures accumulate toward ``failure_threshold``.

        Args:
            error: Exception that occurred
        """
        now = datetime.now(UTC)
        self.last_failure_time = now
        self.failure_count += 1
        self._probe_in_flight = False

        if self.state == CircuitState.HALF_OPEN:
            self._open(now)
        elif self.failure_count >= self.config.failure_threshold:
            if self.state != CircuitState.OPEN:
                self._open(now)

        logger.warning(
            "provider_failure_recorded",
            failure_count=self.failure_count,
            circuit_state=self.state.value,
            error_type=safe_error_type(error),
        )

    async def is_available(self) -> bool:
        """Check if provider is available for requests.

        HALF_OPEN admits at most one probe request at a time; further
        callers wait for it to resolve.

        Returns:
            False if the circuit is OPEN or a recovery probe is in
            flight, True otherwise.
        """
        if self.state == CircuitState.OPEN:
            # Check if we should transition to HALF_OPEN
            if self.opened_at:
                elapsed = datetime.now(UTC) - self.opened_at
                if elapsed.total_seconds() >= self.config.timeout_seconds:
                    self._half_open()
                    return self._try_admit_probe()
            return False

        if self.state == CircuitState.HALF_OPEN:
            return self._try_admit_probe()

        return True

    def _try_admit_probe(self) -> bool:
        """Admit the single recovery probe (first caller wins).

        Atomic within the event loop: no await between the check and the
        flag set, so two coroutines cannot both be admitted.
        """
        if self._probe_in_flight:
            return False
        self._probe_in_flight = True
        return True

    def _open(self, now: datetime) -> None:
        """Transition to OPEN state."""
        self.state = CircuitState.OPEN
        self.opened_at = now
        self.success_count = 0

        logger.error(
            "circuit_breaker_opened",
            failure_count=self.failure_count,
        )

    def _half_open(self) -> None:
        """Transition to HALF_OPEN state."""
        self.state = CircuitState.HALF_OPEN
        self.failure_count = 0
        self.success_count = 0

        logger.info("circuit_breaker_half_open")

    def _close(self) -> None:
        """Transition to CLOSED state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.opened_at = None

        logger.info("circuit_breaker_closed")

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.opened_at = None
        self.request_times = []
        self._probe_in_flight = False
