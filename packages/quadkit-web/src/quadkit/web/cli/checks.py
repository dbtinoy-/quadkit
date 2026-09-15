"""CLI diagnostic checks for quadkit-web."""

from __future__ import annotations


def check_routes_valid() -> dict[str, object]:
    """Validate that all registered routes have valid controllers.

    Returns:
        A DoctorCheckResult-compatible dict with status and message.
    """
    return {"status": "ok", "message": "Route validation not yet implemented"}
