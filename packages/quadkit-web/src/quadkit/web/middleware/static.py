"""Static file serving middleware."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import mimetypes
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, Response
from starlette.types import ASGIApp


class StaticFilesMiddleware(BaseHTTPMiddleware):
    """Middleware for serving static files"""

    def __init__(
        self,
        app: ASGIApp,
        directory: str = "static",
        prefix: str = "/static",
        html: bool = False,
        check_dir: bool = True,
        cache_max_age: int = 31536000,
    ) -> None:
        super().__init__(app)
        self.directory = Path(directory)
        self.prefix = prefix.rstrip("/")
        self.html = html
        self.cache_max_age = cache_max_age

        if check_dir and not self.directory.exists():
            raise RuntimeError(f"Static files directory '{directory}' does not exist")

        if check_dir and not self.directory.is_dir():
            raise RuntimeError(f"Static files path '{directory}' is not a directory")

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Serve static files if path matches prefix"""
        if not request.url.path.startswith(self.prefix + "/"):
            return await call_next(request)

        # Extract file path from URL
        path = request.url.path[len(self.prefix) + 1 :]

        # Prevent directory traversal
        if ".." in path or path.startswith("/"):
            return Response("Forbidden", status_code=403)

        # Build full file path
        file_path = self.directory / path

        # Check if file exists
        if not file_path.exists() or not file_path.is_file():
            if (self.html and path == "") or path.endswith("/"):
                # Try index.html for directory requests
                index_path = (
                    file_path / "index.html"
                    if file_path.is_dir()
                    else file_path.with_suffix(".html")
                )
                if index_path.exists() and index_path.is_file():
                    file_path = index_path
                else:
                    return await call_next(request)
            else:
                return await call_next(request)

        # Determine content type
        content_type, _ = mimetypes.guess_type(str(file_path))
        if content_type is None:
            content_type = "application/octet-stream"

        # Return file response
        return FileResponse(
            path=file_path,
            media_type=content_type,
            headers={"Cache-Control": f"public, max-age={self.cache_max_age}"},
        )


# Re-export StaticFileProvider from static package
from quadkit.web.static import StaticFileProvider

__all__ = ["StaticFileProvider", "StaticFilesMiddleware"]
