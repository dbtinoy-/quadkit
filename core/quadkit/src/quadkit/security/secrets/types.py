"""Data classes shared by the secret rotation scheduler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass
class SecretRotationResult:
    """Result returned by :class:`SecretRotationScheduler.check_secret`."""

    secret_name: str
    rotation_needed: bool
    warning: bool = False
    expired: bool = False
    age_days: float = 0.0
    message: str = ""


@dataclass
class SecretMetadata:
    """Holds metadata about the lifetime of a secret."""

    name: str
    created_at: datetime | None = None
    last_rotated: datetime | None = None


__all__ = ["SecretMetadata", "SecretRotationResult"]
