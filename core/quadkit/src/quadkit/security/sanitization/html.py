"""HTML sanitization helpers used by :class:`InputSanitizer`."""

from __future__ import annotations

import html
import re

from quadkit.logging import get_logger
from quadkit.security.config import InputSanitizerConfig

logger = get_logger(__name__)

try:
    import nh3 as _nh3  # type: ignore[import-not-found]

    _NH3_AVAILABLE = True
except ImportError:  # pragma: no cover
    _NH3_AVAILABLE = False
    _nh3 = None

# Safe conservative defaults for the standalone sanitize_html function.
_DEFAULT_TAGS: frozenset[str] = frozenset(
    {
        "a",
        "abbr",
        "b",
        "blockquote",
        "br",
        "cite",
        "code",
        "dd",
        "dl",
        "dt",
        "em",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "i",
        "li",
        "ol",
        "p",
        "pre",
        "q",
        "s",
        "small",
        "span",
        "strong",
        "sub",
        "sup",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "u",
        "ul",
    }
)
_DEFAULT_ATTRS: dict[str, set[str]] = {
    "a": {"href", "title", "target", "rel"},
    "abbr": {"title"},
    "blockquote": {"cite"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
}


def sanitize_html(
    html_input: str,
    *,
    allowed_tags: set[str] | None = None,
    allowed_attributes: dict[str, set[str]] | None = None,
    strip_comments: bool = True,
) -> str:
    """Sanitize HTML using nh3 (Rust-based parser — not bypassable with malformed tags).

    Args:
        html_input: Raw HTML string to sanitize.
        allowed_tags: Allowed tag names. Defaults to a safe conservative set.
        allowed_attributes: Per-tag allowed attributes. Defaults to safe set.
        strip_comments: Whether to strip HTML comments. Default True.

    Returns:
        Sanitized HTML string safe for rendering.

    Raises:
        ImportError: If the ``nh3`` package is not installed.
    """
    if not _NH3_AVAILABLE:  # pragma: no cover
        raise ImportError(
            "HTML sanitization requires the 'nh3' package. "
            "Install it with: pip install quadkit[security]"
        )
    tags = allowed_tags if allowed_tags is not None else set(_DEFAULT_TAGS)
    attrs = allowed_attributes if allowed_attributes is not None else _DEFAULT_ATTRS

    return str(
        _nh3.clean(
            html_input,
            tags=tags,
            attributes=attrs,
            strip_comments=strip_comments,
            link_rel=None,
        )
    )


class HtmlSanitizer:
    """Sanitizer providing HTML-related sanitization helpers."""

    _DANGEROUS_ATTR_RE = re.compile(
        r'\s+(?:on\w+|style|srcdoc|formaction|action)\s*=\s*(?:"[^"]*"|'
        r"'[^']*'|[^\s>\n]*)",
        re.IGNORECASE,
    )
    _DANGEROUS_TAG_RE = re.compile(
        r"<(?:script|iframe|object|embed|link|meta|base)(?:\s[^>]*)?>.*?</(?:script|iframe|object|embed|link|meta|base)>"
        r"|<(?:script|iframe|object|embed|link|meta|base)(?:\s[^>]*)?/?>",
        re.IGNORECASE | re.DOTALL,
    )

    def __init__(self, config: InputSanitizerConfig) -> None:
        """Initialize with sanitizer configuration.

        Args:
            config: Input sanitizer configuration instance.
        """
        self._config = config

    def strip_html(self, value: str) -> str:
        """Strip disallowed HTML tags from the value using nh3.

        Args:
            value: HTML string to sanitize.

        Returns:
            String with disallowed tags removed.

        Raises:
            ImportError: If the ``nh3`` package is not installed.
        """
        if not _NH3_AVAILABLE:  # pragma: no cover
            raise ImportError(
                "HTML tag stripping requires the 'nh3' package. "
                "Install it with: pip install quadkit[security]"
            )
        if not value:
            return value

        tags: set[str] = (
            set(self._config.allowed_tags) if self._config.allowed_tags else set()
        )
        return str(
            _nh3.clean(
                value,
                tags=tags,
                attributes=None,
                strip_comments=self._config.strip_comments,
            )
        )

    def strip_dangerous(self, text: str) -> str:
        """Strip dangerous HTML tags and attributes from text.

        Removes elements that are dangerous regardless of context (e.g.
        ``<script>``, ``<iframe>``) and event-handler / injection attributes
        (e.g. ``onclick``, ``style``, ``srcdoc``) using compiled regex patterns.
        This is intentionally lighter than :meth:`strip_html`: it leaves safe
        markup intact while neutralising the most harmful vectors.

        Args:
            text: Input text to sanitize.

        Returns:
            Text with dangerous tags and attributes removed.
        """
        result = self._DANGEROUS_TAG_RE.sub("", text)
        return self._DANGEROUS_ATTR_RE.sub("", result)

    def escape_html(self, value: str) -> str:
        """Escape HTML special characters."""
        if not value:
            return value
        return html.escape(value)


__all__ = ["HtmlSanitizer", "sanitize_html"]
