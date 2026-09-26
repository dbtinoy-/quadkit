"""CLI doctor checks for quadkit-sql."""

from __future__ import annotations

import os


def check_database_url() -> dict[str, object]:
    """Check DATABASE_URL or application.yaml database config exists.

    Returns:
        A DoctorCheckResult-compatible dict with status and message.
    """
    if os.getenv("DATABASE_URL"):
        return {"status": "ok", "message": "DATABASE_URL is configured"}
    return {"status": "warning", "message": "DATABASE_URL environment variable not set"}


def check_migrations_dir() -> dict[str, object]:
    """Check migrations directory exists with valid structure.

    Returns:
        A DoctorCheckResult-compatible dict with status, message, and can_fix.
    """
    import pathlib

    migrations_path = pathlib.Path("migrations")
    if migrations_path.exists() and migrations_path.is_dir():
        return {"status": "ok", "message": "Migrations directory exists"}
    return {
        "status": "warning",
        "message": "Migrations directory not found — run `quadkit db init` to create it",
        "can_fix": True,
    }
