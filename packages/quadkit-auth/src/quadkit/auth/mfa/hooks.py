"""Lifecycle hooks for auth/mfa — intercepted when MFA operations occur."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["MFAChallengeIssuedHook", "MFAFailedHook", "MFAVerifiedHook"]


@dataclass(frozen=True, kw_only=True)
class MFAChallengeIssuedHook:
    """Payload fired when an MFA challenge is issued to a user.

    Attributes:
        user_id: Identifier of the user receiving the MFA challenge.
        method: MFA method used (e.g. ``"totp"``, ``"backup_code"``).
    """

    user_id: str
    method: str


@dataclass(frozen=True, kw_only=True)
class MFAVerifiedHook:
    """Payload fired when MFA verification succeeds.

    Attributes:
        user_id: Identifier of the user whose MFA was verified.
        method: MFA method that was verified (e.g. ``"totp"``, ``"backup_code"``).
    """

    user_id: str
    method: str


@dataclass(frozen=True, kw_only=True)
class MFAFailedHook:
    """Payload fired when MFA verification fails.

    Attributes:
        user_id: Identifier of the user whose MFA failed.
        method: MFA method that failed (e.g. ``"totp"``, ``"backup_code"``).
        reason: Short description of why verification failed.
    """

    user_id: str
    method: str
    reason: str
