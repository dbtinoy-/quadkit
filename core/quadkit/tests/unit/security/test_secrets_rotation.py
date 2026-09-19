"""Tests for SecretRotationScheduler.

Adapted from quadkit-security/tests/unit/test_secrets_rotation.py.
Adds origin-guard assertion proving modules resolve to quadkit core.
"""

from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone

import pytest

from quadkit.security.types import SecretRotationPolicy
from quadkit.security.secrets import (
    InMemorySecretStore,
    SecretMetadata,
    SecretRotationResult,
    SecretRotationScheduler,
)


# ---------------------------------------------------------------------------
# Origin guard — proves core package is being exercised
# ---------------------------------------------------------------------------


class TestSecretsRotationModuleIsCore:
    """Verify secrets rotation resolves to quadkit core, not quadkit-security."""

    def test_secrets_rotation_module_is_core_package(self) -> None:
        spec = importlib.util.find_spec("quadkit.security.secrets.rotation")
        assert spec is not None
        assert spec.origin is not None
        assert "quadkit-security" not in spec.origin, (
            f"Expected secrets.rotation to resolve to quadkit core, "
            f"got: {spec.origin!r}"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeSecretStore:
    """Fake secret store for testing."""

    def __init__(self, secrets: dict[str, str] | None = None) -> None:
        self._secrets: dict[str, str] = dict(secrets or {})

    def get_secret(self, name: str) -> str:
        if name not in self._secrets:
            raise KeyError(f"Secret '{name}' not found")
        return self._secrets[name]

    def set_secret(self, name: str, value: str) -> None:
        self._secrets[name] = value

    def delete_secret(self, name: str) -> None:
        if name not in self._secrets:
            raise KeyError(f"Secret '{name}' not found")
        del self._secrets[name]

    def exists(self, name: str) -> bool:
        return name in self._secrets


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSecretRotationScheduler:
    """Tests for SecretRotationScheduler."""

    @pytest.fixture
    def secret_store(self) -> FakeSecretStore:
        return FakeSecretStore({"api-key": "test-key", "db-pass": "db-pass"})

    @pytest.fixture
    def scheduler(self, secret_store: FakeSecretStore) -> SecretRotationScheduler:
        return SecretRotationScheduler(
            secret_store=secret_store,
            policies={
                "api-key": SecretRotationPolicy(
                    max_age_days=30,
                    rotation_warning_days=7,
                ),
                "db-pass": SecretRotationPolicy(
                    max_age_days=90,
                    rotation_warning_days=14,
                ),
            },
        )

    def test_set_and_get_policy(self, scheduler: SecretRotationScheduler) -> None:
        """Test setting and getting policies."""
        policy = SecretRotationPolicy(max_age_days=15)
        scheduler.set_policy("new-secret", policy)

        retrieved = scheduler.get_policy("new-secret")
        assert retrieved is not None
        assert retrieved.max_age_days == 15

    def test_remove_policy(self, scheduler: SecretRotationScheduler) -> None:
        """Test removing policies."""
        scheduler.remove_policy("api-key")
        assert scheduler.get_policy("api-key") is None

    @pytest.mark.asyncio
    async def test_check_secret_no_policy(
        self, scheduler: SecretRotationScheduler
    ) -> None:
        """Test checking a secret without a policy."""
        result = await scheduler.check_secret("unknown-secret")

        assert result.secret_name == "unknown-secret"
        assert result.rotation_needed is False
        assert result.message == "No rotation policy set"

    @pytest.mark.asyncio
    async def test_check_secret_fresh(
        self, scheduler: SecretRotationScheduler
    ) -> None:
        """Test checking a fresh secret."""
        result = await scheduler.check_secret("api-key")

        assert result.secret_name == "api-key"
        assert result.rotation_needed is False
        assert result.warning is False
        assert result.expired is False

    @pytest.mark.asyncio
    async def test_check_secret_warning(self, secret_store: FakeSecretStore) -> None:
        """Test checking a secret that's approaching expiry."""
        metadata_store = {
            "api-key": SecretMetadata(
                name="api-key",
                last_rotated=datetime.now(timezone.utc) - timedelta(days=25),
            )
        }

        scheduler = SecretRotationScheduler(
            secret_store=secret_store,
            policies={
                "api-key": SecretRotationPolicy(
                    max_age_days=30,
                    rotation_warning_days=7,
                )
            },
            metadata_store=metadata_store,
        )

        result = await scheduler.check_secret("api-key")

        assert result.warning is True
        assert result.expired is False
        assert "will expire" in result.message

    @pytest.mark.asyncio
    async def test_check_secret_expired(self, secret_store: FakeSecretStore) -> None:
        """Test checking an expired secret."""
        metadata_store = {
            "api-key": SecretMetadata(
                name="api-key",
                last_rotated=datetime.now(timezone.utc) - timedelta(days=35),
            )
        }

        scheduler = SecretRotationScheduler(
            secret_store=secret_store,
            policies={
                "api-key": SecretRotationPolicy(
                    max_age_days=30,
                    rotation_warning_days=7,
                )
            },
            metadata_store=metadata_store,
        )

        result = await scheduler.check_secret("api-key")

        assert result.expired is True
        assert result.rotation_needed is True
        assert "expired" in result.message.lower()

    @pytest.mark.asyncio
    async def test_check_secret_auto_rotate(
        self, secret_store: FakeSecretStore
    ) -> None:
        """Test checking a secret with auto_rotate enabled."""
        metadata_store = {
            "api-key": SecretMetadata(
                name="api-key",
                last_rotated=datetime.now(timezone.utc) - timedelta(days=25),
            )
        }

        scheduler = SecretRotationScheduler(
            secret_store=secret_store,
            policies={
                "api-key": SecretRotationPolicy(
                    max_age_days=30,
                    rotation_warning_days=7,
                    auto_rotate=True,
                )
            },
            metadata_store=metadata_store,
        )

        result = await scheduler.check_secret("api-key")
        assert result.rotation_needed is True

    @pytest.mark.asyncio
    async def test_check_all(self, scheduler: SecretRotationScheduler) -> None:
        """Test checking all secrets."""
        results = await scheduler.check_all()

        assert len(results) == 2
        names = {r.secret_name for r in results}
        assert names == {"api-key", "db-pass"}

    @pytest.mark.asyncio
    async def test_get_secrets_needing_rotation(
        self, secret_store: FakeSecretStore
    ) -> None:
        """Test getting list of secrets needing rotation."""
        metadata_store = {
            "api-key": SecretMetadata(
                name="api-key",
                last_rotated=datetime.now(timezone.utc) - timedelta(days=35),
            ),
            "db-pass": SecretMetadata(
                name="db-pass",
                last_rotated=datetime.now(timezone.utc) - timedelta(days=10),
            ),
        }

        scheduler = SecretRotationScheduler(
            secret_store=secret_store,
            policies={
                "api-key": SecretRotationPolicy(max_age_days=30),
                "db-pass": SecretRotationPolicy(max_age_days=90),
            },
            metadata_store=metadata_store,
        )

        needing_rotation = await scheduler.get_secrets_needing_rotation()

        assert "api-key" in needing_rotation
        assert "db-pass" not in needing_rotation

    def test_record_rotation(self, scheduler: SecretRotationScheduler) -> None:
        """Test recording a secret rotation."""
        scheduler.record_rotation("api-key")

        assert "api-key" in scheduler._metadata_store
        assert scheduler._metadata_store["api-key"].last_rotated is not None
