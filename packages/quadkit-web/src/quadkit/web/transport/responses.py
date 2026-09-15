"""Response handling"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterator
from pathlib import Path
from typing import Any, cast

from starlette.responses import (
    FileResponse as StarletteFileResponse,
)
from starlette.responses import (
    HTMLResponse as StarletteHTMLResponse,  # type: ignore[import]
)
from starlette.responses import (
    RedirectResponse as StarletteRedirectResponse,
)
from starlette.responses import (
    Response as StarletteResponse,
)
from starlette.responses import (
    StreamingResponse as StarletteStreamingResponse,
)

from quadkit.logging import get_logger

# JSON helper for HTMX header encoding
from quadkit.serialization import dumps, dumps_str

# Use quadkit common JSON utilities for consistent serialization across packages

logger = get_logger(__name__)


class Response(StarletteResponse):
    """Base response class"""


class FastJSONResponse(Response):
    """JSON response using quadkit common JSON utilities.

    Uses orjson when available (5-10x faster than stdlib json) with graceful
    fallback to stdlib json. Provides consistent JSON serialization across
    all Quadkit packages.

    Performance benefits:
    - 5-10x faster than stdlib json when orjson is available
    - Native datetime/UUID/dataclass support
    - Efficient bytes output
    - Consistent behavior across packages

    For Pydantic models, prefer model.model_dump_json() which uses
    Rust-based serialization (similar performance to orjson).
    """

    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        # Check if content is a Pydantic model
        if hasattr(content, "model_dump_json"):
            # Use Pydantic's efficient Rust-based serializer
            return content.model_dump_json().encode("utf-8")

        # Use quadkit common JSON utilities for everything else
        return cast("Any", dumps)(content)


class JSONResponse(FastJSONResponse):
    """JSON response with high performance.

    Uses quadkit common JSON utilities for consistent serialization
    across all Quadkit packages. Automatically uses Pydantic's Rust serializer
    for Pydantic models when available.
    """


class HTMLResponse(StarletteHTMLResponse):
    """HTML response"""


class HTMLContent(str):
    """Marker type explicitly indicating HTML content.

    Handlers that return `HTMLContent` are explicitly declaring that the
    returned string should be treated as HTML. This avoids heuristic checks
    and makes the behavior explicit for callers.
    """

    __slots__ = ()


class HTMXResponse(StarletteHTMLResponse):
    """Convenience HTML response with HTMX-specific headers support.

    Example:
        return HTMXResponse("<div>ok</div>", hx_trigger={"showToast": "Saved"})
    This will set the `HX-Trigger` header to the JSON-encoded value.
    """

    def __init__(
        self,
        content: Any,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        hx_trigger: Any = None,
        hx_refresh: bool = False,
    ) -> None:
        # Prepare headers dict
        headers = headers or {}
        # Set HX-Trigger header if provided
        if hx_trigger is not None:
            # Allow passing a str or a mapping which will be JSON-encoded
            try:
                if isinstance(hx_trigger, str):
                    headers["HX-Trigger"] = hx_trigger
                else:
                    headers["HX-Trigger"] = cast("Any", dumps_str)(hx_trigger)
            except (TypeError, ValueError) as e:
                logger.debug("Failed to JSON-encode HX-Trigger header: %s", e)
                headers["HX-Trigger"] = str(hx_trigger)

        if hx_refresh:
            headers["HX-Refresh"] = "true"

        super().__init__(content=content, status_code=status_code, headers=headers)


class FileResponse(StarletteFileResponse):
    """File response for serving static files"""


class StreamingResponse(StarletteStreamingResponse):
    """Streaming response for large files or server-sent events"""


class RedirectResponse(StarletteRedirectResponse):
    """Redirect response"""


# Convenience functions
def json_response(
    content: Any,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Create a JSON response"""
    return JSONResponse(content=content, status_code=status_code, headers=headers)


def html_response(
    content: str,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> HTMLResponse:
    """Create an HTML response"""
    return HTMLResponse(content=content, status_code=status_code, headers=headers)


def file_response(
    path: str | Path,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    media_type: str | None = None,
    filename: str | None = None,
    content_disposition_type: str = "attachment",
) -> FileResponse:
    """Create a file response"""
    return FileResponse(
        path=path,
        status_code=status_code,
        headers=headers,
        media_type=media_type,
        filename=filename,
        content_disposition_type=content_disposition_type,
    )


def streaming_response(
    content: AsyncGenerator[bytes, None] | Iterator[bytes],
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    media_type: str | None = None,
) -> StreamingResponse:
    """Create a streaming response"""
    return StreamingResponse(
        content=content,
        status_code=status_code,
        headers=headers,
        media_type=media_type,
    )


def redirect_response(
    url: str,
    status_code: int = 302,
    headers: dict[str, str] | None = None,
) -> RedirectResponse:
    """Create a redirect response"""
    return RedirectResponse(url=url, status_code=status_code, headers=headers)


__all__ = [
    "FastJSONResponse",
    "FileResponse",
    "HTMLContent",
    "HTMLResponse",
    "HTMXResponse",
    "JSONResponse",
    "RedirectResponse",
    "Response",
    "StreamingResponse",
    "file_response",
    "html_response",
    "json_response",
    "redirect_response",
    "streaming_response",
]
