"""Content Security Policy (CSP) builder with preset policies."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CSPPolicy:
    """Content Security Policy configuration builder.

    Builds the ``Content-Security-Policy`` header value from individual
    directive lists. Each list may contain quoted keywords like ``'self'``,
    ``'none'``, ``'unsafe-inline'``, as well as scheme and host sources.

    Example::

        policy = CSPPolicy.strict()
        headers = {"Content-Security-Policy": policy.build()}
    """

    default_src: list[str] = field(default_factory=lambda: ["'self'"])
    script_src: list[str] = field(default_factory=lambda: ["'self'"])
    style_src: list[str] = field(default_factory=lambda: ["'self'"])
    img_src: list[str] = field(default_factory=lambda: ["'self'", "data:"])
    connect_src: list[str] = field(default_factory=lambda: ["'self'"])
    font_src: list[str] = field(default_factory=lambda: ["'self'"])
    object_src: list[str] = field(default_factory=lambda: ["'none'"])
    frame_ancestors: list[str] = field(default_factory=lambda: ["'none'"])
    base_uri: list[str] = field(default_factory=lambda: ["'self'"])
    form_action: list[str] = field(default_factory=lambda: ["'self'"])
    upgrade_insecure_requests: bool = False
    report_uri: str | None = None
    report_only: bool = False

    def build(self, report_only: bool | None = None) -> str:
        """Build and return the CSP header value string.

        Args:
            report_only: If True, returns the report-only header name.
                If False, returns the enforce header name.
                If None, uses self.report_only instance attribute.
        """
        use_report_only = report_only if report_only is not None else self.report_only  # noqa: F841
        parts: list[str] = []
        for directive, sources in [
            ("default-src", self.default_src),
            ("script-src", self.script_src),
            ("style-src", self.style_src),
            ("img-src", self.img_src),
            ("connect-src", self.connect_src),
            ("font-src", self.font_src),
            ("object-src", self.object_src),
            ("frame-ancestors", self.frame_ancestors),
            ("base-uri", self.base_uri),
            ("form-action", self.form_action),
        ]:
            if sources:
                parts.append(f"{directive} {' '.join(sources)}")
        if self.upgrade_insecure_requests:
            parts.append("upgrade-insecure-requests")
        if self.report_uri:
            parts.append(f"report-uri {self.report_uri}")
        return "; ".join(parts)

    def get_header_name(self) -> str:
        """Return the appropriate CSP header name based on report_only setting.

        Returns:
            'Content-Security-Policy-Report-Only' if report_only is True,
            otherwise 'Content-Security-Policy'.
        """
        return (
            "Content-Security-Policy-Report-Only"
            if self.report_only
            else "Content-Security-Policy"
        )

    @classmethod
    def strict(cls) -> CSPPolicy:
        """Strict preset — blocks inline scripts, eval, and external fonts."""
        return cls(
            script_src=["'self'"],
            style_src=["'self'"],
            object_src=["'none'"],
            frame_ancestors=["'none'"],
            upgrade_insecure_requests=True,
        )

    @classmethod
    def relaxed(cls) -> CSPPolicy:
        """Relaxed preset — allows popular CDNs and Google Fonts."""
        return cls(
            script_src=["'self'", "https://cdn.jsdelivr.net"],
            style_src=["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
            font_src=["'self'", "https://fonts.gstatic.com"],
            img_src=["'self'", "data:", "https:"],
        )

    @classmethod
    def api_only(cls) -> CSPPolicy:
        """API-only preset — blocks all document/resource loading."""
        return cls(
            default_src=["'none'"],
            script_src=["'none'"],
            style_src=["'none'"],
            img_src=["'none'"],
            connect_src=["'self'"],
            font_src=["'none'"],
            object_src=["'none'"],
            frame_ancestors=["'none'"],
        )


__all__ = ["CSPPolicy"]
