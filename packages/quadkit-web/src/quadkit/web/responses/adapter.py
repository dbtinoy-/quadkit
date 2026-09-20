from __future__ import annotations

from typing import Any

from starlette.responses import HTMLResponse, JSONResponse

from quadkit.contracts.web import ResponseFactoryProtocol, ResponseProtocol


class StarletteResponseAdapter(ResponseFactoryProtocol):
    """Implementation of ResponseFactoryProtocol using Starlette responses.

    This class name uses *Adapter* instead of *Factory* to comply with
    naming guidelines that prohibit "factory" and "facade".
    """

    def json(
        self,
        content: Any,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> ResponseProtocol:
        """Create a JSON response."""
        return JSONResponse(  # type: ignore[return-value]
            content=content,
            status_code=status_code,
            headers=headers,
        )

    def html(
        self,
        content: str,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> ResponseProtocol:
        """Create an HTML response."""
        return HTMLResponse(  # type: ignore[return-value]
            content=content,
            status_code=status_code,
            headers=headers,
        )

    def redirect(
        self,
        url: str,
        status_code: int = 302,
        headers: dict[str, str] | None = None,
    ) -> ResponseProtocol:
        """Create a redirect response."""
        from starlette.responses import RedirectResponse

        return RedirectResponse(  # type: ignore[return-value]
            url=url,
            status_code=status_code,
            headers=headers,
        )
