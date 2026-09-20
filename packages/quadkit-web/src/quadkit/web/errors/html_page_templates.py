"""HTML template builders for the debug error page.

Pure-Python markup construction helpers — no external template engine
required.  Consumed by :mod:`quadkit.web.errors.html_error_renderer`.
"""

from __future__ import annotations

import html
from typing import Any


def _h(tag: str, *children: str | dict[str, Any] | None, **attrs: Any) -> str:
    """Minimal HTML element builder — no external dependencies required.

    String children are concatenated as-is (caller is responsible for escaping).
    Dict children contribute attribute key/value pairs.
    Keyword args become attributes; trailing underscore stripped, remaining underscores
    converted to hyphens (e.g. ``class_`` → ``class``, ``x_data`` → ``x-data``).
    """
    attr_parts: list[str] = []
    text_parts: list[str] = []
    for child in children:
        if child is None:
            continue
        if isinstance(child, dict):
            for k, v in child.items():
                if v is False or v is None:
                    continue
                if v is True:
                    attr_parts.append(f" {k}")
                else:
                    attr_parts.append(f' {k}="{html.escape(str(v))}"')
        else:
            text_parts.append(child)
    for key, val in attrs.items():
        if val is None or val is False:
            continue
        name = key.rstrip("_").replace("_", "-")
        if val is True:
            attr_parts.append(f" {name}")
        else:
            attr_parts.append(f' {name}="{html.escape(str(val))}"')
    return f"<{tag}{''.join(attr_parts)}>{''.join(text_parts)}</{tag}>"


# ---------------------------------------------------------------------------
# HTML template helpers (pure Python — no external template engine required)
# ---------------------------------------------------------------------------

_CSS = """
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                     "Helvetica Neue", Arial, sans-serif;
        background: #0f1117;
        color: #e8eaf0;
        line-height: 1.6;
        min-height: 100vh;
    }
    .header {
        background: linear-gradient(135deg, #c0392b 0%, #922b21 100%);
        padding: 2rem 2.5rem;
        border-bottom: 3px solid #a93226;
    }
    .header h1 { font-size: 1rem; opacity: .7; font-weight: 400; margin-bottom: .4rem; letter-spacing: .05em; text-transform: uppercase; }
    .header h2 { font-size: 2rem; font-weight: 700; margin-bottom: .5rem; }
    .header .exc-type {
        display: inline-block;
        background: rgba(0,0,0,.3);
        padding: .2rem .7rem;
        border-radius: 4px;
        font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
        font-size: .9rem;
    }
    .main { max-width: 1100px; margin: 0 auto; padding: 2rem 2.5rem; }
    .section { margin-bottom: 2.5rem; }
    .section-title {
        font-size: .7rem;
        text-transform: uppercase;
        letter-spacing: .12em;
        color: #8b9dc3;
        margin-bottom: 1rem;
        padding-bottom: .4rem;
        border-bottom: 1px solid #1e2433;
    }
    /* Traceback */
    .frame {
        background: #161b27;
        border: 1px solid #252d40;
        border-radius: 6px;
        margin-bottom: 1rem;
        overflow: hidden;
    }
    .frame-header {
        background: #1a2035;
        padding: .6rem 1rem;
        font-family: monospace;
        font-size: .85rem;
        color: #8b9dc3;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .frame-header .fn-name { color: #7ec8e3; font-weight: 600; }
    .frame-header .file-path { color: #64748b; font-size: .78rem; }
    .code-block { overflow-x: auto; }
    .code-block table { width: 100%; border-collapse: collapse; }
    .code-block td { padding: .15rem 0; white-space: pre; font-family: monospace; font-size: .85rem; }
    .code-block .ln { color: #4a5568; padding-right: 1rem; padding-left: .8rem; user-select: none; text-align: right; min-width: 3.5rem; border-right: 2px solid #1e2433; }
    .code-block .src { padding-left: .8rem; color: #c0cfe0; }
    .code-block tr.error-line { background: rgba(231, 76, 60, .15); }
    .code-block tr.error-line .ln { border-right-color: #e74c3c; color: #e74c3c; }
    .code-block tr.error-line .src { color: #fff; }
    .frame.top-frame { border-color: #e74c3c; }
    /* Request info */
    .kv-table { width: 100%; border-collapse: collapse; font-size: .88rem; }
    .kv-table td { padding: .5rem .8rem; border-bottom: 1px solid #1e2433; vertical-align: top; }
    .kv-table td:first-child { color: #8b9dc3; font-family: monospace; width: 30%; font-size: .82rem; }
    .kv-table td:last-child { font-family: monospace; word-break: break-all; }
    .kv-table tr:last-child td { border-bottom: none; }
    .badge {
        display: inline-block;
        padding: .15rem .5rem;
        border-radius: 3px;
        font-size: .78rem;
        font-weight: 600;
        font-family: monospace;
    }
    .badge-get    { background: #1a4a2e; color: #6fcf97; }
    .badge-post   { background: #1a2f4a; color: #56bcf9; }
    .badge-put    { background: #3a2f1a; color: #f2994a; }
    .badge-patch  { background: #2a1e3a; color: #bb6bd9; }
    .badge-delete { background: #3a1a1a; color: #eb5757; }
    .badge-other  { background: #1e2433; color: #8b9dc3; }
    .footer {
        margin-top: 3rem;
        padding: 1.2rem 2.5rem;
        border-top: 1px solid #1e2433;
        font-size: .75rem;
        color: #4a5568;
        display: flex;
        justify-content: space-between;
    }
"""


def _method_badge(method: str) -> str:
    """Render an HTTP method badge as an HTML string."""
    css_class = {
        "GET": "badge-get",
        "POST": "badge-post",
        "PUT": "badge-put",
        "PATCH": "badge-patch",
        "DELETE": "badge-delete",
    }.get(method.upper(), "badge-other")
    return f'<span class="badge {css_class}">{html.escape(method.upper())}</span>'


def _render_frames(frames: list[dict[str, Any]]) -> str:
    """Render traceback frames as structured HTML elements."""
    if not frames:
        return _h(
            "p", "No traceback available.", style="color:#64748b;font-size:.9rem;"
        )

    parts: list[str] = []
    for i, frame in enumerate(frames):
        is_top = i == len(frames) - 1
        fn_escaped = html.escape(frame["name"])
        fp_escaped = html.escape(frame["filename"])
        ln = frame["lineno"]

        rows_html = "".join(
            _h(
                "tr",
                _h("td", str(line_no), class_="ln"),
                _h("td", html.escape(code), class_="src"),
                class_="error-line" if is_err else None,
            )
            for line_no, code, is_err in frame["lines"]
        )
        frame_html = _h(
            "div",
            _h(
                "div",
                _h("span", f'<span class="fn-name">{fn_escaped}</span>'),
                _h("span", f"{fp_escaped}:{ln}", class_="file-path"),
                class_="frame-header",
            ),
            _h(
                "div",
                _h("table", rows_html),
                class_="code-block",
            ),
            class_="frame top-frame" if is_top else "frame",
        )
        parts.append(frame_html)
    return "\n".join(parts)


def _render_kv(pairs: list[tuple[str, str]]) -> str:
    """Render key-value pairs as a structured HTML table."""
    if not pairs:
        return _h("p", "None", style="color:#64748b;font-size:.9rem;")
    rows_html = "".join(
        _h(
            "tr",
            _h("td", html.escape(str(k))),
            _h("td", html.escape(str(v))),
        )
        for k, v in pairs
    )
    return _h("table", rows_html, class_="kv-table")


def _render_debug_page(
    *,
    headline: str,
    exc_type: str,
    exc_msg: str,
    chain_html: str,
    traceback_html: str,
    request_html: str,
    query_html: str,
    python_ver: str,
    lx_ver: str,
) -> str:
    """Render the full debug error HTML page as a plain string."""
    header = _h(
        "div",
        _h("h1", "Quadkit — Debug Mode"),
        _h("h2", html.escape(headline)),
        _h("span", f"{html.escape(exc_type)}: {exc_msg}", class_="exc-type"),
        chain_html,
        class_="header",
    )
    main_content = _h(
        "div",
        _h(
            "div",
            _h("div", "Traceback (most recent call last)", class_="section-title"),
            traceback_html,
            class_="section",
        ),
        _h(
            "div",
            _h("div", "Request", class_="section-title"),
            request_html,
            class_="section",
        ),
        _h(
            "div",
            _h("div", "Query Parameters", class_="section-title"),
            query_html,
            class_="section",
        ),
        class_="main",
    )
    footer = _h(
        "div",
        _h(
            "span",
            f"Python {html.escape(python_ver)}"
            f" &nbsp;·&nbsp; Quadkit {html.escape(lx_ver)}",
        ),
        _h("span", "This page is only visible in debug mode."),
        class_="footer",
    )
    return (
        "<!DOCTYPE html>"
        '<html lang="en">'
        "<head>"
        '<meta charset="utf-8">'
        f"<title>{html.escape(headline)}</title>"
        f"<style>{_CSS}</style>"
        "</head>"
        f"<body>{header}{main_content}{footer}</body>"
        "</html>"
    )


__all__ = ["_h", "_method_badge", "_render_debug_page", "_render_frames", "_render_kv"]
