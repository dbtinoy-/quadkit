# quadkit-contracts/src/quadkit/contracts/mailer/errors.py
"""Mailer error types."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions.domain import DomainError


class MailerError(DomainError):
    """Base mailer/email notification error."""

    _code = "QK_ERR_NOTIF_002"

    def __init__(
        self,
        message: str = "Mailer error",
        *,
        backend: str = "unknown",
        **kwargs: Any,
    ) -> None:
        details = {"backend": backend, **kwargs.pop("details", {})}
        super().__init__(message, details=details, **kwargs)
        self.backend = backend


__all__ = ["MailerError"]
