"""
API Versioning Support for Quadkit Web.

Supports multiple versioning strategies:
- URI versioning: /v1/users
- Header versioning: X-API-Version: 1
- Media type versioning: Accept: application/vnd.api.v1+json
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request

    from quadkit.web.transport.responses import Response


class VersioningStrategy(StrEnum):
    """API versioning strategy."""

    HEADER = "header"
    URI = "uri"
    MEDIA_TYPE = "media_type"
    QUERY = "query"


@dataclass
class VersioningConfig:
    """Configuration for API versioning."""

    strategy: VersioningStrategy = VersioningStrategy.URI
    default_version: str = "1"
    header_name: str = "X-API-Version"
    uri_prefix: str = "v"
    media_type_prefix: str = "vnd.api"
    query_param: str = "api_version"


class VersionExtractor:
    """Extracts version from requests based on strategy."""

    def __init__(self, config: VersioningConfig):
        self.config = config

    def extract(self, request: Request) -> str:
        """Extract version from request."""
        if self.config.strategy == VersioningStrategy.HEADER:
            return self._extract_from_header(request)
        if self.config.strategy == VersioningStrategy.URI:
            return self._extract_from_uri(request)
        if self.config.strategy == VersioningStrategy.MEDIA_TYPE:
            return self._extract_from_media_type(request)
        # QUERY or any future strategy
        return self._extract_from_query(request)

    def _extract_from_header(self, request: Request) -> str:
        """Extract version from header."""
        version = request.headers.get(self.config.header_name)
        return version if version else self.config.default_version

    def _extract_from_uri(self, request: Request) -> str:
        """Extract version from URI path."""
        path = request.url.path
        parts = path.strip("/").split("/")

        for part in parts:
            if part.startswith(self.config.uri_prefix):
                return part[len(self.config.uri_prefix) :]

        return self.config.default_version

    def _extract_from_media_type(self, request: Request) -> str:
        """Extract version from Accept header media type."""
        accept = request.headers.get("Accept", "")

        # Parse media types like application/vnd.api.v1+json and
        # application/vnd.api.v1.json alike: the version segment may carry a
        # structured-syntax suffix, which is not part of the version.
        if self.config.media_type_prefix in accept:
            parts = accept.split(".")
            for part in parts:
                version_token = part[1:].split("+")[0] if part.startswith("v") else ""
                if version_token.isdigit():
                    return version_token

        return self.config.default_version

    def _extract_from_query(self, request: Request) -> str:
        """Extract version from query parameter."""
        version = request.query_params.get(self.config.query_param)
        return version if version else self.config.default_version


def version(api_version: str) -> Callable[[Any], Any]:
    """
    Decorator to specify controller or method version.

    Usage::

        @version("1")
        class UsersController(Controller):
            ...

        @version("2")
        class UsersV2Controller(Controller):
            ...
    """

    def decorator(target: Any) -> Any:
        # Store version metadata
        target.__api_version__ = api_version
        return target

    return decorator


class VersioningMiddleware:
    """Extraction-only version middleware.

    Reads the negotiated version (header/query/URI/media-type per config)
    and stamps ``request.state.api_version`` for handlers and diagnostics.
    Route selection is the router's job (mount per-version controllers with
    :func:`api_version`); this middleware deliberately performs no
    negotiation or rewriting.
    """

    def __init__(self, config: VersioningConfig):
        self.config = config
        self.extractor = VersionExtractor(config)

    async def __call__(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process request and extract version."""
        # Extract version and store in request state
        version = self.extractor.extract(request)
        request.state.api_version = version

        # Continue processing
        return await call_next(request)


def get_version(request: Request) -> str:
    """
    Get API version from request state.

    Args:
        request: The HTTP request

    Returns:
        API version string
    """
    return getattr(request.state, "api_version", "1")


# ---------------------------------------------------------------------------
# @api_version — richer version decorator with URI prefix + deprecation
# ---------------------------------------------------------------------------


@dataclass
class ApiVersionMetadata:
    """Metadata attached to a versioned controller or handler by ``@api_version``."""

    version: int | str
    """Version number/string (e.g. ``1``, ``2``, ``"2.1"``)."""
    deprecated: bool = False
    """When ``True``, add ``Deprecation: true`` and ``Sunset`` response headers."""
    sunset: str | None = None
    """ISO-8601 date after which the version will be removed (e.g. ``"2025-12-31"``)."""
    prefix: str | None = None
    """Explicit URL prefix override (e.g. ``"/api/v1"``). When *None*, the prefix
    is derived automatically from the version number as ``"/v{version}"``."""
    _extra: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def url_prefix(self) -> str:
        """Return the URL prefix for this version."""
        if self.prefix is not None:
            return self.prefix
        return f"/v{self.version}"


def api_version(
    ver: int | str,
    *,
    deprecated: bool = False,
    sunset: str | None = None,
    prefix: str | None = None,
) -> Callable[[Any], Any]:
    """Mark a controller (or individual handler) with an API version.

    This extends the simpler :func:`version` decorator with:

    * **URL prefix** — the version number is automatically prepended to the
      controller's ``prefix`` attribute (e.g. ``prefix = "/users"`` becomes
      ``"/v1/users"``).  Override with the *prefix* argument.
    * **Deprecation support** — setting ``deprecated=True`` causes the
      routing layer to inject ``Deprecation: true`` and optionally
      ``Sunset: <date>`` response headers for all routes on the controller.
    * **Metadata storage** — an :class:`ApiVersionMetadata` instance is
      stored on the class/function as ``__api_version_meta__`` and the plain
      version string as ``__api_version__`` (compatible with
      :class:`VersioningMiddleware`).

    Args:
        ver: Version number or string (e.g. ``1``, ``"2"``, ``"2.1"``).
        deprecated: When ``True``, mark this version as deprecated.
        sunset: Optional ISO-8601 date string indicating when support ends.
        prefix: Explicit URL prefix to use instead of the auto-derived one.

    Returns:
        Class/function decorator.

    Example::

        @api_version(1)
        class UserControllerV1(Controller):
            prefix = "/users"   # mounted at /v1/users

        @api_version(2)
        class UserControllerV2(Controller):
            prefix = "/users"   # mounted at /v2/users

        @api_version(1, deprecated=True, sunset="2025-12-31")
        class LegacyController(Controller):
            prefix = "/legacy"  # adds Deprecation + Sunset headers
    """
    meta = ApiVersionMetadata(
        version=ver,
        deprecated=deprecated,
        sunset=sunset,
        prefix=prefix,
    )

    def decorator(target: Any) -> Any:
        # Store rich metadata
        target.__api_version_meta__ = meta
        # Keep backward-compat plain string for VersioningMiddleware
        target.__api_version__ = str(ver)

        # If this is a class (controller), automatically prepend the version
        # prefix to the controller's `prefix` attribute.
        if isinstance(target, type):
            existing_prefix: str = getattr(target, "prefix", "") or ""
            # Avoid double-prefixing if the prefix already starts with "/vN"
            version_prefix = meta.url_prefix
            if not existing_prefix.startswith(version_prefix):
                target.prefix = version_prefix + existing_prefix  # type: ignore[attr-defined]

        return target

    return decorator


__all__ = [
    "ApiVersionMetadata",
    "VersionExtractor",
    "VersioningConfig",
    "VersioningMiddleware",
    "VersioningStrategy",
    "api_version",
    "get_version",
    "version",
]


def with_deprecation_headers(
    endpoint: Callable[..., Any], meta: ApiVersionMetadata
) -> Callable[..., Any]:
    """Wrap an endpoint so deprecated versions advertise themselves.

    Used by the routing layer when a controller (or individual handler)
    carries an :class:`ApiVersionMetadata` with ``deprecated=True`` — the
    response gains ``Deprecation: true`` and, when set,
    ``Sunset: <date>`` headers (RFC 8594 / draft-polli-ratelimit-headers
    conventions).
    """
    from functools import wraps

    @wraps(endpoint)
    async def wrapper(request: Any) -> Any:
        response = await endpoint(request)
        response.headers["Deprecation"] = "true"
        if meta.sunset:
            response.headers["Sunset"] = meta.sunset
        return response

    return wrapper
