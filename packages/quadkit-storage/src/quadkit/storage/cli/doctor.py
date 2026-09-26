"""CLI doctor checks for quadkit-storage."""

from __future__ import annotations


def check_storage_configured() -> dict[str, object]:
    """Check storage backend is configured.

    Returns:
        A DoctorCheckResult-compatible dict.
    """
    return {
        "status": "ok",
        "message": "Storage configuration check not yet implemented",
    }
