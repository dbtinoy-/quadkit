"""Content negotiation based on Accept header."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from quadkit.web.serialization.serializers import (
    AbstractMediaSerializer,
    HTMLSerializer,
    JSONSerializer,
    PlainTextSerializer,
    XMLSerializer,
)

if TYPE_CHECKING:
    from starlette.requests import Request as StarletteRequest
    from starlette.responses import Response as StarletteResponse


class ContentNegotiator:
    """Handles content negotiation based on Accept header."""

    # Default priority order for content negotiation
    DEFAULT_PRIORITY = [
        "application/json",
        "text/html",
        "text/plain",
        "application/xml",
        "*/*",
    ]

    def __init__(self, serializers: list[AbstractMediaSerializer] | None = None):
        """Initialize with optional custom serializers."""
        self._serializers: dict[str, AbstractMediaSerializer] = {}

        # Register default serializers if none provided
        if serializers:
            for serializer in serializers:
                for media_type in serializer.supported_types():
                    self._serializers[media_type] = serializer
        else:
            # Register built-in serializers
            json_ser = JSONSerializer()
            html_ser = HTMLSerializer()
            text_ser = PlainTextSerializer()
            xml_ser = XMLSerializer()

            for mt in json_ser.supported_types():
                self._serializers[mt] = json_ser
            for mt in html_ser.supported_types():
                self._serializers[mt] = html_ser
            for mt in text_ser.supported_types():
                self._serializers[mt] = text_ser
            for mt in xml_ser.supported_types():
                self._serializers[mt] = xml_ser

    def add_serializer(self, serializer: AbstractMediaSerializer) -> None:
        """Add a custom serializer."""
        for media_type in serializer.supported_types():
            self._serializers[media_type] = serializer

    def negotiate(self, request: StarletteRequest) -> AbstractMediaSerializer:
        """Determine the best serializer based on Accept header."""
        accept_header = request.headers.get("accept", "*/*")

        # Parse Accept header into (media_type, q-value) pairs
        options = []
        for item in accept_header.split(","):
            item = item.strip()
            if not item:
                continue

            # Parse quality factor
            parts = item.split(";")
            media_type = parts[0].strip()
            q_value = 1.0

            for part in parts[1:]:
                if part.strip().startswith("q="):
                    try:
                        q_value = float(part.strip()[2:])
                    except ValueError:
                        q_value = 1.0

            options.append((media_type, q_value))

        # Sort by q-value descending
        options.sort(key=lambda x: x[1], reverse=True)

        # Find first matching serializer
        for media_type, _ in options:
            # Direct match
            if media_type in self._serializers:
                return self._serializers[media_type]

            # Wildcard match
            if media_type == "*/*":
                return self._serializers.get("application/json", JSONSerializer())

            # Type wildcard match (e.g., "text/*")
            if "/*" in media_type:
                prefix = media_type.split("/*")[0]
                for key in self._serializers:
                    if key.startswith(prefix + "/"):
                        return self._serializers[key]

        # Default to JSON
        return self._serializers.get("application/json", JSONSerializer())

    async def serialize(
        self,
        data: Any,
        request: StarletteRequest,
    ) -> StarletteResponse:
        """Serialize data based on Accept header."""
        serializer = self.negotiate(request)
        return await serializer.serialize(data, request)


# Global default negotiator instance
_default_negotiator: ContentNegotiator | None = None


def get_negotiator(context: Any | None = None) -> ContentNegotiator:
    """Get the default content negotiator."""
    from quadkit.di.resolution.context import get_resolver

    resolver = get_resolver(context)
    if resolver:
        return cast(
            "ContentNegotiator", cast("Any", resolver).resolve_sync(ContentNegotiator)
        )

    global _default_negotiator
    if _default_negotiator is None:
        _default_negotiator = ContentNegotiator()
    return _default_negotiator
