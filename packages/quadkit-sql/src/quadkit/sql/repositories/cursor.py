"""Cursor-based pagination for efficient large-dataset traversal.

Cursor pagination avoids the performance pitfalls of OFFSET-based pagination
by using a cursor (encoded position marker) to fetch the next page.

Example:
    # First page
    page = await repo.paginate_cursor(limit=20, sort_by="created_at")

    # Next page
    page2 = await repo.paginate_cursor(
        cursor=page.next_cursor,
        limit=20,
        sort_by="created_at",
    )
"""

from __future__ import annotations

import base64
from typing import Any, TypeVar

from quadkit import serialization as json
from quadkit.contracts.domain.pagination import CursorPage

TEntity = TypeVar("TEntity")

__all__ = ["CursorPage", "decode_cursor", "encode_cursor"]


def encode_cursor(values: dict[str, Any]) -> str:
    """Encode cursor values into an opaque base64 string.

    Args:
        values: Dictionary of sort field values at the cursor position.

    Returns:
        Base64-encoded cursor string.
    """
    # Convert non-serializable types
    serializable = {}
    for k, v in values.items():
        if hasattr(v, "isoformat"):
            serializable[k] = {"__type__": "datetime", "value": v.isoformat()}
        else:
            serializable[k] = v

    json_bytes = json.dumps(serializable, default=str)
    return base64.urlsafe_b64encode(json_bytes).decode("ascii")


def decode_cursor(cursor: str) -> dict[str, Any]:
    """Decode an opaque cursor string back into values.

    Args:
        cursor: Base64-encoded cursor string.

    Returns:
        Dictionary of sort field values.
    """
    try:
        json_bytes = base64.urlsafe_b64decode(cursor.encode("ascii"))
        data = json.loads(json_bytes)
        # Restore datetime types
        result = {}
        for k, v in data.items():
            if isinstance(v, dict) and v.get("__type__") == "datetime":
                from datetime import datetime

                result[k] = datetime.fromisoformat(v["value"])
            else:
                result[k] = v
        return result
    except (ValueError, json.JSONDecodeError, KeyError) as e:
        raise ValueError(f"Invalid cursor: {e}") from e
