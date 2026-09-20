"""Content Security Policy configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from quadkit.config.base import BaseConfig
from quadkit.validation import ConfigDict, Field, model_validator

_DEFAULT_DIRECTIVES: dict[str, str] = {
    "default-src": "'self'",
    # plans/09172026 H-03: docs UI assets (Swagger UI, ReDoc) are vendored
    # and served from this application under /docs-static, so the default
    # policy needs no third-party origins and no 'unsafe-inline'/'unsafe-eval'
    # (the docs pages load scripts and styles as plain external files).
    # Operators who opt into a CDN via web.api_docs.cdn_base (or per-asset
    # URL overrides) get that origin merged in automatically at boot.
    "script-src": "'self'",
    "script-src-elem": "'self'",
    "style-src": "'self'",
    "style-src-elem": "'self'",
    "img-src": "'self' data: https: blob:",
    "font-src": "'self' data:",
    "connect-src": "'self'",
    # ReDoc spawns its search worker from a Blob URL.
    "worker-src": "'self' blob:",
    "frame-ancestors": "'none'",
    "base-uri": "'self'",
    "form-action": "'self'",
}


@dataclass(init=False)
class CSPConfig(BaseConfig):
    """Content Security Policy configuration.

    Manages CSP directives as a ``dict[str, str | set[str]]`` and
    serialises them to the ``Content-Security-Policy`` header value
    via :meth:`build_header`.

    Attributes:
        enabled: Emit the ``Content-Security-Policy`` header.
        directives: Mapping of CSP directive name to source expression(s).
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    enabled: bool = Field(
        default=False, description="Emit the Content-Security-Policy header"
    )
    directives: dict[str, Any] = Field(
        default_factory=lambda: dict(_DEFAULT_DIRECTIVES),
        description="CSP directives mapping directive name to source expression(s)",
    )

    @model_validator(mode="after")
    def _merge_default_directives(self) -> CSPConfig:
        """Merge the framework default directives into the configured ones.

        User-supplied directives always win per-key; any directive the user
        omitted falls back to the safe framework default. This prevents a
        partial ``directives`` dict from silently dropping defaults — e.g. a
        user configuring only ``style-src`` previously lost the default
        ``style-src-elem`` with ``'unsafe-inline'``, which then blocked all
        inline styles (the CSP fallback chain does not apply when the
        ``-elem`` variant is present).

        Returns:
            Self with merged directives.
        """
        merged = dict(_DEFAULT_DIRECTIVES)
        merged.update(self.directives)
        self.directives = merged
        return self

    def build_header(self) -> str:
        """Build the ``Content-Security-Policy`` header value.

        Returns:
            Semicolon-delimited CSP policy string ready for the response header.
        """
        parts: list[str] = []
        for directive, value in self.directives.items():
            if isinstance(value, set):
                csp_value = " ".join(str(v) for v in value) if value else "'none'"
                parts.append(f"{directive} {csp_value}")
            else:
                str_value = str(value)
                if str_value:
                    parts.append(f"{directive} {str_value}")
                else:
                    parts.append(directive)
        return "; ".join(parts)


__all__ = [
    "CSPConfig",
]
