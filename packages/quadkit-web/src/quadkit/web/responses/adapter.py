from __future__ import annotations

from typing import Any

from quadkit.contracts.web import ResponseFactoryProtocol, ResponseProtocol
from quadkit.web.transport.responses import FastJSONResponse, HTMLResponse


class StarletteResponseAdapter(ResponseFactoryProtocol):
    """Implementation of ResponseFactoryProtocol using quadkit responses.

    The returned objects are the framework's own response family
    (:class:`FastJSONResponse`/:class:`HTMLResponse` — starlette subclasses),
    so JSON payloads serialize through ``quadkit.serialization`` (orjson
    when installed, native datetime/UUID/dataclass support). The class
    name keeps *Adapter* instead of *Factory* to comply with naming
    guidelines that prohibit "factory" and "facade".
    """

    def json(
        self,
        content: Any,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> ResponseProtocol:
        """Create a JSON response (datetime/UUID payloads serialize natively)."""
        return FastJSONResponse(  # type: ignore[return-value]
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
        from quadkit.web.transport.responses import RedirectResponse

        return RedirectResponse(  # type: ignore[return-value]
            url=url,
            status_code=status_code,
            headers=headers,
        )
