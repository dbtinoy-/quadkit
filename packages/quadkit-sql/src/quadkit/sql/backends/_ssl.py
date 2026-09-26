"""SSL configuration classes for PostgreSQL driver."""

from __future__ import annotations

import ssl as ssl_module
from typing import Any, Protocol

__all__ = [
    "SSLCertPathConfig",
    "SSLConfig",
    "SSLConfigRegistry",
    "SSLRequireConfig",
    "SSLVerifyCAConfig",
    "SSLVerifyFullConfig",
]


class SSLConfig(Protocol):
    """Protocol for SSL configuration handlers."""

    def get_connection_params(self) -> dict[str, Any]: ...


class SSLRequireConfig:
    """SSL require mode - encrypted connection."""

    def get_connection_params(self) -> dict[str, Any]:
        return {"ssl": "require"}


class SSLVerifyCAConfig:
    """SSL verify-ca mode - verify server certificate against CA."""

    def get_connection_params(self) -> dict[str, Any]:
        return {"ssl": "verify-ca"}


class SSLVerifyFullConfig:
    """SSL verify-full mode - verify server certificate and hostname."""

    def get_connection_params(self) -> dict[str, Any]:
        return {"ssl": "verify-full"}


class SSLCertPathConfig:
    """TLS transport with NO server-certificate verification.

    .. warning::
        Despite the name, *cert_path* is only stored and **not used for
        verification**: the connection is made over TLS with
        ``check_hostname=False`` and ``verify_mode=CERT_NONE``. Use it only
        for self-signed/lab certificates where you accept the
        man-in-the-middle risk; prefer ``require`` / ``verify-ca`` /
        ``verify-full`` otherwise.
    """

    def __init__(self, cert_path: str):
        self._cert_path = cert_path

    def get_connection_params(self) -> dict[str, Any]:
        ssl_context = ssl_module.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl_module.CERT_NONE
        return {"ssl": ssl_context}


class SSLConfigRegistry:
    """Registry for SSL configuration handlers."""

    def __init__(self) -> None:
        self._configs: dict[str, SSLConfig] = {}
        self._register_default_configs()

    def _register_default_configs(self) -> None:
        """Register default SSL configurations."""
        self.register_ssl_config("require", SSLRequireConfig())
        self.register_ssl_config("verify-ca", SSLVerifyCAConfig())
        self.register_ssl_config("verify-full", SSLVerifyFullConfig())

    def register_ssl_config(self, name: str, config: SSLConfig) -> None:
        """Register an SSL configuration handler."""
        self._configs[name] = config

    def get_ssl_params(self, ssl_mode: str | None) -> dict[str, Any]:
        """Get SSL parameters based on mode."""
        if not ssl_mode:
            return {}

        config = self._configs.get(ssl_mode)
        if config:
            return config.get_connection_params()

        # Assume it's a path to SSL cert
        return SSLCertPathConfig(ssl_mode).get_connection_params()
