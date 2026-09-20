"""Content negotiation and response serialization.

This package provides content negotiation based on the Accept header
and response serializers for different media types.
"""

from __future__ import annotations

from quadkit.web.serialization.negotiator import ContentNegotiator
from quadkit.web.serialization.serializers import (
    HTMLSerializer,
    JSONSerializer,
    PlainTextSerializer,
    ResponseSerializer,
    XMLSerializer,
)

__all__ = [
    "ContentNegotiator",
    "HTMLSerializer",
    "JSONSerializer",
    "PlainTextSerializer",
    "ResponseSerializer",
    "XMLSerializer",
]
