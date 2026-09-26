from __future__ import annotations


def safe_error_message(exc: Exception) -> str:
    """Return a generic, leak-free failure message for a health check.

    The returned string contains only the exception type name and never
    ``str(exc)``, which can embed connection details (host, port, DSN
    fragments) in the JSON health payload.  The full exception detail is
    logged separately by callers.

    Args:
        exc: The exception raised by the checked dependency.

    Returns:
        A message of the form ``"<ExceptionType>: connection check failed"``.
    """
    return f"{type(exc).__name__}: connection check failed"
