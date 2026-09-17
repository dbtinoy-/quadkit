"""PiiRedactorProtocol — field-name and pattern-based PII redaction."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PiiRedactorProtocol(Protocol):
    """Protocol for PII redaction on audit payloads.

    Implementations redact sensitive fields (by field name or pattern
    matching) from ``dict`` payloads before they are persisted.
    """

    def redact(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return a redacted copy of *payload*.

        Sensitive values are replaced with ``"<redacted>"``.
        The original dict is not mutated.
        """
        ...


__all__ = ["PiiRedactorProtocol"]
