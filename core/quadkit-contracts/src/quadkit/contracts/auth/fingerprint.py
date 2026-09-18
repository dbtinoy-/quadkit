"""Device fingerprinting utilities for session management.

Defined in quadkit-contracts so that any package (auth, admin, etc.) can
generate stable device identifiers without creating a cross-extension dependency.
"""

from __future__ import annotations

import hashlib
import importlib
from typing import Any

__all__ = ["generate_device_id"]

_json_module = importlib.import_module("json")


def generate_device_id(fingerprint_data: dict[str, Any]) -> str:
    """Generate a stable device ID from fingerprint data.

    Produces a deterministic SHA-256 hex digest from a JSON-serialised
    snapshot of the client metadata supplied in *fingerprint_data*.

    Args:
        fingerprint_data: Dictionary containing client metadata such as
            ``user_agent``, ``screen_resolution``, ``timezone``,
            ``language``, and ``platform``.

    Returns:
        A 64-character SHA-256 hex digest that uniquely identifies the device.
    """
    serialized: bytes = _json_module.dumps(
        fingerprint_data,
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()
