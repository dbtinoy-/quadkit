"""Canonical JSON serialization for content-addressed hashing.

Deterministic JSON bytes output with sorted keys and compact separators,
ensuring the same logical object always produces identical bytes across
runs and processes.
"""

from __future__ import annotations

from typing import Any

import quadkit.serialization as json

__all__ = ["canonical_json_bytes"]


def canonical_json_bytes(obj: Any) -> bytes:
    """Serialize *obj* to canonical JSON bytes.

    Uses sorted keys and compact separators so the output is deterministic
    across runs and processes — suitable for content-addressed hashing.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
