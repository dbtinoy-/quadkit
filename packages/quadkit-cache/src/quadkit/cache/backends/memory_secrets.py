"""In-memory secret store implementation"""

from __future__ import annotations

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.security.secrets import SecretStoreProtocol


class MemorySecretStore(SecretStoreProtocol):
    """In-memory secret store for testing"""

    def __init__(self, secrets: dict[str, str] | None = None):
        self._secrets = secrets or {}

    async def get_secret(self, key: str) -> str | None:  # type: ignore[override]
        """Get a secret by name"""
        return self._secrets.get(key)

    async def set_secret(self, key: str, value: str) -> None:  # type: ignore[override]
        """Set a secret"""
        self._secrets[key] = value

    async def delete_secret(self, key: str) -> None:  # type: ignore[override]
        """Delete a secret"""
        self._secrets.pop(key, None)

    async def list_secrets(self, prefix: str | None = None) -> list[str]:
        """List secrets with optional prefix"""
        keys = list(self._secrets.keys())
        if prefix:
            keys = list(filter(lambda k: k.startswith(prefix), keys))
        return keys

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check the health of the secret store"""
        return HealthCheckResult(
            component="memory-secrets",
            status=HealthStatus.HEALTHY,
            details={"driver": "memory", "secrets_count": len(self._secrets)},
        )
