"""CLI doctor checks for quadkit-notification."""

from __future__ import annotations

import os


def check_smtp_config() -> dict[str, object]:
    """Check SMTP configuration is present.

    Looks for ``SMTP_HOST`` environment variable.

    Returns:
        A DoctorCheckResult-compatible dict.
    """
    if os.environ.get("SMTP_HOST"):
        return {"status": "ok", "message": "SMTP_HOST is configured"}
    return {
        "status": "warning",
        "message": "SMTP_HOST is not set. Email notifications may not work.",
    }


def check_push_credentials() -> dict[str, object]:
    """Check push notification credentials are configured.

    Looks for ``FCM_SERVER_KEY`` or ``APNS_KEY_PATH`` environment variables.

    Returns:
        A DoctorCheckResult-compatible dict.
    """
    if os.environ.get("FCM_SERVER_KEY"):
        return {"status": "ok", "message": "FCM_SERVER_KEY is configured"}
    if os.environ.get("APNS_KEY_PATH"):
        return {"status": "ok", "message": "APNS_KEY_PATH is configured"}
    return {
        "status": "warning",
        "message": "No push credentials found. Set FCM_SERVER_KEY or APNS_KEY_PATH.",
    }
