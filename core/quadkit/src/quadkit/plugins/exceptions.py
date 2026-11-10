"""Exception types for the quadkit-plugins package."""

from __future__ import annotations

from quadkit.contracts.exceptions.infra import InfrastructureError

__all__ = ["PluginStateError"]


class PluginStateError(InfrastructureError):
    """Raised when plugin enable/disable state cannot be persisted or read.

    The admin surface converts this into a flash message and audit entry —
    a storage failure must never surface as an unhandled 500.

    The optional ``path`` argument is accepted for compatibility but is
    intentionally discarded so local filesystem paths are never retained on
    the exception.
    """

    _code = "QK_ERR_INFRA_012"

    def __init__(self, message: str, *, path: str | None = None) -> None:
        super().__init__(message)
        self.path = None
