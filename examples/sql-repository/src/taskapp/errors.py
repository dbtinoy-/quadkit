"""Exception hierarchy for the task repository demo — the **error taxonomy** lesson.

Every demo error extends ``TaskError(DomainError)`` so the web pipeline can
map the whole subtree; specific subclasses get explicit HTTP statuses via
``ResultResponseMapper.register(...)`` in the controller:

- ``InvalidStatusError`` → 422 Unprocessable Entity

Framework errors keep their RFC-9457 default mappings
(``ValidationError`` → 422, ``NotFoundError`` → 404).

Handlers return ``Result`` instead of raising — the pipeline renders
``Err`` values as ProblemDetail bodies, so error-to-HTTP mapping lives in
exactly one place.
"""

from __future__ import annotations

from quadkit.contracts.exceptions.domain import DomainError


class TaskError(DomainError):
    """Base error for the task repository demo."""


class InvalidStatusError(TaskError):
    """Raised when a status value is outside the allowed set."""


__all__ = ["InvalidStatusError", "TaskError"]
