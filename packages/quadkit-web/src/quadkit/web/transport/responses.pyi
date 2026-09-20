from typing import Any

from starlette.responses import Response as StarletteResponse

class Response(StarletteResponse): ...

class JSONResponse(Response):
    def __init__(
        self,
        content: Any = ...,
        status_code: int = ...,
        headers: dict[str, str] | None = ...,
        media_type: str | None = ...,
        background: Any | None = ...,
    ) -> None: ...

class RedirectResponse(Response): ...
class HTMLResponse(Response): ...
class HTMLContent(str): ...

def json_response(
    content: Any,
    status_code: int = ...,
    headers: dict[str, str] | None = ...,
) -> JSONResponse: ...
def redirect_response(
    url: str,
    status_code: int = ...,
    headers: dict[str, str] | None = ...,
) -> RedirectResponse: ...

__all__ = [
    "HTMLContent",
    "HTMLResponse",
    "JSONResponse",
    "RedirectResponse",
    "Response",
    "json_response",
    "redirect_response",
]
