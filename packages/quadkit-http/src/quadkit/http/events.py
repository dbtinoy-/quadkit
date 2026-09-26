"""Domain events for HTTP client operations."""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.contracts.domain.events import DomainEvent


@dataclass(frozen=True, init=False)
class RequestRetryExhaustedEvent(DomainEvent):
    """HTTP request exhausted all retry attempts.

    Consumed by: retry management, circuit breaker logic, error reporting.
    """

    url: str
    method: str
    attempt_count: int


@dataclass(frozen=True, init=False)
class RequestTimeoutEvent(DomainEvent):
    """HTTP request timed out before completion.

    Consumed by: timeout tracking, performance monitoring, alerting.
    """

    url: str
    method: str
    timeout_seconds: float


@dataclass(frozen=True, init=False)
class RequestCompletedEvent(DomainEvent):
    """HTTP request completed successfully.

    Consumed by: request metrics, audit logging, performance analysis.
    """

    url: str
    method: str
    status_code: int
