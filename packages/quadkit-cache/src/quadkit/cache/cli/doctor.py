"""CLI doctor checks for quadkit-cache."""

from __future__ import annotations


def check_cache_configured() -> dict[str, object]:
    """Check cache backend is configured.

    Returns:
        A DoctorCheckResult-compatible dict.
    """
    return {"status": "ok", "message": "Cache configuration check not yet implemented"}
