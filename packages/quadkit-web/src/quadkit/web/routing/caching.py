"""HTTP caching response decorators.

Provides declarative decorators for setting HTTP cache-control semantics
and ETag-based conditional request handling.

Usage::

    from quadkit.web.routing.caching import cache_control, etag

    class ArticleController(Controller):

        @get("/{id}")
        @cache_control(max_age=3600, public=True)
        async def get_article(self, id: str) -> ArticleResponse:
            ...

        @get("/{id}/preview")
        @etag
        async def get_preview(self, id: str) -> ArticleResponse:
            # Framework auto-generates ETag from response body and
            # returns 304 Not Modified if If-None-Match matches.
            ...
"""

from __future__ import annotations

from collections.abc import Callable
import hashlib
from typing import Any, TypeVar

from starlette.requests import Request

# boundary-catch: handlers may hand back a raw starlette response; quadkit's
# family subclasses it, so this isinstance accepts both shapes.
from starlette.responses import Response

from quadkit.logging import get_logger
from quadkit.web.transport.responses import Response as QuadkitResponse

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# Sentinel attribute written by decorators so ResponseSerializer can inspect
_CACHE_CONTROL_ATTR = "__http_cache_control__"
_ETAG_ATTR = "__http_etag__"


# ---------------------------------------------------------------------------
# @cache_control
# ---------------------------------------------------------------------------


def cache_control(
    *,
    max_age: int | None = None,
    s_maxage: int | None = None,
    public: bool = False,
    private: bool = False,
    no_cache: bool = False,
    no_store: bool = False,
    must_revalidate: bool = False,
    immutable: bool = False,
    stale_while_revalidate: int | None = None,
) -> Callable[[F], F]:
    """Declaratively set ``Cache-Control`` headers on a controller handler.

    The generated ``Cache-Control`` value is written to the response by the
    ``RequestPipeline`` after handler execution.  When applied, it wraps
    the handler and patches whatever ``Response`` is returned.

    Args:
        max_age: ``max-age`` in seconds.
        s_maxage: ``s-maxage`` in seconds (shared/CDN caches).
        public: Mark the response as publicly cacheable.
        private: Mark the response as private (per-user).
        no_cache: Force revalidation before serving from cache.
        no_store: Disallow any caching whatsoever.
        must_revalidate: Require revalidation when stale.
        immutable: Hint that the response will never change.
        stale_while_revalidate: Seconds to serve stale while revalidating.

    Example::

        @get("/articles")
        @cache_control(max_age=60, public=True)
        async def list_articles(self) -> list[ArticleDTO]:
            ...
    """
    directives: list[str] = []
    if public:
        directives.append("public")
    if private:
        directives.append("private")
    if no_store:
        directives.append("no-store")
    if no_cache:
        directives.append("no-cache")
    if must_revalidate:
        directives.append("must-revalidate")
    if immutable:
        directives.append("immutable")
    if max_age is not None:
        directives.append(f"max-age={max_age}")
    if s_maxage is not None:
        directives.append(f"s-maxage={s_maxage}")
    if stale_while_revalidate is not None:
        directives.append(f"stale-while-revalidate={stale_while_revalidate}")

    header_value = ", ".join(directives) if directives else "no-cache"

    def decorator(fn: F) -> F:
        import functools

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await fn(*args, **kwargs)
            if isinstance(result, Response):
                result.headers["Cache-Control"] = header_value
            return result

        wrapper.__http_cache_control__ = header_value  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator


# ---------------------------------------------------------------------------
# @etag
# ---------------------------------------------------------------------------


def etag(fn: F) -> F:
    """Auto-generate and validate ETag headers for a controller handler.

    When applied, the response body is hashed (MD5) to produce a weak ETag.
    If the client sends ``If-None-Match`` and it matches the computed ETag,
    the response is replaced with a ``304 Not Modified`` with no body.

    Supports both strong and weak ETags (weak is the default).

    Args:
        fn: The (async) handler method to decorate.

    Example::

        @get("/{id}")
        @etag
        async def get_article(self, id: str) -> ArticleResponse:
            ...
    """
    import functools

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = await fn(*args, **kwargs)

        # Only decorate Response objects — if the handler returned raw data
        # it will be serialized later; skip ETag injection here
        if not isinstance(result, Response):
            return result

        # Generate weak ETag from response body
        body: bytes | bytearray = bytes(result.body) if hasattr(result, "body") else b""
        etag_value = f'W/"{hashlib.md5(body, usedforsecurity=False).hexdigest()}"'

        result.headers["ETag"] = etag_value

        # Check If-None-Match — requires request in scope
        # Starlette injects `request` as the first positional argument when
        # the handler is a controller method.  We inspect args to locate it.
        request = _find_request(args, kwargs)
        if request is not None:
            client_etag = request.headers.get("If-None-Match", "")
            if client_etag and _etag_matches(client_etag, etag_value):
                return QuadkitResponse(status_code=304, headers={"ETag": etag_value})

        return result

    wrapper.__http_etag__ = True  # type: ignore[attr-defined]
    return wrapper  # type: ignore[return-value]


def _find_request(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Request | None:
    """Locate the Starlette Request object inside handler arguments."""
    for arg in args:
        if isinstance(arg, Request):
            return arg
    for val in kwargs.values():
        if isinstance(val, Request):
            return val
    return None


def _etag_matches(client_header: str, server_etag: str) -> bool:
    """Return True if the client's If-None-Match header matches the server ETag.

    Handles ``*`` (match-all) and comma-separated lists of tags.
    """
    if client_header.strip() == "*":
        return True
    client_tags = {tag.strip() for tag in client_header.split(",")}
    # Compare both weak and strong form
    bare = server_etag.strip('"').lstrip("W/").strip('"')
    for tag in client_tags:
        tag_bare = tag.strip('"').lstrip("W/").strip('"')
        if tag_bare == bare:
            return True
    return False


__all__ = ["cache_control", "etag"]
