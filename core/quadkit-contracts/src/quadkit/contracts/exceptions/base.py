"""Base exception classes for Quadkit Framework.

This module contains the canonical exception hierarchy for the entire Quadkit
ecosystem. All framework exceptions should inherit from QuadkitError.
"""

from __future__ import annotations

from typing import Any, Self


class QuadkitError(Exception):
    """Root exception for the entire Quadkit ecosystem.

    All Quadkit exceptions inherit from this class. This ensures that
    isinstance checks work identically across core, events, web, and
    all subpackages.

    Attributes:
        code: Machine-readable error code (e.g., 'QK_CONTAINER_001')
        message: Human-readable error message
        details: Additional context dictionary
        cause: Original exception that triggered this one
        hint: Optional suggestion for fixing the error
    """

    _code: str = "QK_ERR_CORE_001"

    def __init__(
        self,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
        hint: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.message = message or "An internal error occurred"
        self.code = self._code
        self.details = details or {}
        self.cause = cause
        self.hint = hint
        super().__init__(self.message)

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__}(code={self.code!r}, message={self.message!r})"
        )

    @property
    def docs_url(self) -> str:
        """Return the documentation URL for this error code."""
        return f"https://quadkit.dev/reference/errors/{self.code}"

    def __str__(self) -> str:
        base = f"[{self.code}] {self.message}"
        if self.hint:
            base += f"\n  → Fix: {self.hint}"
        if self.code != "QK_ERR_CORE_001":
            base += f"\n  → See: {self.docs_url}"
        return base

    def to_dict(self) -> dict[str, Any]:
        """Serialize exception to dictionary for logging/API responses."""
        result: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }
        if self.hint:
            result["hint"] = self.hint
        if self.cause is not None:
            result["cause"] = {
                "type": type(self.cause).__name__,
                "message": str(self.cause),
            }
        return result

    def with_details(self, **kwargs: Any) -> Self:
        """Return self with additional detail key-value pairs merged in.

        Mutates and returns self to preserve the exception subtype.
        """
        self.details = {**self.details, **kwargs}
        return self

    def with_hint(self, hint: str) -> Self:
        """Return self with a human-readable hint attached."""
        self.hint = hint
        return self

    def with_cause(self, cause: BaseException) -> Self:
        """Return self with ``__cause__`` set to ``cause``."""
        self.cause = cause
        self.__cause__ = cause
        return self

    def format(self) -> str:
        """Format for developer-friendly console output.

        Returns a multi-line string containing the error class name, code,
        message, details, hint, and cause chain when present.
        """
        lines = []
        lines.append(f"\n{type(self).__name__} [{self.code}]\n")
        lines.append(f"  {self.message}\n")

        if self.details:
            lines.append("")
            for key, value in self.details.items():
                lines.append(f"    {key}: {value}")
            lines.append("")

        if self.hint:
            lines.append(f"  Hint: {self.hint}\n")

        if self.__cause__:
            lines.append(
                f"  Caused by: {type(self.__cause__).__name__}: {self.__cause__}",
            )

        return "\n".join(lines)


__all__ = ["QuadkitError"]
