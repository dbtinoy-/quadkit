"""Type definitions for quadkit core security."""

from __future__ import annotations

from quadkit.contracts.security.rotation import (
    SecretRotationPolicy as SecretRotationPolicy,  # re-export
)

__all__ = ["SecretRotationPolicy"]
