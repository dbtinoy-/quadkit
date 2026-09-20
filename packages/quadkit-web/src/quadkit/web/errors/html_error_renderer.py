"""Debug HTML error page renderer for Quadkit Web.

Generates rich, browser-friendly error pages in debug mode.
Only activated when ``debug=True`` **and** the request prefers HTML
(``Accept: text/html``).  In production (``debug=False``) all error
responses remain JSON regardless of the ``Accept`` header.

Usage::

    renderer = DebugHtmlErrorRenderer()
    html_response = renderer.render(exc, request, status_code=500)
"""

from __future__ import annotations

import html
import linecache
import sys
import traceback
from typing import TYPE_CHECKING, Any

from quadkit.web.errors.html_page_templates import (
    _h,
    _render_debug_page,
    _render_frames,
    _render_kv,
)

if TYPE_CHECKING:
    from starlette.responses import HTMLResponse

_STATUS_LABELS: dict[int, str] = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    408: "Request Timeout",
    409: "Conflict",
    410: "Gone",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    500: "Internal Server Error",
    501: "Not Implemented",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
}

# Number of source lines to display around the error frame
_CONTEXT_LINES = 7

# Headers whose values should be redacted in the debug page
_SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "cookie",
        "x-api-key",
        "x-auth-token",
        "proxy-authorization",
    }
)


def _accepts_html(request: Any) -> bool:
    """Return True if the HTTP client prefers an HTML response.

    Browsers send ``Accept: text/html,...`` while REST clients typically send
    ``Accept: application/json`` or omit the header entirely.  We render HTML
    only when ``text/html`` appears in the ``Accept`` header **and** has a
    higher weight (q-value) than ``application/json``.  When no ``Accept``
    header is present we assume a non-browser client and return JSON.
    """
    accept = ""
    try:
        accept = request.headers.get("accept", "") or request.headers.get("Accept", "")
    except Exception:  # noqa: BLE001
        return False

    if not accept or (
        "text/html" not in accept and "text/*" not in accept and "*/*" not in accept
    ):
        return False

    # Parse q-values for text/html and application/json
    html_q = 0.0
    json_q = 0.0
    for part in accept.split(","):
        part = part.strip()
        mime, *params = part.split(";")
        mime = mime.strip().lower()
        q = 1.0
        for p in params:
            p = p.strip()
            if p.startswith("q="):
                try:
                    q = float(p[2:])
                except ValueError:
                    pass
        if mime in ("text/html", "text/*", "*/*"):
            html_q = max(html_q, q)
        elif mime in ("application/json", "application/*"):
            json_q = max(json_q, q)

    return html_q >= json_q and html_q > 0.0


def _extract_frames(exc: BaseException) -> list[dict[str, Any]]:
    """Extract traceback frames with surrounding source context.

    Returns a list of dicts, each containing:
    - ``filename``: absolute path
    - ``lineno``: error line number (1-based)
    - ``name``: function/method name
    - ``lines``: list of ``(line_number, code, is_error_line)`` tuples
    """
    tb = exc.__traceback__
    if tb is None:
        return []

    frames = []
    for frame_summary in traceback.extract_tb(tb):
        filename = frame_summary.filename or "<unknown>"
        lineno = frame_summary.lineno or 0
        func_name = frame_summary.name or "<unknown>"

        # Load surrounding lines
        start = max(1, lineno - _CONTEXT_LINES // 2)
        end = lineno + _CONTEXT_LINES // 2 + 1
        source_lines = []
        for ln in range(start, end):
            code = linecache.getline(filename, ln)
            if code:
                source_lines.append((ln, code.rstrip("\n"), ln == lineno))

        frames.append(
            {
                "filename": filename,
                "lineno": lineno,
                "name": func_name,
                "lines": source_lines,
            }
        )

    return frames


def _redact_headers(request: Any) -> list[tuple[str, str]]:
    """Return request headers with sensitive values replaced by ``[REDACTED]``."""
    rows: list[tuple[str, str]] = []
    try:
        for key, value in request.headers.items():
            display = "[REDACTED]" if key.lower() in _SENSITIVE_HEADERS else value
            rows.append((key, display))
    except Exception:  # noqa: BLE001, S110
        pass
    return rows


class DebugHtmlErrorRenderer:
    """Renders a developer-friendly HTML error page for use in debug mode.

    The page includes:
    - HTTP status code and error type
    - Full Python traceback with highlighted source context
    - Annotated request details (method, path, headers — sensitive values redacted)
    - Python / framework version footer

    This class produces no output when ``debug=False``; it is designed to be
    composed into ``DefaultExceptionFilter`` and ``FilterPipeline``.
    """

    def should_render(self, request: Any) -> bool:
        """Return True when the client prefers an HTML response.

        Args:
            request: The incoming HTTP request.

        Returns:
            True when ``Accept`` header prefers HTML over JSON.
        """
        return _accepts_html(request)

    def render(
        self,
        exc: BaseException,
        request: Any,
        status_code: int = 500,
        title: str | None = None,
    ) -> HTMLResponse:
        """Build and return a rich HTML error response.

        Args:
            exc: The exception that was raised.
            request: The incoming HTTP request.
            status_code: HTTP status code to return.
            title: Optional override for the error headline.

        Returns:
            An ``HTMLResponse`` with full debug information.
        """
        from starlette.responses import HTMLResponse

        status_label = _STATUS_LABELS.get(status_code, "Error")
        exc_type = type(exc).__name__
        exc_msg = html.escape(str(exc)) if str(exc) else "(no message)"
        headline = title or f"{status_code} {status_label}"

        frames = _extract_frames(exc)
        traceback_html = _render_frames(frames)

        # Chain of causes
        chain_causes: list[BaseException] = []
        cause: BaseException | None = exc.__cause__ or exc.__context__
        while cause is not None:
            chain_causes.append(cause)
            cause = cause.__cause__ or cause.__context__

        if chain_causes:
            chain_items_html = "".join(
                _h(
                    "li",
                    f"<code>{html.escape(type(c).__name__)}</code>:"
                    f" {html.escape(str(c))}",
                )
                for c in chain_causes
            )
            chain_html = _h(
                "ul",
                chain_items_html,
                style="margin:.5rem 0 0 1rem;font-size:.85rem;color:#f0a500;",
            )
        else:
            chain_html = ""

        try:
            method = request.method
            path = str(request.url)
        except Exception:  # noqa: BLE001
            method, path = "?", "?"

        headers = _redact_headers(request)
        request_html = _render_kv([("Method", method), ("URL", path), *headers])

        try:
            qp = list(request.query_params.items())
            query_html = (
                _render_kv(qp)
                if qp
                else _h("p", "None", style="color:#64748b;font-size:.9rem;")
            )
        except Exception:  # noqa: BLE001
            query_html = _h("p", "N/A", style="color:#64748b;font-size:.9rem;")

        python_ver = sys.version.split()[0]
        try:
            import quadkit as _lx

            lx_ver = getattr(_lx, "__version__", "?")
        except Exception:  # noqa: BLE001
            lx_ver = "?"

        content = _render_debug_page(
            headline=headline,
            exc_type=exc_type,
            exc_msg=exc_msg,
            chain_html=chain_html,
            traceback_html=traceback_html,
            request_html=request_html,
            query_html=query_html,
            python_ver=python_ver,
            lx_ver=lx_ver,
        )
        return HTMLResponse(content=content, status_code=status_code)


__all__ = ["DebugHtmlErrorRenderer"]
