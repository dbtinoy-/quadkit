"""Framework-owned HTTP response model.

Decouples consumers from ``aiohttp`` (or any other HTTP library) by providing
a transport-agnostic response object.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class HttpResponse:
    """Framework-owned representation of an HTTP response.

    Wraps the raw response produced by the underlying HTTP library (e.g.
    ``aiohttp``) so that consumers never need to import transport-level
    objects.

    Attributes:
        status: HTTP status code (e.g. 200, 404).
        headers: Response headers as a plain ``dict[str, str]``.
        body: Raw response body bytes.
        text: Response body decoded as UTF-8 text; empty string when absent.
        json: Parsed JSON payload; ``None`` when the response is not JSON.
        url: Final (possibly redirected) URL as a string.
        method: HTTP method of the originating request (upper-cased).
        content_length: Parsed ``Content-Length`` response header value, or
            ``None`` when absent or non-numeric.
    """

    status: int
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    text: str = ""
    json: Any = None
    url: str = ""
    method: str = ""
    content_length: int | None = None

    def raise_for_status(self) -> None:
        """Raise :class:`HttpStatusError` when the status code indicates failure.

        Raises:
            HttpStatusError: For any 4xx or 5xx status code.
        """
        if self.status >= 400:
            raise HttpStatusError(
                f"HTTP {self.status} for {self.method} {self.url}",
                status=self.status,
                response=self,
            )

    @property
    def Ok(self) -> bool:
        """``True`` when the status code is below 400."""
        return self.status < 400


from quadkit.contracts.exceptions.infra import InfrastructureError


class HttpStatusError(InfrastructureError):
    """Raised by :meth:`HttpResponse.raise_for_status` for 4xx/5xx responses.

    Attributes:
        status: HTTP status code that triggered this error.
        response: The originating :class:`HttpResponse` instance.
    """

    _code: str = "QK_ERR_WEB_002"

    def __init__(
        self,
        message: str,
        *,
        status: int,
        response: HttpResponse,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            message=message,
            code=f"HTTP_{status}",
            details={"status": status, "url": response.url, "method": response.method},
            **kwargs,
        )
        self.status = status
        self.response = response


__all__ = ["HttpResponse", "HttpStatusError"]
