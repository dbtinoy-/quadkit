"""Backend-independent intent digests; no duplicate copy of private mail content."""

from __future__ import annotations

from hashlib import sha256
import math
from typing import Any

from quadkit.contracts.notification.inbox import InboxMessage
from quadkit.serialization import dumps_str


def validate_key(key: str) -> None:
    """Reject ambiguous or unbounded server delivery identities."""
    if not isinstance(key, str) or not key.strip() or len(key) > 512 or "\x00" in key:
        raise ValueError(
            "inbox delivery key must be non-empty and at most 512 characters"
        )


def _canonical(value: Any, ancestors: frozenset[int] = frozenset()) -> list[Any]:
    """Tag JSON types explicitly; float representation is encoder independent."""
    if value is None:
        return ["null"]
    if isinstance(value, bool):
        return ["bool", str(value)]
    if isinstance(value, str):
        value.encode("utf-8")
        return ["str", value]
    if isinstance(value, int):
        return ["int", str(value)]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("inbox metadata must contain finite JSON numbers")
        return ["float", value.hex()]
    if not isinstance(value, (list, dict)):
        raise TypeError("inbox metadata must contain JSON values")
    if id(value) in ancestors:
        raise ValueError("inbox metadata must not contain cycles")
    seen = ancestors | {id(value)}
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("inbox metadata keys must be strings")
        return ["dict", [[key, _canonical(value[key], seen)] for key in sorted(value)]]
    return ["list", [_canonical(item, seen) for item in value]]


def fingerprint(message: InboxMessage) -> str:
    """Hash immutable send intent, excluding generated/read-state fields."""
    if not all(
        isinstance(v, str) for v in (message.user_id, message.title, message.body)
    ):
        raise TypeError("inbox recipient, title and body must be strings")
    if not message.user_id.strip():
        raise ValueError("a resolved recipient user ID is required")
    intent = [message.user_id, message.title, message.body, message.metadata]
    return sha256(dumps_str(_canonical(intent)).encode("utf-8")).hexdigest()
