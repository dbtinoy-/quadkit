"""AsyncStringSerializerProtocol registry for content negotiation.

Provides a central registry for format-specific serializers, allowing
for easy retrieval and Accept-header negotiation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.result import Err, Ok, Result
from quadkit.serialization.exceptions import NegotiationError

if TYPE_CHECKING:
    from quadkit.contracts.core.serialization import SerializerProtocol


class SerializerRegistry:
    """Registry of format-specific serializers."""

    def __init__(self) -> None:
        """Initialize the registry."""
        self._serializers: dict[str, SerializerProtocol] = {}

    def register(self, content_type: str, serializer: SerializerProtocol) -> None:
        """Register a serializer for a specific content type.

        Args:
            content_type: MIME type (e.g., 'application/json').
            serializer: AsyncStringSerializerProtocol instance.
        """
        self._serializers[content_type.lower()] = serializer

    def get(self, content_type: str) -> SerializerProtocol | None:
        """Retrieve the serializer for a content type.

        Args:
            content_type: MIME type.

        Returns:
            AsyncStringSerializerProtocol instance or None if not registered.
        """
        return self._serializers.get(content_type.lower())

    def negotiate(
        self, accept_header: str
    ) -> Result[SerializerProtocol, NegotiationError]:
        """Content negotiation: find best serializer for Accept header.

        Args:
            accept_header: The value of the HTTP Accept header.

        Returns:
            ``Ok(serializer)`` when a matching serializer is found,
            ``Err(NegotiationError)`` when no registered serializer matches.
        """
        if not accept_header:
            serializer = self.get("application/json")
            if serializer is not None:
                return Ok(serializer)
            return Err(NegotiationError(accept_header))

        # Simple negotiation for now: take first match
        for part in accept_header.split(","):
            mime = part.split(";")[0].strip().lower()
            if mime in self._serializers:
                return Ok(self._serializers[mime])
            if mime == "*/*":
                serializer = self.get("application/json")
                if serializer is not None:
                    return Ok(serializer)

        # Default fallback to JSON
        serializer = self.get("application/json")
        if serializer is not None:
            return Ok(serializer)
        return Err(NegotiationError(accept_header))
