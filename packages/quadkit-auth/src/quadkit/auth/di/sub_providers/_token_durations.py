"""Resolve JWT lifetimes from typed configuration without losing fractions."""

from __future__ import annotations

import math
from typing import Any

from quadkit.auth import constants as const
from quadkit.contracts.core import Duration
from quadkit.contracts.exceptions import ConfigurationError


def _seconds(config: Any, name: str) -> float | None:
    value = getattr(config, name, None) if config is not None else None
    return value.total_seconds if isinstance(value, Duration) else None


def _legacy(config: Any, name: str, default: float) -> float:
    value = getattr(config, name, default) if config is not None else default
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return default


def token_durations(
    config: Any,
    *,
    access_hours: float | None = None,
    refresh_days: float | None = None,
) -> tuple[float, float, float]:
    """Return access hours, refresh days and key grace seconds.

    Explicit legacy-unit overrides win; actual ``Duration`` settings come
    next. Legacy config-shaped doubles remain supported for existing callers.
    Invalid durations fail configuration rather than silently using a longer
    default. A zero grace period remains valid; token lifetimes must be positive.
    """
    access_seconds = _seconds(config, "access_token_expire")
    refresh_seconds = _seconds(config, "refresh_token_expire")
    grace_seconds = _seconds(config, "key_rotation_grace_period")
    access = (
        access_hours
        if access_hours is not None
        else access_seconds / 3600
        if access_seconds is not None
        else _legacy(config, "access_expiration_hours", 1)
    )
    refresh = (
        refresh_days
        if refresh_days is not None
        else refresh_seconds / 86400
        if refresh_seconds is not None
        else _legacy(
            config, "refresh_expiration_days", const.DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS
        )
    )
    grace = (
        grace_seconds
        if grace_seconds is not None
        else _legacy(
            config,
            "key_rotation_grace_period_seconds",
            const.DEFAULT_JWT_KEY_ROTATION_GRACE_PERIOD_SECONDS,
        )
    )
    for name, value, allow_zero in (
        ("access token lifetime", access, False),
        ("refresh token lifetime", refresh, False),
        ("key rotation grace period", grace, True),
    ):
        if not math.isfinite(value) or value < 0 or (not allow_zero and value == 0):
            raise ConfigurationError(
                f"Invalid {name}: expected a finite {'non-negative' if allow_zero else 'positive'} duration"
            )
    return float(access), float(refresh), float(grace)
