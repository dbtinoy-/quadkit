"""Safe text helpers for task failure messages."""

from __future__ import annotations

__all__ = ["safe_failure_message"]


_PREFIX = "Task failed ("


def safe_failure_message(message: str) -> str:
    """Keep only an explicit exception-type label from a failure message.

    Task failures can carry private inputs, identifiers, and filesystem paths.
    The only free-form string shape retained is one generated from
    ``safe_error_type`` at the exception boundary; all other text becomes a
    generic failure message.
    """
    if message.startswith(_PREFIX) and message.endswith(")"):
        error_type = message[len(_PREFIX) : -1]
        if error_type.isidentifier():
            return f"{_PREFIX}{error_type})"
    return "Task failed"
