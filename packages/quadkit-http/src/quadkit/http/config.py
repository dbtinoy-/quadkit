"""HTTP client configuration models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar
from urllib.parse import urlparse

from quadkit.config.base import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.http.constants import (
    DEFAULT_MAX_CONNECTIONS,
    DEFAULT_MAX_CONNECTIONS_PER_HOST,
    DEFAULT_MAX_KEEPALIVE_CONNECTIONS,
    DEFAULT_TIMEOUT,
    DEFAULT_TTL_DNS_CACHE,
)
from quadkit.http.exceptions import HTTPClientError
from quadkit.http.validation import validate_url
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class ConnectionPoolConfig(BaseConfig):
    """Configuration for the HTTP connection pool.

    Attributes:
        max_connections: Maximum total concurrent connections (default: 10).
        max_keepalive_connections: Keep-alive connections per host (default: 5).
        max_connections_per_host: Maximum connections per individual host (default: 10).
        timeout: Request timeout in seconds (default: 30.0).
        ttl_dns_cache: DNS cache TTL in seconds (default: 300).
        force_close: Force-close connections after use (default: False).
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    max_connections: int = DEFAULT_MAX_CONNECTIONS
    max_keepalive_connections: int = DEFAULT_MAX_KEEPALIVE_CONNECTIONS
    max_connections_per_host: int = DEFAULT_MAX_CONNECTIONS_PER_HOST
    timeout: float = DEFAULT_TIMEOUT
    ttl_dns_cache: int = DEFAULT_TTL_DNS_CACHE
    force_close: bool = False


@dataclass(init=False)
class HTTPClientConfig(BaseConfig):
    """Top-level configuration for :class:`~quadkit.http.HTTPClient`.

    Attributes:
        pool: Connection pool settings.
        proxy: Optional HTTP/HTTPS proxy URL (e.g. ``"http://proxy.example.com:8080"``).
            Applied to all requests made by the client.
        trust_env: Whether to read proxy settings from environment variables
            (``HTTP_PROXY``, ``HTTPS_PROXY``, ``NO_PROXY``).  Defaults to
            ``True`` — set to ``False`` to ignore environment proxies.
        cookie_jar: Whether to enable an in-memory cookie jar that persists
            cookies across requests within a single :class:`HTTPClient` session.
            Defaults to ``True``.
        enforce_url_safety: Reject per-request URLs that could reach
            private/reserved hosts. Defaults to ``True`` (safe by default);
            set ``False`` only for clients whose targets are fixed, trusted,
            operator-set URLs.
    """

    config_section: ClassVar[str] = "http"

    name: str = "http"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    pool: ConnectionPoolConfig = field(default_factory=ConnectionPoolConfig)
    proxy: str | None = None
    trust_env: bool = True
    cookie_jar: bool = True
    enforce_url_safety: bool = True
    max_redirects: int = 5

    def __post_init__(self) -> None:
        """Validate proxy URL format if provided."""
        if self.proxy is not None:
            validate_url(self.proxy, require_scheme=True)
            parsed = urlparse(self.proxy)
            if not parsed.netloc:
                raise HTTPClientError(
                    f"Proxy URL must include hostname/IP: {self.proxy!r}"
                )


__all__ = [
    "ConnectionPoolConfig",
    "HTTPClientConfig",
]
