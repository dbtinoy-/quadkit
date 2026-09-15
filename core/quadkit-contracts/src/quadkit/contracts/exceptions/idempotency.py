"""Exception hierarchy for idempotency support."""

from __future__ import annotations

from quadkit.contracts.exceptions.base import QuadkitError


class IdempotencyError(QuadkitError):
    """Base exception for idempotency flows."""

    _code: str = "QK_ERR_IDEM_001"


class DuplicateRequestError(IdempotencyError):
    """Raised when an idempotent key is reused before completion."""

    _code: str = "QK_ERR_IDEM_002"

    def __init__(self, key: str, message: str | None = None) -> None:
        detail = message or f"Duplicate idempotency key: {key}"
        super().__init__(detail)
        self.key = key
        self.message = detail


class IdempotencyStoreError(IdempotencyError):
    """Raised on unexpected failures inside the idempotency store."""

    _code: str = "QK_ERR_IDEM_003"


class IdempotencyConflictError(IdempotencyError):
    """Raised when an idempotency key is already claimed (PENDING)."""

    _code: str = "QK_ERR_IDEM_004"


__all__ = [
    "DuplicateRequestError",
    "IdempotencyConflictError",
    "IdempotencyError",
    "IdempotencyStoreError",
]
