"""Shared, documentation-only HTTP bearer declaration for guarded handlers.

Auth producers and Web consumers communicate through this value, never by
importing one another or guessing policy from guard names. This declaration
does not authenticate requests, install middleware or authorize a handler.
"""

from __future__ import annotations

from dataclasses import dataclass

HTTP_BEARER_DOCUMENTATION_ATTRIBUTE = "__quadkit_http_bearer_documentation__"


@dataclass(frozen=True, slots=True)
class HttpErrorMessageDocumentation:
    """Declare one JSON ``error``/``message`` rejection envelope.

    This is a producer-owned wire claim, not an error mapper or policy.
    ``error`` is the literal error discriminator; ``message`` is a string.
    Other bodies/media types must use explicit operation response metadata.
    Primitive fields keep nested bearer declarations deeply immutable.
    """

    status_code: int
    error: str
    description: str = "Guard rejected the request."


@dataclass(frozen=True, slots=True)
class HttpBearerDocumentation:
    """Declare a supported bearer credential and its OpenAPI scheme name.

    The default matches the generated application's static bearer requirement.
    Other credential schemes and role/permission policy are not implied.
    """

    scheme_name: str = "bearerAuth"
    rejections: tuple[HttpErrorMessageDocumentation, ...] = ()


__all__ = [
    "HTTP_BEARER_DOCUMENTATION_ATTRIBUTE",
    "HttpBearerDocumentation",
    "HttpErrorMessageDocumentation",
]
