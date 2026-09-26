"""Redis secret store implementation.

Secrets are stored in Redis with an optional Fernet symmetric encryption layer
(D11.1).  When an ``encryption_key`` is supplied values are encrypted before
being written and decrypted on read, so at-rest values in Redis are opaque
ciphertext.

Usage::

    # Without encryption (plaintext, not recommended for production)
    store = RedisSecretStore(url="redis://localhost:6379")

    # With encryption — key must be a URL-safe base64-encoded 32-byte key
    import secrets, base64
    key = base64.urlsafe_b64encode(secrets.token_bytes(32))
    store = RedisSecretStore(url="redis://localhost:6379", encryption_key=key)
"""

from __future__ import annotations

from datetime import UTC, datetime
import time
from typing import Any, cast

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.logging import get_logger

logger = get_logger(__name__)

redis: Any = None
RedisError: type[Exception] = Exception
try:
    import redis.asyncio as redis
    from redis.exceptions import RedisError as _RedisError

    RedisError = _RedisError
    HAS_REDIS = True
except ImportError as e:
    redis = None
    RedisError = Exception
    HAS_REDIS = False
    logger.debug("Redis package not available for secrets: %s", e, exc_info=True)
except (OSError, RuntimeError, AttributeError):
    # Unexpected error importing redis - disable and log
    redis = None
    RedisError = Exception
    HAS_REDIS = False
    logger.exception("Unexpected error importing redis module for secrets")


from typing import TYPE_CHECKING

# Import the SecretStore protocol only for typing to avoid a runtime circular import
if TYPE_CHECKING:
    from collections.abc import Awaitable

    from quadkit.contracts import SecretStore

# At runtime, inherit from object to avoid import cycles; typing will see the proper base.
# Use an explicit mypy ignore for the assignment used as a base class so mypy does not
# treat the variable as an invalid type at runtime.
if TYPE_CHECKING:
    BaseSecretStore = SecretStore
else:
    BaseSecretStore = object


class RedisSecretStore(BaseSecretStore):  # type: ignore[valid-type,misc]
    """Redis implementation of SecretStore with optional at-rest encryption.

    Args:
        url: Redis connection URL (e.g. ``redis://localhost:6379/0``).
        prefix: Optional string prefix applied to every key stored in Redis.
        encryption_key: Optional Fernet symmetric encryption key (32-byte
            URL-safe base64-encoded bytes or string).  When provided all
            secret values are encrypted before writing and decrypted on
            read.  Generate one with::

                import secrets, base64
                key = base64.urlsafe_b64encode(secrets.token_bytes(32))
    """

    def __init__(
        self,
        url: str = "",
        prefix: str = "",
        encryption_key: bytes | str | None = None,
        client: Any | None = None,
    ):
        self.url = url
        self.prefix = prefix
        self._client: redis.Redis | None = client
        self._fernet: Any | None = None

        if encryption_key is not None:
            try:
                from cryptography.fernet import Fernet

                if isinstance(encryption_key, str):
                    encryption_key = encryption_key.encode()
                self._fernet = Fernet(encryption_key)
                logger.debug("RedisSecretStore: Fernet encryption enabled")
            except ImportError:
                logger.warning(
                    "cryptography package not installed; "
                    "RedisSecretStore will store secrets in plaintext. "
                    "Install with: pip install cryptography",
                )

    def _encrypt(self, value: str) -> str:
        """Encrypt a plaintext value if encryption is configured."""
        if self._fernet is None:
            return value
        return cast("str", self._fernet.encrypt(value.encode()).decode())

    def _decrypt(self, value: str) -> str:
        """Decrypt a ciphertext value if encryption is configured."""
        if self._fernet is None:
            return value
        try:
            return cast("str", self._fernet.decrypt(value.encode()).decode())
        except Exception as e:  # noqa: BLE001 — cryptography raises varied exceptions; fallback is intentional
            # Return as-is if decryption fails (e.g. value was stored unencrypted).
            logger.warning(
                "secret_decrypt_failed",
                error=str(e),
                hint="Ensure all secrets were stored with the same encryption key.",
            )
            return value

    async def _get_client(self) -> redis.Redis:
        """Lazy client initialization"""
        if self._client is None:
            self._client = redis.from_url(self.url, decode_responses=True)
        return self._client

    async def close(self) -> None:
        """Close the Redis client, releasing its connection pool."""
        if self._client is not None:
            close_fn = getattr(self._client, "aclose", None) or getattr(
                self._client, "close", None
            )
            if close_fn is not None:
                result = close_fn()
                if hasattr(result, "__await__"):
                    await result
            self._client = None

    def _key(self, key: str) -> str:
        """Apply prefix to key"""
        return f"{self.prefix}{key}" if self.prefix else key

    async def get_secret(self, key: str) -> str | None:
        """Get a secret by name, decrypting if encryption is configured."""
        client = await self._get_client()
        result = await client.get(f"secret:{self._key(key)}")
        if result is None:
            return None
        return self._decrypt(cast("str", result))

    async def set_secret(self, key: str, value: str) -> None:
        """Set a secret, encrypting if encryption is configured."""
        client = await self._get_client()
        encrypted = self._encrypt(value)
        await cast("Awaitable[Any]", client.set(f"secret:{self._key(key)}", encrypted))

    async def delete_secret(self, key: str) -> None:
        """Delete a secret"""
        client = await self._get_client()

        await cast("Awaitable[Any]", client.delete(f"secret:{self._key(key)}"))

    async def list_secrets(self, prefix: str | None = None) -> list[str]:
        """List secrets with optional prefix"""
        client = await self._get_client()
        search_prefix = f"secret:{self._key(prefix or '')}*"
        keys = await client.keys(search_prefix)
        # Remove the "secret:" prefix from results
        result = []
        for key in keys:
            clean_key = (
                key[len(f"secret:{self.prefix}") :]
                if self.prefix
                else key[len("secret:") :]
            )
            result.append(clean_key)
        return result

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check the health of the secret store"""
        start_time = time.monotonic()
        try:
            client = await self._get_client()

            await cast("Awaitable[Any]", client.ping())
            duration_ms = (time.monotonic() - start_time) * 1000
            return HealthCheckResult(
                component="secret_store",
                status=HealthStatus.HEALTHY,
                message="Redis secret store is healthy",
                details={
                    "driver": "redis",
                    "url": self.url,
                },
                duration_ms=duration_ms,
                checked_at=datetime.now(UTC),
            )
        except Exception as e:  # noqa: BLE001 — a health-check failure degrades the status, never raises
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.exception("Redis secret store health check failed")
            return HealthCheckResult(
                component="secret_store",
                status=HealthStatus.UNHEALTHY,
                message=f"Redis secret store unhealthy: {e!s}",
                error=str(e),
                details={
                    "driver": "redis",
                    "url": self.url,
                },
                duration_ms=duration_ms,
                checked_at=datetime.now(UTC),
            )
