"""URL and path sanitization helpers."""

from __future__ import annotations

import re

from quadkit.contracts.security import (
    HostResolver,
)
from quadkit.contracts.security import (
    is_safe_url_for_request as _is_safe_url_for_request,
)
from quadkit.logging import get_logger

logger = get_logger(__name__)


class UrlSanitizer:
    """Sanitizer for URLs, paths, and SSRF protections."""

    _URL_SCHEME_RE = re.compile(r"^[\x00-\x20]*([^\x00-\x20:]+):", re.IGNORECASE)
    _DANGEROUS_SCHEMES: frozenset[str] = frozenset(
        {"javascript", "vbscript", "data", "file"}
    )
    _PATH_TRAVERSAL_RE = re.compile(r"\.{2,}[/\\]|[/\\]\.{2,}|^\.{2,}$")

    def sanitize_url(self, url: str) -> str:
        """Return an empty string when the URL uses a dangerous scheme."""
        if not url:
            return url

        match = self._URL_SCHEME_RE.match(url.lstrip())
        if match:
            scheme = match.group(1).lower().replace("\x00", "").replace(" ", "")
            if scheme in self._DANGEROUS_SCHEMES:
                logger.warning("security.dangerous_url_scheme", scheme=scheme)
                return ""

        return url

    def sanitize_path(self, path: str) -> str:
        """Strip traversal sequences and null bytes from file paths."""
        if not path:
            return path

        sanitized = path.replace("\x00", "")
        previous: str | None = None
        while sanitized != previous:
            previous = sanitized
            sanitized = self._PATH_TRAVERSAL_RE.sub("", sanitized)

        if sanitized != path:
            logger.warning(
                "security.path_traversal_detected",
                original_length=len(path),
                sanitized_length=len(sanitized),
            )

        return sanitized

    def is_safe_url_for_request(
        self,
        url: str,
        *,
        resolver: HostResolver | None = None,
    ) -> bool:
        """Return False if the URL resolves to a private or reserved IP.

        Delegates to the single shared primitive in ``quadkit.contracts``
        (DNS-aware and fail-closed).

        Args:
            url: URL to evaluate.
            resolver: Optional injectable hostname resolver (for tests).

        Returns:
            True only when a request to ``url`` cannot reach a private target.
        """
        return _is_safe_url_for_request(url, resolver=resolver)


__all__ = ["UrlSanitizer"]
