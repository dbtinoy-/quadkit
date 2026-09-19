"""Secret rotation scheduler for automated secret rotation management."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from quadkit.logging import get_logger
from quadkit.security.secrets.types import SecretMetadata, SecretRotationResult

if TYPE_CHECKING:
    from quadkit.contracts.security.secrets import SecretStoreProtocol
    from quadkit.security.types import SecretRotationPolicy

logger = get_logger(__name__)


class SecretRotationScheduler:
    """Scheduler that checks secrets against rotation policies and emits warnings.

    This class monitors secrets and determines which ones need rotation based
    on their associated ``SecretRotationPolicy``. It can be run manually or
    as a scheduled background task.

    Example::

        scheduler = SecretRotationScheduler(
            secret_store=my_store,
            policies={
                "api-key": SecretRotationPolicy(max_age_days=30),
                "db-password": SecretRotationPolicy(max_age_days=90),
            },
        )

        results = await scheduler.check_all()
    """

    def __init__(
        self,
        secret_store: SecretStoreProtocol,
        policies: dict[str, SecretRotationPolicy] | None = None,
        metadata_store: dict[str, SecretMetadata] | None = None,
    ) -> None:
        """Initialize the rotation scheduler.

        Args:
            secret_store: The secret store to check.
            policies: Mapping of secret names to their rotation policies.
            metadata_store: Optional store for secret metadata (creation times).
        """
        self._secret_store = secret_store
        self._policies: dict[str, SecretRotationPolicy] = policies or {}
        self._metadata_store: dict[str, SecretMetadata] = metadata_store or {}
        self._check_times: dict[str, datetime] = {}

    def set_policy(self, name: str, policy: SecretRotationPolicy) -> None:
        """Set or update the rotation policy for a secret."""
        self._policies[name] = policy

    def remove_policy(self, name: str) -> None:
        """Remove the rotation policy for a secret."""
        self._policies.pop(name, None)

    def get_policy(self, name: str) -> SecretRotationPolicy | None:
        """Get the rotation policy for a secret."""
        return self._policies.get(name)

    async def check_secret(self, name: str) -> SecretRotationResult:
        """Check a single secret against its rotation policy.

        Args:
            name: Secret name to check.

        Returns:
            SecretRotationResult with the check outcome.
        """
        policy = self._policies.get(name)
        if policy is None:
            return SecretRotationResult(
                secret_name=name,
                rotation_needed=False,
                message="No rotation policy set",
            )

        metadata = self._metadata_store.get(name)

        try:
            self._secret_store.get_secret(name)
        except (OSError, ConnectionError, RuntimeError, ValueError, KeyError) as e:
            logger.warning("secret_check_failed", secret_name=name, error=str(e))
            return SecretRotationResult(
                secret_name=name,
                rotation_needed=False,
                message=f"Failed to access secret: {e}",
            )

        now = datetime.now(UTC)
        if metadata and metadata.last_rotated:
            age = now - metadata.last_rotated
            age_days = age.total_seconds() / 86400
        elif name in self._check_times:
            age = now - self._check_times[name]
            age_days = age.total_seconds() / 86400
        else:
            age_days = 0.0
            self._check_times[name] = now

        self._check_times[name] = now

        expired = policy.is_expired(age_days)
        warning = policy.is_warning_due(age_days) and not expired
        rotation_needed = expired or (warning and policy.auto_rotate)

        message = ""
        if expired:
            message = f"Secret expired {age_days - policy.max_age_days:.1f} days ago"
        elif warning:
            message = f"Secret will expire in {policy.max_age_days - age_days:.1f} days"

        return SecretRotationResult(
            secret_name=name,
            rotation_needed=rotation_needed,
            warning=warning,
            expired=expired,
            age_days=age_days,
            message=message,
        )

    async def check_all(self) -> list[SecretRotationResult]:
        """Check all secrets with policies.

        Returns:
            List of rotation results for all monitored secrets.
        """
        results: list[SecretRotationResult] = []
        for name in self._policies:
            result = await self.check_secret(name)
            results.append(result)

            if result.warning:
                logger.warning(
                    "secret_rotation_warning",
                    secret_name=name,
                    age_days=result.age_days,
                    message=result.message,
                )
            elif result.expired:
                logger.error(
                    "secret_rotation_expired",
                    secret_name=name,
                    age_days=result.age_days,
                    message=result.message,
                )

        return results

    async def get_secrets_needing_rotation(self) -> list[str]:
        """Get list of secret names that need rotation."""
        results = await self.check_all()
        return [r.secret_name for r in results if r.rotation_needed]

    def record_rotation(self, name: str) -> None:
        """Record that a secret was rotated.

        Args:
            name: Secret name that was rotated.
        """
        now = datetime.now(UTC)
        if name in self._metadata_store:
            self._metadata_store[name].last_rotated = now
        else:
            self._metadata_store[name] = SecretMetadata(
                name=name,
                last_rotated=now,
            )
        self._check_times[name] = now
        logger.info("secret_rotation_recorded", secret_name=name)


__all__ = [
    "SecretMetadata",
    "SecretRotationResult",
    "SecretRotationScheduler",
]
