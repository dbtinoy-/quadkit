"""Cursor codec for keyset pagination.

Encodes and decodes opaque cursor strings used by cursor-based pagination.
Cursors are base64-encoded JSON objects mapping sort/key field names to values.
"""

from __future__ import annotations

import base64
from typing import Any, cast

from quadkit.serialization import dumps_str as _json_dumps
from quadkit.serialization import loads_str
from quadkit.sql.exceptions import CursorError


class CursorCodec:
    """Encodes and decodes opaque pagination cursors.

    Cursors are base64url-encoded JSON objects.  They are opaque to callers
    but carry the field values required to continue keyset pagination from a
    given position.

    Example::

        codec = CursorCodec()
        token = codec.encode({"id": "abc", "created_at": "2024-01-01"})
        values = codec.decode(token)  # {"id": "abc", "created_at": "2024-01-01"}
    """

    def encode(self, values: dict[str, Any]) -> str:
        """Encode a dictionary of field values into an opaque cursor string.

        Args:
            values: Mapping of field names to their cursor values.

        Returns:
            A base64url-encoded cursor string.
        """
        payload = _json_dumps(values)
        return base64.urlsafe_b64encode(payload.encode()).decode()

    def decode(self, cursor: str) -> dict[str, Any]:
        """Decode an opaque cursor string back into field values.

        Args:
            cursor: A base64url-encoded cursor string previously produced by
                :meth:`encode`.

        Returns:
            The original field-value mapping.

        Raises:
            CursorError: If the cursor is malformed or cannot be decoded.
        """
        try:
            payload = base64.urlsafe_b64decode(cursor.encode()).decode()
            return cast("dict[str, Any]", loads_str(payload))
        except (ValueError, UnicodeDecodeError) as exc:
            raise CursorError(f"Invalid cursor: {cursor!r}") from exc


__all__ = ["CursorCodec"]
