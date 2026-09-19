"""Tests for security secret store implementations.

Adapted from quadkit-security/tests/unit/test_secrets_store.py.
Adds origin-guard assertion proving modules resolve to quadkit core.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

from quadkit.contracts.security import SecretNotFoundError
from quadkit.security.exceptions import SecretAccessError
from quadkit.security.secrets import (
    EnvSecretStore,
    FileSecretStore,
    InMemorySecretStore,
    SecretValue,
)

# ---------------------------------------------------------------------------
# Origin guard — proves core package is being exercised
# ---------------------------------------------------------------------------


class TestSecretsModuleIsCore:
    """Verify secrets store resolves to quadkit core, not quadkit-security."""

    def test_secrets_store_module_is_core_package(self) -> None:
        spec = importlib.util.find_spec("quadkit.security.secrets.store")
        assert spec is not None
        assert spec.origin is not None
        assert "quadkit-security" not in spec.origin, (
            f"Expected secrets.store to resolve to quadkit core, got: {spec.origin!r}"
        )


# ---------------------------------------------------------------------------
# SecretValue
# ---------------------------------------------------------------------------


def test_secret_value_masks_repr() -> None:
    """SecretValue repr should never reveal the underlying secret text."""
    secret = SecretValue("super-secret-value")

    assert secret == "super-secret-value"
    assert "super-secret-value" not in repr(secret)
    assert "masked" in repr(secret)


def test_secret_value_masks_f_string_and_format() -> None:
    secret = SecretValue("super-secret-value")
    assert f"{secret}" != "super-secret-value"
    assert format(secret) != "super-secret-value"
    assert "super-secret-value" not in f"{secret}"
    assert str(secret) == "super-secret-value"


# ---------------------------------------------------------------------------
# InMemorySecretStore
# ---------------------------------------------------------------------------


def test_inmemory_secret_store_has_secret() -> None:
    """InMemorySecretStore implements protocol-style has_secret."""
    store = InMemorySecretStore({"API_KEY": "abc123"})

    assert store.has_secret("API_KEY") is True
    assert store.exists("API_KEY") is True
    assert store.get_secret("API_KEY") == "abc123"


def test_inmemory_store_raises_on_missing() -> None:
    store = InMemorySecretStore()
    with pytest.raises(SecretNotFoundError):
        store.get_secret("missing")


def test_inmemory_store_set_and_delete() -> None:
    store = InMemorySecretStore()
    store.set_secret("key", "val")
    assert store.has_secret("key") is True
    store.delete_secret("key")
    assert store.has_secret("key") is False


def test_inmemory_store_delete_raises_on_missing() -> None:
    store = InMemorySecretStore()
    with pytest.raises(SecretNotFoundError):
        store.delete_secret("not_there")


# ---------------------------------------------------------------------------
# EnvSecretStore
# ---------------------------------------------------------------------------


def test_env_secret_store_clears_after_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """EnvSecretStore should clear environment variable after read by default."""
    monkeypatch.setenv("QK_SECRETS_TEST_SECRET", "value-1")
    store = EnvSecretStore(clear_after_read=True)

    assert store.get_secret("QK_SECRETS_TEST_SECRET") == "value-1"
    assert "QK_SECRETS_TEST_SECRET" not in os.environ


def test_env_secret_store_preserves_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EnvSecretStore can preserve values when clear_after_read is disabled."""
    monkeypatch.setenv("QK_SECRETS_TEST_SECRET", "value-2")
    store = EnvSecretStore(clear_after_read=False)

    assert store.get_secret("QK_SECRETS_TEST_SECRET") == "value-2"
    assert os.environ.get("QK_SECRETS_TEST_SECRET") == "value-2"


def test_env_secret_store_missing_raises() -> None:
    """EnvSecretStore should raise SecretNotFoundError for unknown keys."""
    store = EnvSecretStore()

    with pytest.raises(SecretNotFoundError):
        store.get_secret("DOES_NOT_EXIST_ORI_TEST")


# ---------------------------------------------------------------------------
# FileSecretStore
# ---------------------------------------------------------------------------


def test_file_secret_store_rejects_open_permissions(tmp_path: Path) -> None:
    """FileSecretStore should reject group/world-accessible secret files."""
    base = tmp_path / "secrets"
    base.mkdir()
    path = base / "api_key"
    path.write_text("abcd", encoding="utf-8")
    path.chmod(0o644)

    store = FileSecretStore(base)
    with pytest.raises(SecretAccessError):
        store.get_secret("api_key")


def test_file_secret_store_write_sets_owner_permissions(tmp_path: Path) -> None:
    """FileSecretStore writes with owner-only permissions and reads back value."""
    base = tmp_path / "secrets"
    base.mkdir()
    store = FileSecretStore(base)

    store.set_secret("db_password", "pw-123")

    path = base / "db_password"
    assert path.exists()
    assert (path.stat().st_mode & 0o777) == 0o600
    assert store.get_secret("db_password") == "pw-123"
