# quadkit-contracts/src/quadkit/contracts/queue/errors.py
"""Queue error types."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions.domain import DomainError


class QueueError(DomainError):
    """Base for expected, recoverable queue / bus failures.

    Attributes:
        backend: Name of the queue backend (e.g. "redis", "kafka").
        topic: Topic or queue name where the failure occurred.
    """

    _code = "QK_ERR_QUEUE_001"

    def __init__(
        self,
        message: str = "Queue error",
        *,
        backend: str = "unknown",
        topic: str = "unknown",
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        details["backend"] = backend
        details["topic"] = topic
        super().__init__(message, details=details, **kwargs)
        self.backend = backend
        self.topic = topic


__all__ = ["QueueError"]
