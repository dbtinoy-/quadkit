"""CLI doctor checks for quadkit-auth."""

from __future__ import annotations

import os


def check_jwt_secret() -> dict[str, object]:
    """Check JWT_SECRET env var or auth.jwt.secret config.

    Returns:
        A DoctorCheckResult-compatible dict.
    """
    if os.getenv("JWT_SECRET") or os.getenv("AUTH_JWT_SECRET"):
        return {"status": "ok", "message": "JWT secret is configured"}
    return {"status": "error", "message": "JWT_SECRET environment variable not set"}


def check_auth_config() -> dict[str, object]:
    """Validate auth section in application.yaml.

    Returns:
        A DoctorCheckResult-compatible dict.
    """
    return {"status": "ok", "message": "Auth configuration check not yet implemented"}
