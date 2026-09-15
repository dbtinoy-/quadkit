"""Configuration-related exception classes."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from quadkit.contracts.exceptions.base import QuadkitError

if TYPE_CHECKING:
    from quadkit.contracts.core.config import ConfigIssue

_SECRET_PATTERN = re.compile(
    r"(password|secret|token|key|api_key|auth|credential|private)",
    re.IGNORECASE,
)


def _redact_value(field: str, value: Any) -> str:
    """Return redacted display of a field value if the field name looks secret."""
    if _SECRET_PATTERN.search(field):
        return "***"
    if value is None:
        return "(not set)"
    text = str(value)
    return text if len(text) <= 80 else text[:77] + "..."


class ConfigurationError(QuadkitError):
    """Developer configuration or runtime misconfiguration errors.

    Supports optional structured validation errors for integration
    with validation frameworks.

    Attributes:
        validation_errors: A list of per-field error dicts, each containing
            at minimum ``field``, ``message``, and ``type`` keys.
        issues: Typed ``ConfigIssue`` list produced by
            ``BaseConfig.validate_for_environment()``.
    """

    _code = "QK_ERR_CFG_001"

    validation_errors: list[dict[str, Any]]
    issues: list[ConfigIssue]

    def __init__(
        self,
        message: str = "Configuration error",
        *,
        validation_errors: list[dict[str, Any]] | None = None,
        issues: list[ConfigIssue] | None = None,
        **kwargs: Any,
    ) -> None:
        self.validation_errors = validation_errors or []
        self.issues = issues or []
        super().__init__(message, **kwargs)

    @classmethod
    def from_validation_error(cls, error: Exception) -> ConfigurationError:
        """Create a ``ConfigurationError`` from a ``ValidationError``.

        Supports both the contracts ``ValidationError`` (with ``.errors``
        attribute) and pydantic's ``ValidationError`` (with ``.errors()``
        method) for backwards compatibility.

        Args:
            error: A ``ValidationError`` instance from either
                ``quadkit.contracts.validation`` or ``pydantic``.

        Returns:
            A new ``ConfigurationError`` with structured ``validation_errors``.
        """
        # Get error list: .errors (attribute) or .errors() (pydantic method)
        if hasattr(error, "errors") and callable(error.errors):
            raw_errors = error.errors()
        elif hasattr(error, "errors"):
            raw_errors = error.errors
        else:
            return cls(str(error))

        messages: list[str] = []
        details: list[dict[str, Any]] = []
        for err in raw_errors:
            # Support both FieldError objects and pydantic-style dicts
            if hasattr(err, "field") and hasattr(err, "message"):
                loc_str = err.field
                msg = err.message
                err_type = getattr(err, "code", "validation_error")
                raw_value = getattr(err, "input", None)
            else:
                loc = err.get("loc", ())
                loc_str = " → ".join(str(part) for part in loc) if loc else "unknown"
                msg = err.get("msg", str(err))
                err_type = err.get("type", "validation_error")
                raw_value = err.get("input", None)
            displayed_value = _redact_value(loc_str, raw_value)
            entry: dict[str, Any] = {
                "field": loc_str,
                "message": msg,
                "type": err_type,
                "value": displayed_value,
            }
            details.append(entry)
            messages.append(f"  {loc_str}: {msg} (got: {displayed_value})")

        return cls(
            "Configuration validation failed:\n" + "\n".join(messages),
            validation_errors=details,
        )

    @classmethod
    def from_issues(cls, issues: list[ConfigIssue]) -> ConfigurationError:
        """Create a ``ConfigurationError`` from a list of ``ConfigIssue`` objects.

        Only issues with ``severity == "error"`` contribute to the message.
        All issues (errors **and** warnings) are stored on ``self.issues``.

        Args:
            issues: List of ``ConfigIssue`` instances produced by
                ``BaseConfig.validate_for_environment()``.

        Returns:
            A new ``ConfigurationError`` carrying the typed issue list.
        """
        error_issues = [i for i in issues if i.severity == "error"]
        lines = [f"  {i.field}: {i.message}" for i in error_issues]
        message = "Configuration validation failed:\n" + "\n".join(lines)
        return cls(message, issues=list(issues))


__all__ = ["ConfigurationError"]
