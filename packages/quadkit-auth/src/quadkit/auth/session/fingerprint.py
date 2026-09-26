"""Device fingerprinting for Quadkit Auth."""

from __future__ import annotations

import hashlib
from typing import Any

from quadkit import serialization as json


def generate_device_id(fingerprint_data: dict[str, Any]) -> str:
    """Generate a stable device ID from fingerprint data.

    Args:
        fingerprint_data: Dictionary containing client metadata like:
            - user_agent
            - screen_resolution
            - timezone
            - language
            - platform

    Returns:
        A SHA-256 hash representing the unique device.
    """
    # quadkit.serialization.dumps already returns bytes (either from orjson or encoded stdlib)
    normalized_data = json.dumps(fingerprint_data, sort_keys=True)
    return hashlib.sha256(normalized_data).hexdigest()


__all__ = [
    "generate_device_id",
]
