"""CLI doctor checks for quadkit-events."""

from __future__ import annotations


def check_event_store() -> dict[str, object]:
    """Check event store backend is configured.

    Returns:
        A DoctorCheckResult-compatible dict.
    """
    return {
        "status": "ok",
        "message": "Event store configuration check not yet implemented",
    }
