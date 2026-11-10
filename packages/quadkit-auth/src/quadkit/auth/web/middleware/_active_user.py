"""Fail-closed account status check shared by request authenticators."""

from __future__ import annotations


def is_active_user(user: object) -> bool:
    """Accept only the explicit boolean active flag required by UserProtocol.

    A missing or malformed flag must not authenticate as an active account.
    """
    return getattr(user, "is_active", None) is True
